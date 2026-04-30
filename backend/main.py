import os
import json
import jwt
import shutil
import urllib.request
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.search import search
from backend.ollama import generate
from backend.database import get_conn
from backend.auth import create_access_token, JWT_SECRET, ALGORITHM
from backend.config import RAW_DIR
from backend.ingestion import ingest_chunks, list_products

app = FastAPI(title="Altair Knowledge Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
        "http://[::1]:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Scenario system prompts
# ---------------------------------------------------------------------------

SCENARIO_SYSTEM = {
    "general": (
        "你是 Altair 官方技術文件助理，專門回答關於 Altair 軟體（HyperWorks、HyperMesh CFD、PBS、Flux、SimLab 等）的安裝、授權與使用問題。"
        "請只根據下方提供的文件內容回答，不要推測文件以外的資訊。"
        "若文件內容不足，請直接說「提供的文件未涵蓋此問題，建議洽 Altair 官方支援」。"
        "回答格式：先給精簡結論，再列出依據來源（標明文件名稱與段落）。"
    ),
    "engineer": (
        "你是 Altair 工程師技術支援助理，專精技術文件查詢與問題排查。"
        "請提供詳細的技術步驟、指令語法和參數說明。"
        "若涉及錯誤訊息，請逐步分析可能原因與解決方案，並標明對應文件來源。"
        "回答格式：條列操作步驟，附上指令範例，標示相關文件段落。"
    ),
    "sales": (
        "你是 Altair 業務支援助理，協助整理產品亮點與應用場景。"
        "請以客戶視角整理重點功能、版本差異和應用優勢，語氣專業但易懂，適合對外說明使用。"
        "聚焦在商業價值與用戶效益，避免過多底層技術細節。"
        "回答格式：先列核心亮點，再補充版本重點或差異說明。"
    ),
    "cs": (
        "你是 Altair 客服支援助理，協助快速回應客戶問題。"
        "請提供簡潔明確的解答，必要時附上操作步驟，語氣親切友善。"
        "確保回覆內容的一致性與正確性，複雜問題可建議升級技術支援。"
        "回答格式：直接給答案，操作類問題附上步驟，結尾可加確認語句。"
    ),
    "onboarding": (
        "你是 Altair 新人培訓助理，協助新進員工熟悉產品知識與作業規範。"
        "請用淺顯易懂的方式說明，避免過多技術術語，適時提供背景知識。"
        "幫助學習者建立完整的知識體系，循序漸進地引導理解。"
        "回答格式：先說明概念背景，再說明操作方式，附上學習建議。"
    ),
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str

class SearchRequest(BaseModel):
    query: str
    mode: str = "medium"
    top_k: int = 5
    product: str = ""
    version: str = ""
    doc_type: str = ""

class AskRequest(BaseModel):
    query: str
    mode: str = "medium"
    top_k: int = 5
    model: str = "qwen3:8b"
    scenario: str = "general"
    product: str = ""
    version: str = ""
    doc_type: str = ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_prompt(query: str, docs: list[str], metas: list[dict], scenario: str = "general") -> str:
    system = SCENARIO_SYSTEM.get(scenario, SCENARIO_SYSTEM["general"])
    parts = []
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        product = meta.get("product", "")
        version = meta.get("version", "")
        label = f"{product} {version}".strip() or meta.get("source_file", "")
        parts.append(
            f"[來源{i}] {label}\n"
            f"文件：{meta.get('source_file', '')}\n"
            f"段落：{doc}"
        )
    context = "\n\n".join(parts)
    return f"""{system}
使用繁體中文回答。

問題：{query}

文件內容：
{context}
"""


def get_current_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def get_status():
    status = {"db": False, "ollama": False}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        status["db"] = True
    except Exception:
        pass
    ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        req = urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=2)
        status["ollama"] = req.status == 200
    except Exception:
        pass
    return status


@app.post("/api/login")
def api_login(req: LoginRequest, request: Request):
    try:
        client_host = request.client.host if request.client else "unknown"
        client_ua = request.headers.get("user-agent", "unknown")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username FROM users WHERE username=%s", (req.username,))
                user = cur.fetchone()
                if not user:
                    cur.execute(
                        "INSERT INTO users(username) VALUES(%s) RETURNING id, username",
                        (req.username,),
                    )
                    user = cur.fetchone()
                user_id, username = user
                cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user_id,))
                cur.execute(
                    "INSERT INTO login_logs(user_id, ip_address, user_agent) VALUES(%s,%s,%s)",
                    (user_id, client_host, client_ua),
                )
                conn.commit()
        token = create_access_token({"sub": str(user_id), "username": username})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"username": username},
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.get("/api/products")
def api_products(mode: str = "medium"):
    return list_products(mode)


@app.get("/api/stats")
def get_stats(authorization: str = Header(None)):
    get_current_user(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM query_logs")
            total_queries = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM login_logs")
            total_logins = cur.fetchone()[0]
    return {
        "total_users": total_users,
        "total_docs": total_docs,
        "total_queries": total_queries,
        "total_logins": total_logins,
    }


@app.get("/api/logs")
def get_logs(authorization: str = Header(None), limit: int = 100):
    get_current_user(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ql.id, u.username, ql.query, ql.model, ql.mode, ql.created_at,
                       ql.sources_used, ql.scenario, ql.product, ql.version
                FROM query_logs ql
                LEFT JOIN users u ON ql.user_id = u.id
                ORDER BY ql.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "username": r[1] or "—",
            "query": r[2],
            "model": r[3],
            "mode": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "sources_used": r[6] or [],
            "scenario": r[7] or "general",
            "product": r[8] or "",
            "version": r[9] or "",
        }
        for r in rows
    ]


@app.get("/api/analytics")
def get_analytics(authorization: str = Header(None)):
    get_current_user(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT scenario, COUNT(*) FROM query_logs GROUP BY scenario ORDER BY COUNT(*) DESC")
            by_scenario = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT COALESCE(NULLIF(doc_type, ''), '未指定'), COUNT(*) FROM query_logs GROUP BY 1 ORDER BY COUNT(*) DESC")
            by_doc_type = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT product, COUNT(*) FROM query_logs WHERE product != '' GROUP BY product ORDER BY COUNT(*) DESC LIMIT 10")
            by_product = [{"product": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute("SELECT model, COUNT(*) FROM query_logs GROUP BY model ORDER BY COUNT(*) DESC")
            by_model = {r[0]: r[1] for r in cur.fetchall()}

    return {
        "by_scenario": by_scenario,
        "by_doc_type": by_doc_type,
        "by_product": by_product,
        "by_model": by_model,
    }


@app.post("/api/search")
def api_search(req: SearchRequest, authorization: str = Header(None)):
    get_current_user(authorization)
    result = search(req.query, mode=req.mode, top_k=req.top_k,
                    product=req.product, version=req.version, doc_type=req.doc_type)
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    return {
        "query": req.query,
        "items": [
            {
                "source_file": m["source_file"],
                "product": m.get("product", ""),
                "version": m.get("version", ""),
                "doc_type": m.get("doc_type", ""),
                "chunk_index": m["chunk_index"],
                "char_count": m["char_count"],
                "text": d,
            }
            for d, m in zip(docs, metas)
        ],
    }


@app.post("/api/ask")
def api_ask(req: AskRequest, authorization: str = Header(None)):
    payload = get_current_user(authorization)
    result = search(req.query, mode=req.mode, top_k=req.top_k,
                    product=req.product, version=req.version, doc_type=req.doc_type)
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    prompt = build_prompt(req.query, docs, metas, scenario=req.scenario)
    answer = generate(prompt, model=req.model)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO query_logs(user_id, query, response, sources_used, model, mode, top_k, scenario, doc_type, product, version) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    payload.get("sub"), req.query, answer,
                    json.dumps([m["source_file"] for m in metas]),
                    req.model, req.mode, req.top_k,
                    req.scenario, req.doc_type, req.product, req.version,
                ),
            )
        conn.commit()

    return {
        "query": req.query,
        "answer": answer,
        "model": req.model,
        "mode": req.mode,
        "sources": [
            {
                "source_file": m["source_file"],
                "product": m.get("product", ""),
                "version": m.get("version", ""),
                "doc_type": m.get("doc_type", ""),
                "chunk_index": m["chunk_index"],
                "char_count": m["char_count"],
            }
            for m in metas
        ],
    }


@app.post("/api/upload")
def api_upload(authorization: str = Header(None), file: UploadFile = File(...)):
    payload = get_current_user(authorization)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".txt"):
        raise HTTPException(status_code=400, detail="僅支援 PDF / DOCX / TXT")
    target_dir = RAW_DIR / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file.filename
    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents(title, source_path, uploaded_by) VALUES(%s,%s,%s) "
                "ON CONFLICT(source_path) DO UPDATE SET updated_at=NOW()",
                (file.filename, str(target_path), payload.get("sub")),
            )
        conn.commit()
    return {"message": "上傳成功", "filename": file.filename}


class QuizRequest(BaseModel):
    product: str = ""
    version: str = ""
    count: int = 5


@app.post("/api/quiz/generate")
def generate_quiz(req: QuizRequest, authorization: str = Header(None)):
    get_current_user(authorization)
    import re
    query = f"{req.product} {req.version} 安裝 設定 操作 重點".strip()
    result = search(query, mode="medium", top_k=8, product=req.product, version=req.version)
    docs = result["documents"][0]
    context = "\n\n---\n\n".join(docs[:6])

    prompt = f"""根據以下技術文件，出 {req.count} 道繁體中文簡答考題，測試讀者對文件的理解。

文件內容：
{context}

嚴格使用以下格式輸出，每題之間空一行，不要有其他說明：
Q: 問題內容
A: 標準答案"""

    raw = generate(prompt, model="qwen3:8b")
    questions = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        q = re.search(r"^Q[：:]\s*(.+)", block, re.MULTILINE)
        a = re.search(r"^A[：:]\s*([\s\S]+)", block, re.MULTILINE)
        if q and a:
            questions.append({"q": q.group(1).strip(), "a": a.group(1).strip()})
    return {"questions": questions[: req.count]}


@app.post("/api/ingest")
def api_ingest(background_tasks: BackgroundTasks, mode: str = "medium", authorization: str = Header(None)):
    get_current_user(authorization)
    background_tasks.add_task(lambda: ingest_chunks(mode))
    return {"message": f"索引建立中（{mode}），請稍後查詢結果"}

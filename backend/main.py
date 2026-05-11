import os
import json
import jwt
import logging
import shutil
import urllib.request
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.search import search
from backend.ollama import generate
from backend.database import get_conn
from backend.auth import create_access_token, JWT_SECRET, ALGORITHM
from backend.config import RAW_DIR, PRODUCT_LABELS, VENDOR_LABELS, CORS_ORIGINS, DEFAULT_LLM_MODEL, DEFAULT_SCENARIO_SYSTEM
from backend.ingestion import ingest_chunks, list_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Altair Knowledge Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    
    import traceback
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled Exception: {error_trace}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": error_trace},
    )

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
    model: str = DEFAULT_LLM_MODEL
    scenario: str = "general"
    product: str = ""
    version: str = ""
    doc_type: str = ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_scenario_prompt(scenario_key: str) -> str:
    """從資料庫獲取 System Prompt，若失敗或不存在則使用 config 中的預設值"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT prompt FROM system_scenarios WHERE key = %s", (scenario_key,))
                row = cur.fetchone()
                if row:
                    return row[0]
    except Exception as e:
        logger.error(f"Failed to fetch scenario '{scenario_key}' from DB: {e}")
    
    # Fallback 到 config.py
    return DEFAULT_SCENARIO_SYSTEM.get(scenario_key, DEFAULT_SCENARIO_SYSTEM["general"])

def build_prompt(query: str, docs: list[str], metas: list[dict], scenario: str = "general") -> str:
    system = get_scenario_prompt(scenario)
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


def get_current_user(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未經授權，請先登入")
    token = authorization.split(" ")[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="認證權杖 (Token) 無效或已過期")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    # 增加 LQS 環境變數檢查 (範例)
    lqs_host = os.getenv("LQS_HOST", "找不到環境變數")
    logger.info(f"執行健康檢查。LQS_HOST 狀態: {lqs_host}")
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
        logger.error("資料庫健康檢查失敗")

    from backend.config import OLLAMA_HOST
    try:
        req = urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
        status["ollama"] = req.status == 200
    except Exception:
        logger.error("Ollama 服務連線失敗")
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
                        "INSERT INTO users(username, password_hash) VALUES(%s, %s) RETURNING id, username",
                        (req.username, "no_password_required"),
                    )
                    user = cur.fetchone()
                user_id, username = user
                cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user_id,))
                cur.execute(
                    "INSERT INTO login_logs(user_id, ip_address, user_agent, status) VALUES(%s,%s,%s,%s)",
                    (user_id, client_host, client_ua, "success"),
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
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤: {str(e)}")


@app.get("/api/products")
def api_products(mode: str = "medium"):
    print(f"\n[API] 收到請求: GET /api/products?mode={mode}", flush=True)
    return list_products(mode)


@app.get("/api/stats")
def get_stats(user: dict = Depends(get_current_user)):
    try:
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
        return {"total_users": total_users, "total_docs": total_docs,
                "total_queries": total_queries, "total_logins": total_logins}
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"total_users": 0, "total_docs": 0, "total_queries": 0, "total_logins": 0}


@app.get("/api/logs")
def get_logs(limit: int = 100, user: dict = Depends(get_current_user)):
    try:
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
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        return []


@app.get("/api/analytics")
def get_analytics(user: dict = Depends(get_current_user)):
    empty = {"by_scenario": {}, "by_doc_type": {}, "by_product": [], "by_model": {}}
    try:
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

        return {"by_scenario": by_scenario, "by_doc_type": by_doc_type,
                "by_product": by_product, "by_model": by_model}
    except Exception as e:
        logger.error(f"Analytics failure: {e}")
        return empty

def _walk(path, depth=0):
    children = []
    file_count = 0
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return {"label": path.name, "type": "dir", "total_files": 0, "children": []}
    for item in entries:
        if item.name.startswith("."):
            continue
        if item.is_file():
            if item.suffix.lower() == ".pdf":
                children.append({"label": item.name, "type": "file"})
                file_count += 1
        else:
            label = PRODUCT_LABELS.get(item.name.lower(), item.name)
            sub = _walk(item, depth + 1)
            sub["label"] = label
            file_count += sub["total_files"]
            children.append(sub)
    return {"label": path.name, "type": "dir", "total_files": file_count, "children": children}


@app.get("/api/filetree")
def api_filetree(user: dict = Depends(get_current_user)):
    try:
        from backend.config import RAW_DIR
        if not RAW_DIR.exists():
            return []
        result = []
        for vendor_dir in sorted(RAW_DIR.iterdir()):
            if not vendor_dir.is_dir() or vendor_dir.name.startswith("."):
                continue
            node = _walk(vendor_dir)
            node["label"] = VENDOR_LABELS.get(vendor_dir.name.lower(), vendor_dir.name)
            node["type"] = "vendor"
            result.append(node)
        return result
    except Exception:
        return []


@app.post("/api/search")
def api_search(req: SearchRequest, user: dict = Depends(get_current_user)):
    try:
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask")
def api_ask(req: AskRequest, user: dict = Depends(get_current_user)):
    try:
        result = search(req.query, mode=req.mode, top_k=req.top_k,
                        product=req.product, version=req.version, doc_type=req.doc_type)
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        prompt = build_prompt(req.query, docs, metas, scenario=req.scenario)
        answer = generate(prompt, model=req.model)

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO query_logs(user_id, query, response, sources_used, model, mode, top_k, scenario, doc_type, product, version) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            user.get("sub"), req.query, answer,
                            json.dumps([m["source_file"] for m in metas], ensure_ascii=False),
                            req.model, req.mode, req.top_k,
                            req.scenario, req.doc_type, req.product, req.version,
                        ),
                    )
                conn.commit()
        except Exception as db_e:
            logger.error(f"Failed to log query to database: {db_e}")

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
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error in api_ask: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
def api_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
                (file.filename, str(target_path), user.get("sub")),
            )
        conn.commit()
    return {"message": "上傳成功", "filename": file.filename}


class QuizRequest(BaseModel):
    product: str = ""
    version: str = ""
    count: int = 5
    model: str = DEFAULT_LLM_MODEL


@app.post("/api/quiz/generate")
def generate_quiz(req: QuizRequest, user: dict = Depends(get_current_user)):
    import re
    query = f"{req.product} {req.version} 安裝 設定 操作 重點".strip()
    result = search(query, mode="medium", top_k=8, product=req.product, version=req.version)
    docs = result["documents"][0]
    context = "\n\n---\n\n".join(docs[:6])

    prompt = f"""根據以下技術文件，出 {req.count} 道繁體中文簡答考題，測試讀者對文件的理解。請務必使用繁體中文回答。

文件內容：
{context}

嚴格使用以下格式輸出，每題之間空一行，不要有其他說明：
Q: 問題內容
A: 標準答案"""

    raw = generate(prompt, model=req.model)
    questions = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        q = re.search(r"^Q[：:]\s*(.+)", block, re.MULTILINE)
        a = re.search(r"^A[：:]\s*([\s\S]+)", block, re.MULTILINE)
        if q and a:
            questions.append({"q": q.group(1).strip(), "a": a.group(1).strip()})
    return {"questions": questions[: req.count]}


@app.post("/api/ingest")
async def ingest_data(background_tasks: BackgroundTasks, mode: str = "medium"):
    # 加入這兩行 print，這會在終端機強制顯示
    print("\n" + "=" * 30)
    print(f"🚀 收到 Ingest 請求！模式: {mode}")
    print("=" * 30 + "\n")

    # 確保這裡呼叫的函式名稱正確 (在 ingestion.py 中定義為 ingest_chunks)
    background_tasks.add_task(ingest_chunks, mode)
    return {"message": f"索引建立中 ({mode})，請稍後查詢結果"}

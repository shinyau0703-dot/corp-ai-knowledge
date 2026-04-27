import os
import json
import jwt
import shutil
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.search import search
from backend.ollama import generate
from backend.database import get_conn
from backend.auth import verify_password, create_access_token, JWT_SECRET, ALGORITHM
from backend.config import RAW_DIR
from backend.ingestion import ingest_chunks, list_products

app = FastAPI(title="Altair Knowledge Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str

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
    product: str = ""
    version: str = ""
    doc_type: str = ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_prompt(query: str, docs: list[str], metas: list[dict]) -> str:
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
    return f"""你是 Altair 官方技術文件助理，專門回答關於 Altair 軟體（HyperWorks、HyperMesh CFD、PBS、Flux、SimLab 等）的安裝、授權與使用問題。
請只根據下方提供的文件內容回答，不要推測文件以外的資訊。
若文件內容不足，請直接說「提供的文件未涵蓋此問題，建議洽 Altair 官方支援」。
回答格式：先給精簡結論，再列出依據來源（標明文件名稱與段落）。
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


@app.post("/api/login")
def api_login(req: LoginRequest, request: Request):
    client_host = request.client.host if request.client else "unknown"
    client_ua = request.headers.get("user-agent", "unknown")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, is_active FROM users WHERE username=%s",
                (req.username,),
            )
            user = cur.fetchone()
            if not user or not user[4]:
                if user:
                    cur.execute(
                        "INSERT INTO login_logs(user_id, ip_address, user_agent, status) VALUES(%s,%s,%s,'failed')",
                        (user[0], client_host, client_ua),
                    )
                    conn.commit()
                raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

            user_id, username, password_hash, role, _ = user
            if not verify_password(req.password, password_hash):
                cur.execute(
                    "INSERT INTO login_logs(user_id, ip_address, user_agent, status) VALUES(%s,%s,%s,'failed')",
                    (user_id, client_host, client_ua),
                )
                conn.commit()
                raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

            cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user_id,))
            cur.execute(
                "INSERT INTO login_logs(user_id, ip_address, user_agent, status) VALUES(%s,%s,%s,'success')",
                (user_id, client_host, client_ua),
            )
            conn.commit()

    token = create_access_token({"sub": str(user_id), "username": username, "role": role})
    return {"access_token": token, "token_type": "bearer", "role": role, "username": username}


@app.get("/api/products")
def api_products(mode: str = "medium"):
    """Return [{product, versions:[]}] from chunk files — no auth required."""
    return list_products(mode)


@app.get("/api/admin/stats")
def get_admin_stats(authorization: str = Header(None)):
    payload = get_current_user(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="管理員限定")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM query_logs")
            total_queries = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM login_logs WHERE status='success'")
            total_logins = cur.fetchone()[0]

    return {
        "total_users": total_users,
        "total_docs": total_docs,
        "total_queries": total_queries,
        "total_logins": total_logins,
    }


@app.post("/api/search")
def api_search(req: SearchRequest, authorization: str = Header(None)):
    get_current_user(authorization)
    result = search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        product=req.product,
        version=req.version,
        doc_type=req.doc_type,
    )
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
    result = search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        product=req.product,
        version=req.version,
        doc_type=req.doc_type,
    )
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    prompt = build_prompt(req.query, docs, metas)
    answer = generate(prompt, model=req.model)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO query_logs(user_id, query, response, sources_used, model, mode, top_k) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    payload.get("sub"),
                    req.query,
                    answer,
                    json.dumps([m["source_file"] for m in metas]),
                    req.model,
                    req.mode,
                    req.top_k,
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
    if payload.get("role") not in ("editor", "admin"):
        raise HTTPException(status_code=403, detail="editor / admin 限定")

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


@app.post("/api/ingest")
def api_ingest(
    background_tasks: BackgroundTasks,
    mode: str = "medium",
    authorization: str = Header(None),
):
    payload = get_current_user(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="管理員限定")

    def _run():
        ingest_chunks(mode)

    background_tasks.add_task(_run)
    return {"message": f"索引建立中（{mode}），請稍後查詢結果"}

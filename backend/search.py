import chromadb
import logging
from chromadb.config import Settings
from backend.config import VECTOR_SMALL_DIR, VECTOR_MEDIUM_DIR
from backend.embedder import embed_texts, get_model

logger = logging.getLogger(__name__)

# 快取 ChromaDB 客戶端，避免重複初始化造成的檔案鎖定問題
_client_cache = {}

def _get_client(path: str):
    if path not in _client_cache:
        _client_cache[path] = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False)
        )
    return _client_cache[path]


def _keyword_score(text: str, tokens: list[str]) -> int:
    t = text.lower()
    return sum(1 for tok in tokens if tok.strip().lower() and tok.strip().lower() in t)


def _meta_score(meta: dict, product: str, version: str, doc_type: str) -> int:
    score = 0
    p = meta.get("product", "").lower()
    v = meta.get("version", "").lower()
    d = meta.get("doc_type", "").lower()

    if product and product.lower() in p:
        score += 8
    if version and version.lower() in v:
        score += 12
    if doc_type and doc_type.lower() in d:
        score += 6
    return score


def _passes_filter(meta: dict, product: str, version: str, doc_type: str) -> bool:
    if product and product.lower() not in meta.get("product", "").lower():
        return False
    if version and version.lower() not in meta.get("version", "").lower():
        return False
    if doc_type and doc_type.lower() not in meta.get("doc_type", "").lower():
        return False
    return True


def search(
    query: str,
    mode: str = "medium",
    top_k: int = 5,
    product: str = "",
    version: str = "",
    doc_type: str = "",
) -> dict:
    store_dir = VECTOR_SMALL_DIR if mode == "small" else VECTOR_MEDIUM_DIR
    col_name = "small_chunks" if mode == "small" else "medium_chunks"

    client = _get_client(str(store_dir))
    
    try:
        collection = client.get_collection(col_name)
    except Exception:
        logger.warning(f"集合 {col_name} 尚未建立")
        return {"documents": [[]], "metadatas": [[]], "count": 0}

    count = collection.count()
    logger.info(f"正在搜尋集合: {col_name} (總資料筆數: {count})")

    try:
        model = get_model()
    except Exception as e:
        logger.error(f"模型載入失敗: {e}")
        raise RuntimeError(f"Embedding model failed to load: {e}")

    has_filters = bool(product or version or doc_type)
    n_fetch = min(200 if has_filters else top_k * 20, count)
    if n_fetch == 0:
        return {"documents": [[]], "metadatas": [[]], "count": 0}

    query_vec = embed_texts([query])[0]
    raw = collection.query(query_embeddings=[query_vec], n_results=n_fetch)

    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    
    # 過濾符合條件的文檔
    candidates = []
    for doc, meta in zip(docs, metas):
        if has_filters and not _passes_filter(meta, product, version, doc_type):
            continue
        candidates.append((doc, meta))

    if not candidates:
        return {"documents": [[]], "metadatas": [[]], "count": 0}

    # 使用 BGE-M3 的 compute_score 進行二次重排 (Reranking)
    # 這能準確計算 Query 與每個 Doc 的語義相關性
    doc_texts = [c[0] for c in candidates]
    # 這裡調用模型的 compute_score 或使用 dense 相似度來排序
    # 為了保持效能，我們對過濾後的結果進行計分
    res = model.compute_score([[query, d] for d in doc_texts], batch_size=32)
    
    # 處理不同版本的 FlagEmbedding 可能的回傳格式 (dict 或 list)
    if isinstance(res, dict):
        # 優先取 colbert_score，否則取 scores，再不然取字典中的第一個值
        scores = res.get("colbert_score") or res.get("scores")
        if scores is None and len(res) > 0:
            scores = list(res.values())[0]
    else:
        scores = res
    
    rows = []
    for i, (doc, meta) in enumerate(candidates):
        # 最終分數 = 語義分數 + 元資料權重
        final_score = scores[i] + (_meta_score(meta, product, version, doc_type) / 20.0)
        rows.append((final_score, doc, meta))

    rows.sort(key=lambda x: x[0], reverse=True)
    rows = rows[:top_k]

    return {
        "documents": [[r[1] for r in rows]],
        "metadatas": [[r[2] for r in rows]],
    }

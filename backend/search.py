import chromadb
import logging
from chromadb.config import Settings
from backend.config import VECTOR_SMALL_DIR, VECTOR_MEDIUM_DIR, RERANK_WEIGHT_DIVISOR, EMBEDDING_BATCH_SIZE, BGE_HYBRID_WEIGHTS, SC_RATIO_THRESHOLD
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

def _check_sc_ratio(text: str, threshold: float) -> bool:
    """
    檢查文字中簡體字佔中文字符的比例是否超過閾值。
    利用 Big5 編碼測試作為啟發式判斷（繁體中文常用字多在 Big5 範圍內）。
    """
    if not text:
        return False
    
    total_cjk = 0
    sc_count = 0
    for char in text:
        # 僅針對基本中文字符範圍進行統計
        if '\u4e00' <= char <= '\u9fff':
            total_cjk += 1
            try:
                char.encode('big5')
            except UnicodeEncodeError:
                sc_count += 1
                
    if total_cjk == 0:
        return False
    return (sc_count / total_cjk) > threshold


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
    # 適度調整抓取的候選數量，100 筆對 BGE-M3 而言是效能與召回的平衡點
    n_fetch = min(100 if has_filters else top_k * 15, count)
    if n_fetch == 0:
        return {"documents": [[]], "metadatas": [[]], "count": 0}

    query_vec = embed_texts([query], is_query=True)[0]
    raw = collection.query(query_embeddings=[query_vec], n_results=n_fetch)

    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    
    # 過濾符合條件的文檔
    candidates = []
    for doc, meta in zip(docs, metas):
        if has_filters and not _passes_filter(meta, product, version, doc_type):
            continue
            
        # 檢查簡體字比例，若過高則自動排除該片段
        if _check_sc_ratio(doc, SC_RATIO_THRESHOLD):
            logger.info(f"已過濾簡體比例過高之片段: {meta.get('source_file')} (Index: {meta.get('chunk_index')})")
            continue
            
        candidates.append((doc, meta))

    if not candidates:
        return {"documents": [[]], "metadatas": [[]], "count": 0}

    # 使用 BGE-M3 的 compute_score 進行二次重排 (Reranking)
    # 這能準確計算 Query 與每個 Doc 的語義相關性
    doc_texts = [c[0] for c in candidates]
    # 這裡調用模型的 compute_score 或使用 dense 相似度來排序
    # 為了保持效能，我們對過濾後的結果進行計分
    res = model.compute_score(
        [[query, d] for d in doc_texts], 
        batch_size=EMBEDDING_BATCH_SIZE,
        weights_for_different_modes=BGE_HYBRID_WEIGHTS
    )
    
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
        final_score = scores[i] + (_meta_score(meta, product, version, doc_type) / RERANK_WEIGHT_DIVISOR)
        rows.append((final_score, doc, meta))

    rows.sort(key=lambda x: x[0], reverse=True)
    rows = rows[:top_k]

    return {
        "documents": [[r[1] for r in rows]],
        "metadatas": [[r[2] for r in rows]],
    }

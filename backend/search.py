import chromadb
from backend.config import VECTOR_SMALL_DIR, VECTOR_MEDIUM_DIR
from backend.embedder import embed_texts


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

    client = chromadb.PersistentClient(path=str(store_dir))
    collection = client.get_collection(col_name)

    has_filters = bool(product or version or doc_type)
    n_fetch = min(3000 if has_filters else top_k * 30, collection.count())

    query_vec = embed_texts([query])[0]
    raw = collection.query(query_embeddings=[query_vec], n_results=n_fetch)

    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    tokens = query.split()

    rows = []
    for doc, meta in zip(docs, metas):
        if has_filters and not _passes_filter(meta, product, version, doc_type):
            continue
        score = _keyword_score(doc, tokens) + _meta_score(meta, product, version, doc_type)
        rows.append((score, doc, meta))

    rows.sort(key=lambda x: x[0], reverse=True)
    rows = rows[:top_k]

    return {
        "documents": [[r[1] for r in rows]],
        "metadatas": [[r[2] for r in rows]],
    }

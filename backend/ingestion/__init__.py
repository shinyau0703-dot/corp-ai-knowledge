import json
from pathlib import Path
import chromadb
from backend.config import CHUNKS_MEDIUM_DIR, CHUNKS_SMALL_DIR, VECTOR_MEDIUM_DIR, VECTOR_SMALL_DIR
from backend.embedder import embed_texts


def _read_chunk_file(jf: Path) -> tuple[dict, list]:
    """Return (file_meta, chunks) from a chunk JSON.

    New format: {"product": ..., "version": ..., "source_file": ..., "chunks": [...]}
    Old format: [{"chunk_index": ..., "text": ..., ...}, ...]
    """
    with open(jf, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "chunks" in data:
        meta = {
            "product":     data.get("product", ""),
            "version":     data.get("version", ""),
            "doc_type":    data.get("doc_type", ""),
            "source_file": data.get("source_file", jf.name),
        }
        return meta, data["chunks"]

    # Old format — flat list
    return {"product": "", "version": "", "doc_type": "", "source_file": jf.name}, \
           (data if isinstance(data, list) else [])


def list_products(mode: str = "medium") -> list[dict]:
    """Return [{product, versions: [...]}] sorted alphabetically."""
    chunks_dir = CHUNKS_MEDIUM_DIR if mode == "medium" else CHUNKS_SMALL_DIR
    catalog: dict[str, set] = {}
    for jf in chunks_dir.glob("*.json"):
        try:
            meta, _ = _read_chunk_file(jf)
        except Exception:
            continue
        p, v = meta["product"], meta["version"]
        if p:
            catalog.setdefault(p, set())
            if v:
                catalog[p].add(v)
    return [
        {"product": p, "versions": sorted(catalog[p], reverse=True)}
        for p in sorted(catalog)
    ]


def ingest_chunks(mode: str = "medium") -> dict:
    """Embed chunk JSONs and write to ChromaDB. Returns stats dict."""
    if mode == "medium":
        chunks_dir, vector_dir, col_name = CHUNKS_MEDIUM_DIR, VECTOR_MEDIUM_DIR, "medium_chunks"
    else:
        chunks_dir, vector_dir, col_name = CHUNKS_SMALL_DIR, VECTOR_SMALL_DIR, "small_chunks"

    client = chromadb.PersistentClient(path=str(vector_dir))
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
    collection = client.create_collection(col_name)

    chunk_files = sorted(chunks_dir.glob("*.json"))
    all_ids, all_texts, all_metas = [], [], []

    for jf in chunk_files:
        try:
            file_meta, chunks = _read_chunk_file(jf)
        except Exception:
            continue

        for chunk in chunks:
            cid = f"{jf.stem}__{chunk['chunk_index']}"
            all_ids.append(cid)
            all_texts.append(chunk["text"])
            all_metas.append({
                "source_file": file_meta["source_file"],
                "source_path": jf.name,
                "file_type":   "pdf",
                "chunk_index": int(chunk["chunk_index"]),
                "char_count":  int(chunk.get("char_count", len(chunk["text"]))),
                "product":     file_meta["product"],
                "version":     file_meta["version"],
                "doc_type":    file_meta["doc_type"],
            })

    BATCH = 64
    for i in range(0, len(all_ids), BATCH):
        embeddings = embed_texts(all_texts[i: i + BATCH])
        collection.add(
            ids=all_ids[i: i + BATCH],
            embeddings=embeddings,
            documents=all_texts[i: i + BATCH],
            metadatas=all_metas[i: i + BATCH],
        )

    return {"mode": mode, "files": len(chunk_files), "chunks": len(all_ids)}

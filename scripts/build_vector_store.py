import json
import sys
import os
sys.path.insert(0, "/app")

import chromadb
from backend.embedder import embed_texts

CHUNKS_SMALL_DIR = "/app/data/chunks/small"
CHUNKS_MEDIUM_DIR = "/app/data/chunks/medium"
VECTOR_SMALL_DIR = "/app/data/vector_store/small"
VECTOR_MEDIUM_DIR = "/app/data/vector_store/medium"
BATCH_SIZE = 500

def get_or_create_collection(client, name):
    try:
        return client.get_collection(name)
    except:
        return client.create_collection(name)

def add_rows(collection, rows):
    total_added = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        batch_ids = [row["chunk_id"] for row in batch]
        existing = collection.get(ids=batch_ids, include=[])
        existing_ids = set(existing["ids"])
        new_rows = [row for row in batch if row["chunk_id"] not in existing_ids]
        if not new_rows:
            continue
        ids = [row["chunk_id"] for row in new_rows]
        docs = [row["text"] for row in new_rows]
        metas = [{
            "source_file": row["source_file"],
            "source_path": row["source_path"],
            "file_type": row["file_type"],
            "chunk_index": row["chunk_index"],
            "char_count": row["char_count"],
        } for row in new_rows]
        embeddings = embed_texts(docs)
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        total_added += len(ids)
    return total_added

def sync_store(chunks_dir, store_dir, collection_name):
    import pathlib
    chunks_path = pathlib.Path(chunks_dir)
    if not chunks_path.exists():
        print(f"chunks dir not found: {chunks_dir}")
        return
    client = chromadb.PersistentClient(path=store_dir)
    collection = get_or_create_collection(client, collection_name)
    total_added = 0
    for file_path in sorted(chunks_path.glob("*.json")):
        rows = json.loads(file_path.read_text(encoding="utf-8"))
        added = add_rows(collection, rows)
        print(f"{'add' if added else 'skip'} {collection_name}: {file_path.name} -> {added}")
        total_added += added
    print(f"done {collection_name}: added={total_added}, total={collection.count()}")

print("building small chunks...")
sync_store(CHUNKS_SMALL_DIR, VECTOR_SMALL_DIR, "small_chunks")
print("building medium chunks...")
sync_store(CHUNKS_MEDIUM_DIR, VECTOR_MEDIUM_DIR, "medium_chunks")
print("all done!")

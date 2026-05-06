import json
import logging
import shutil
from pathlib import Path
import chromadb
from chromadb.config import Settings
from backend.config import CHUNKS_SMALL_DIR, CHUNKS_MEDIUM_DIR, VECTOR_SMALL_DIR, VECTOR_MEDIUM_DIR, VECTOR_STORE_DIR
from backend.embedder import embed_texts, get_model

logger = logging.getLogger(__name__)

def list_products(mode: str = "medium") -> list[str]:
    """列出目前已有 chunk 的產品清單，供前端篩選使用"""
    root = CHUNKS_SMALL_DIR if mode == "small" else CHUNKS_MEDIUM_DIR
    logger.info(f"掃描路徑: {root.absolute()}")

    if not root.exists():
        logger.error("錯誤：資料夾不存在！")
        return []

    products = set()
    all_jsons = list(root.glob("**/*.json"))
    logger.info(f"找到 {len(all_jsons)} 個 JSON 檔案")

    for p in all_jsons:
        rel_parts = p.relative_to(root).parts
        # 支援多種結構：
        # 1. vendor/product/version.json -> parts[1]
        # 2. product/version.json -> parts[0]
        # 3. product.json -> p.stem
        if len(rel_parts) >= 2:
            # 如果第一層是已知廠商，取第二層當產品名
            if rel_parts[0].lower() in ["altair", "siemens-cfd"]:
                products.add(rel_parts[1])
            else:
                products.add(rel_parts[0])
        else:
            products.add(p.stem)

    return sorted(list(products))

def ingest_chunks(mode: str = "medium"):
    """讀取 chunks 目錄並建立 BGE-M3 向量索引"""
    logger.info(f"開始處理索引重建 模式: {mode}")
    # 確保模型在開始掃描檔案前已載入 GPU，避免後續在迴圈內初始化造成延遲
    get_model()

    chunk_root = CHUNKS_SMALL_DIR if mode == "small" else CHUNKS_MEDIUM_DIR
    vector_dir = VECTOR_SMALL_DIR if mode == "small" else VECTOR_MEDIUM_DIR
    col_name = "small_chunks" if mode == "small" else "medium_chunks"

    # 0. 自動清理：因為更換 BGE-M3 必須徹底清空舊向量目錄
    if vector_dir.exists():
        logger.info(f"🧹 正在清理舊的向量目錄: {vector_dir}")
        shutil.rmtree(vector_dir)
    vector_dir.mkdir(parents=True, exist_ok=True)

    # 1. 初始化 ChromaDB
    client = chromadb.PersistentClient(
        path=str(vector_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    
    collection = client.create_collection(
        name=col_name, 
        metadata={"hnsw:space": "cosine"} # BGE-M3 推薦使用 Cosine 相似度
    )

    # 2. 掃描 JSON Chunks
    logger.info(f"正在掃描目錄：{chunk_root.absolute()}")
    all_files = list(chunk_root.glob("**/*.json"))
    
    if not all_files:
        msg = f"找不到任何 JSON 檔案！請確認 {chunk_root.absolute()} 是否已有資料。"
        logger.warning(msg)
        return {"error": msg}

    logger.info(f"找到 {len(all_files)} 個檔案，開始使用 BGE-M3 建立索引...")

    total_chunks = 0
    for file_path in all_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)
            
            if not chunks_data:
                continue

            # 從 JSON 讀取 meta 與 chunks (修正原先對資料結構的讀取邏輯)
            product = chunks_data.get("product", "")
            version = chunks_data.get("version", "")
            source_file = chunks_data.get("source_file", "")
            chunks = chunks_data.get("chunks", [])

            if not chunks:
                continue

            # 將一個檔案內的 chunks 進行分批處理，避免顯存溢出
            batch_size = 8
            texts = [c["text"] for c in chunks]
            
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                all_embeddings.extend(embed_texts(batch_texts))

            # 分批寫入資料庫，提升大型檔案的處理穩定性
            for i in range(0, len(texts), batch_size):
                end_idx = i + batch_size
                batch_ids = [f"{file_path.stem}_{mode}_{j}" for j in range(i, min(end_idx, len(texts)))]
                batch_metas = []
                for j in range(i, min(end_idx, len(texts))):
                    chunk = chunks[j]
                    batch_metas.append({
                        "source_file": source_file,
                        "product": product,
                        "version": version,
                        "doc_type": chunk.get("doc_type", ""),
                        "chunk_index": j,
                        "char_count": len(chunk["text"])
                    })
                
                collection.add(
                    ids=batch_ids, 
                    embeddings=all_embeddings[i:end_idx], 
                    documents=texts[i:end_idx], 
                    metadatas=batch_metas
                )

            total_chunks += len(texts)
            print(f"   ∟ 成功索引: {len(texts)} 個區塊")
            
        except Exception as e:
            print(f"❌ 處理 {file_path.name} 時發生錯誤: {e}")
    
    print(f"--- 🏁 索引重建完成，總計處理 {len(all_files)} 個檔案，共 {total_chunks} 個區塊 ---")
    return {"files": len(all_files), "chunks": total_chunks}
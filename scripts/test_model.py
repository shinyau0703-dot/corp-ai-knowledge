import sys
import os
from pathlib import Path

# 確保能正確引用 backend 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from backend.embedder import get_model, embed_texts

def main():
    print("--- 硬體環境檢查 ---")
    print(f"CUDA 是否可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU 裝置: {torch.cuda.get_device_name(0)}")

    print("--- 正在初始化 BGE-M3 模型 ---")
    # get_model 會根據是否有 GPU 自動決定是否開啟 fp16
    model = get_model()
    
    sentences = [
        "如何安裝 HyperWorks 軟體？",
        "Altair 授權伺服器設定指南",
        "這是一個關於機器學習的測試",
        "BGE-M3 支援多種檢索模式，包含稠密與稀疏向量"
    ]

    print(f"\n1. 測試文本編碼 (Dense Embeddings):")
    embeddings = embed_texts(sentences)
    print(f"成功取得 {len(embeddings)} 個向量，每個向量維度為 {len(embeddings[0])}")

    print(f"\n2. 測試語義評分 (Reranking):")
    query = "請告訴我關於 Altair 授權設定的方法"
    
    # 模擬 search.py 中的重排邏輯
    # compute_score 會計算 query 與各個 sentence 之間的 ColBERT 相似度分數
    scores_out = model.compute_score([[query, sent] for sent in sentences], batch_size=32)
    
    if isinstance(scores_out, dict):
        scores = scores_out.get("colbert_score") or scores_out.get("scores") or list(scores_out.values())[0]
    else:
        scores = scores_out
    
    print(f"查詢字串: {query}")
    results = sorted(zip(scores, sentences), key=lambda x: x[0], reverse=True)
    
    for score, sent in results:
        print(f"  [得分: {score:.4f}] {sent}")

if __name__ == "__main__":
    main()
import os
from pathlib import Path

# Project root = the directory that contains the backend/ folder
PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data"

RAW_DIR = DATA_ROOT / "raw"
CHUNKS_DIR = DATA_ROOT / "chunks"
CHUNKS_SMALL_DIR = CHUNKS_DIR / "small"
CHUNKS_MEDIUM_DIR = CHUNKS_DIR / "medium"

VECTOR_STORE_DIR = DATA_ROOT / "vector_store"
VECTOR_SMALL_DIR = VECTOR_STORE_DIR / "small"
VECTOR_MEDIUM_DIR = VECTOR_STORE_DIR / "medium"

# AI Models Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen2.5:7b")
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

# Model Execution Settings
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))
RERANK_WEIGHT_DIVISOR = 20.0  # 元資料分數的縮放權重
SC_RATIO_THRESHOLD = 0.3  # 放寬到 30%，避免過濾掉重要的技術片段

# BGE-M3 Hybrid Search Weights: [Dense, Sparse, ColBERT]
# 增加 Sparse (索引 1) 的權重可以顯著提升關鍵字匹配能力
BGE_HYBRID_WEIGHTS = [0.4, 0.4, 0.2] 

# CORS Settings
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://0.0.0.0:3000,http://[::1]:3000").split(",")

PRODUCT_LABELS = {
    "activate-libs": "Activate Libraries",
    "connectme": "ConnectMe",
    "electronics": "Electronics", "feko": "Feko", "flux": "Flux / FluxMotor",
    "hypermesh-cfd": "HyperMesh CFD", "hyperworks": "HyperWorks",
    "cast": "Cast", "compose": "Compose", "extrude": "Extrude",
    "form": "Form", "inspire": "Inspire", "mold": "Mold", "polyfoam": "PolyFoam",
    "license": "License Management", "pbs": "PBS Professional",
    "physicsai": "PhysicsAI", "simlab": "SimLab", "studio": "Studio",
    "twin-activate": "Twin Activate", "floefd": "FLOEFD",
    "flotherm": "Flotherm", "star-ccm+": "STAR-CCM+",
}

VENDOR_LABELS = {"altair": "Altair", "siemens-cfd": "Siemens CFD"}

DEFAULT_SCENARIO_SYSTEM = {
    "general": (
        "你是 Altair 官方技術文件助理，專門回答關於 Altair 軟體（HyperWorks、HyperMesh CFD、PBS、Flux、SimLab 等）的安裝、授權與使用問題。請務必使用繁體中文回答。"
        "請只根據下方提供的文件內容回答，不要推測文件以外的資訊。"
        "若文件內容不足，請直接說「提供的文件未涵蓋此問題，建議洽 Altair 官方支援」。"
        "回答格式：先給精簡結論，再列出依據來源（標明文件名稱與段落）。"
    ),
    "engineer": (
        "你是 Altair 工程師技術支援助理，專精技術文件查詢與問題排查。"
        "請提供詳細的技術步驟、指令語法與參數說明。請務必使用繁體中文回答。"
        "若涉及錯誤訊息，請逐步分析可能原因與解決方案，並標明對應文件來源。"
        "回答格式：條列操作步驟，附上指令範例，標示相關文件段落。"
    ),
    "sales": (
        "你是 Altair 業務支援助理，協助整理產品亮點與應用場景。"
        "請以客戶視角整理重點功能、版本差異與應用優勢，語氣專業但易懂，適合對外說明使用。請務必使用繁體中文回答。"
        "聚焦在商業價值與用戶效益，避免過多底層技術細節。"
        "回答格式：先列核心亮點，再補充版本重點或差異說明。"
    ),
    "cs": (
        "你是 Altair 客服支援助理，協助快速回應客戶問題。"
        "請提供簡潔明確的解答，必要時附上操作步驟，語氣親切友善。請務必使用繁體中文回答。"
        "確保回覆內容的一致性與正確性，複雜問題可建議升級技術支援。"
        "回答格式：直接給答案，操作類問題附上步驟，結尾可加確認語句。"
    ),
    "onboarding": (
        "你是 Altair 新人培訓助理，協助新進員工熟悉產品知識與作業規範。請務必使用繁體中文回答。"
        "請用淺顯易懂的方式說明，避免過多技術術語，適時提供背景知識。"
        "幫助學習者建立完整的知識體系，循序漸進地引導理解。"
        "回答格式：先說明概念背景，再說明操作方式，附上學習建議。"
    ),
}

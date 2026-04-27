# Altair Knowledge Hub

Altair 官方技術文件 AI 問答系統，以 RAG（Retrieval-Augmented Generation）技術為核心，讓工程師透過自然語言查詢 HyperWorks、PBS、SimLab、Flux 等產品的安裝手冊與技術文件。

---

## 系統架構

```
前端 (Next.js)  →  後端 API (FastAPI)  →  PostgreSQL
                                       →  ChromaDB（本機向量索引）
                                       →  Ollama（本機 LLM）
```

---

## 環境需求

| 工具 | 版本 | 說明 |
|------|------|------|
| Python | 3.11+ | 後端 |
| Node.js | 20+ | 前端 |
| PostgreSQL | 15+ | 使用者與 log 資料庫 |
| Ollama | 最新版 | 本機 LLM 推論 |

---

## 快速啟動

### 1. clone 專案

```bash
git clone https://github.com/shinyaus0703-dot/corp-ai-knowledge.git
cd corp-ai-knowledge
```

### 2. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，填入實際值：

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=eaih_app
POSTGRES_USER=eaih_app
POSTGRES_PASSWORD=你的資料庫密碼
JWT_SECRET=你的JWT金鑰
OLLAMA_HOST=http://127.0.0.1:11434
```

### 3. 放入資料

將 `data/` 資料夾放到專案根目錄下：

```
corp-ai-knowledge/
└── data/
    ├── raw/           ← 原始 PDF
    ├── chunks/
    │   └── medium/    ← chunk JSON 檔案
    └── vector_store/  ← ChromaDB 索引（有的話直接用，沒有跑步驟 6）
```

### 4. 安裝後端套件

```bash
pip install -r requirements.txt
```

### 5. 建立資料庫

確認 PostgreSQL 已啟動，執行：

```bash
psql -U postgres -c "CREATE USER eaih_app WITH PASSWORD '你的密碼';"
psql -U postgres -c "CREATE DATABASE eaih_app OWNER eaih_app;"
psql -U eaih_app -d eaih_app -f db/init.sql
```

### 6. 建立向量索引（首次必做，或有新資料時）

```bash
python scripts/run_ingest.py
```

### 7. 啟動後端

```bash
uvicorn backend.main:app --reload --port 8000
```

### 8. 安裝並啟動前端

```bash
cd frontend
npm install
```

建立 `frontend/.env.local`：

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

啟動：

```bash
npm run dev
```

瀏覽器開啟 `http://localhost:3000`

---

## 建立第一個管理員帳號

後端啟動後執行：

```bash
python scripts/create_admin.py
```

或手動：

```bash
python -c "
from backend.auth import hash_password
print(hash_password('你想設的密碼'))
"
```

再把 hash 寫入資料庫：

```sql
INSERT INTO users(username, password_hash, role)
VALUES('admin', '上面產生的hash', 'admin');
```

---

## 日常開發

| 服務 | 指令 | 網址 |
|------|------|------|
| 後端 API | `uvicorn backend.main:app --reload --port 8000` | http://localhost:8000 |
| API 文件 | （後端啟動後自動可用） | http://localhost:8000/docs |
| 前端 | `cd frontend && npm run dev` | http://localhost:3000 |

---

## 協作開發流程

```
本機改 code → 測試 OK → git push → 通知另一位 → git pull → 繼續開發
```

---

## 專案結構

```
corp-ai-knowledge/
├── backend/
│   ├── main.py          # FastAPI 主程式
│   ├── auth.py          # JWT 驗證、bcrypt 密碼
│   ├── config.py        # 路徑設定（自動對應專案根目錄）
│   ├── database.py      # PostgreSQL 連線
│   ├── embedder.py      # SentenceTransformer 向量化
│   ├── search.py        # ChromaDB 查詢 + metadata 重排
│   ├── ollama.py        # 呼叫本機 Ollama
│   └── ingestion/
│       └── __init__.py  # chunk JSON → embed → ChromaDB
├── frontend/
│   └── app/
│       ├── page.tsx     # 問答主頁
│       └── login/page.tsx
├── scripts/
│   ├── run_ingest.py    # 建立向量索引
│   └── create_admin.py  # 建立管理員帳號
├── db/
│   └── init.sql         # PostgreSQL schema
├── data/                # ← 不進 git，各自放置
│   ├── raw/
│   ├── chunks/
│   └── vector_store/
├── requirements.txt
└── .env                 # ← 不進 git
```

---

## API 端點

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/api/health` | 無 | 健康檢查 |
| POST | `/api/login` | 無 | 登入，回傳 JWT |
| GET | `/api/products` | 無 | 產品 / 版本清單 |
| POST | `/api/search` | 登入 | 語意搜尋 |
| POST | `/api/ask` | 登入 | RAG 問答 |
| POST | `/api/upload` | editor / admin | 上傳文件 |
| GET | `/api/admin/stats` | admin | 系統統計 |
| POST | `/api/ingest` | admin | 觸發背景索引建立 |

---

## 知識庫涵蓋產品

- **PBS Professional**（2024 / 2025.1 / 2025.2 / 2026）
- **HyperWorks**（2023.1 / 2024 / 2024.1 / 2025 / 2025.1 / 2026）
- **HyperMesh CFD**（2024 / 2024.1 / 2025 / 2025.1 / 2026）
- **Flux / FluxMotor**（2024 / 2024.1 / 2025 / 2025.1）
- **ConnectMe**（2024 / 2024.1 / 2025 / 2025.1）
- **SimLab**（2024 / 2024.1 / 2025 / 2025.1 / 2026）
- **Inspire / Form / Extrude / Cast / Compose / Mold / PolyFoam**（各版）
- **Feko**（v24 / v25 / v25.1）
- **PhysicsAI**（2024 / 2025）
- **License Management System**（v15.5 / v2025 / v2026）

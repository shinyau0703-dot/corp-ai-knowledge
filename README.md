# Altair Knowledge Hub

Altair 官方技術文件 AI 問答系統，以 RAG（Retrieval-Augmented Generation）技術為核心，讓工程師透過自然語言查詢 HyperWorks、PBS、SimLab、Flux 等產品的安裝手冊與技術文件。

---

## 系統架構

```
User / Editor / Admin
        │
   [Next.js Frontend :3001]
        │ NEXT_PUBLIC_API_BASE (build-time)
        │
   [FastAPI Backend :8000]
        ├── PostgreSQL :5432  (users / login_logs / documents / query_logs)
        ├── ChromaDB (local volume)  — 向量索引
        └── Ollama (host network)   — 本地 LLM 推論
```

---

## 專案現況

### 已完成

| 模組 | 說明 |
|------|------|
| 後端 API | FastAPI：登入、搜尋、問答、上傳、管理統計、產品列表、索引觸發 |
| 前端介面 | Next.js 16：登入頁、問答主頁（產品/版本下拉選單）、管理儀表板 |
| Ingestion Pipeline | `backend/ingestion/` — 從 chunk JSON 批次嵌入、寫入 ChromaDB |
| 資料庫 Schema | PostgreSQL：users / login_logs / documents / query_logs |
| 嵌入模型 | `paraphrase-multilingual-MiniLM-L12-v2`（多語言，支援中英文） |
| 向量資料庫 | ChromaDB persistent — medium 模式 |
| 原始文件 | Altair PBS、HyperWorks、HyperMesh CFD、SimLab、Flux 等 PDF |
| Chunks | medium chunks 已切分（`data/chunks/medium/`） |
| Docker Compose | db / api / frontend / adminer 四服務 |

### 待辦

- [ ] 執行首次索引建立（`docker exec -it eaih_api python scripts/run_ingest.py`）
- [ ] small chunks 切分與索引
- [ ] 更換 `.env` 中的預設密碼與 JWT secret
- [ ] AD/LDAP 整合（計畫書 P3 階段）
- [ ] Re-ranker 精準重排（計畫書 P4 階段）

---

## 快速啟動

### 1. 設定環境變數

複製並修改 `.env`（請務必更換密碼）：

```env
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=eaih_app
POSTGRES_USER=eaih_app
POSTGRES_PASSWORD=<請修改>
JWT_SECRET=<請修改>
OLLAMA_HOST=http://host.docker.internal:11434
```

### 2. 確認資料位置

伺服器上需有以下目錄（docker-compose 掛載來源）：

```
/hdd-sda1/km-data/
├── raw/          ← 原始 PDF
├── chunks/       ← 切分後 JSON
└── vector_store/ ← ChromaDB 索引（首次執行後自動生成）
```

### 3. 啟動服務

```bash
docker compose up -d
```

| 服務 | 網址 |
|------|------|
| 前端 | http://192.168.40.155:3001 |
| API | http://192.168.40.155:8000 |
| API Docs | http://192.168.40.155:8000/docs |
| Adminer | http://192.168.40.155:8080 |

### 4. 建立向量索引（首次執行必做）

```bash
docker exec -it eaih_api python scripts/run_ingest.py
```

### 5. 建立第一個管理員帳號

```bash
docker exec -it eaih_postgres psql -U eaih_app -d eaih_app -c \
  "INSERT INTO users(username, password_hash, role) VALUES('admin', '<bcrypt_hash>', 'admin');"
```

---

## 目錄結構

```
corp-ai-knowledge/
├── backend/
│   ├── main.py          # FastAPI 主程式（所有 API endpoints）
│   ├── auth.py          # JWT 驗證、bcrypt 密碼
│   ├── config.py        # 路徑設定、Ollama host
│   ├── database.py      # PostgreSQL 連線（psycopg3）
│   ├── embedder.py      # SentenceTransformer 向量化
│   ├── search.py        # ChromaDB 查詢 + metadata 重排
│   ├── ollama.py        # 呼叫本機 Ollama 產生回答
│   └── ingestion/
│       └── __init__.py  # chunk JSON → embed → ChromaDB
├── frontend/
│   └── app/
│       ├── page.tsx     # 問答主頁（產品/版本下拉、來源顯示）
│       └── login/page.tsx
├── scripts/
│   └── run_ingest.py    # 手動觸發索引建立
├── db/
│   └── init.sql         # PostgreSQL schema
├── data/
│   ├── raw/             ← 掛載自 /hdd-sda1/km-data/raw
│   ├── chunks/medium/   ← 掛載自 /hdd-sda1/km-data/chunks
│   └── vector_store/    ← 掛載自 /hdd-sda1/km-data/vector_store
├── docker-compose.yml
├── Dockerfile.api
└── .env
```

---

## API 端點

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/api/health` | 無 | 健康檢查 |
| POST | `/api/login` | 無 | 登入，回傳 JWT |
| GET | `/api/products?mode=medium` | 無 | 產品 / 版本清單 |
| POST | `/api/search` | 登入 | 語意搜尋，回傳相關段落 |
| POST | `/api/ask` | 登入 | RAG 問答，回傳 AI 回答與來源 |
| POST | `/api/upload` | editor / admin | 上傳文件 |
| GET | `/api/admin/stats` | admin | 系統統計 |
| POST | `/api/ingest?mode=medium` | admin | 觸發背景索引建立 |

---

## 使用者角色

| 角色 | 權限 |
|------|------|
| `user` | 搜尋、問答 |
| `editor` | user 所有 + 上傳文件 |
| `admin` | editor 所有 + 系統統計 + 觸發索引建立 |

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

---

## 向量搜尋流程

1. 查詢文字 → SentenceTransformer → 向量
2. ChromaDB 餘弦相似度檢索（medium chunk，1000 chars/chunk）
3. 若指定 product / version / doc_type → metadata 過濾 + 加權重排
4. Top-K 段落組成 prompt → Ollama（qwen3:8b / 32b / 235b）
5. 回答與來源記錄至 `query_logs`

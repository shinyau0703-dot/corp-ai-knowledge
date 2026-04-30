# 勢流科技 AI 技術知識庫

> 以 RAG 技術為核心的內部問答系統，讓工程師用自然語言查詢 **Altair** 與 **Siemens CFD** 代理產品的安裝手冊與技術文件。

---

## 系統架構

```
使用者
  │
  ▼
┌─────────────────┐
│  Next.js 前端    │  :3000
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  FastAPI 後端    │  :8000
└──┬──────────┬───┘
   │          │
   ▼          ▼
┌──────────┐  ┌─────────────────────────────┐
│PostgreSQL│  │  查詢流程                    │
│使用者/log │  │                             │
└──────────┘  │  問題 → 向量化               │
              │       → ChromaDB 語意搜尋   │
              │       → Ollama 生成回答      │
              └─────────────────────────────┘
```

**資料 Pipeline**

```
PDF 文件              chunk JSON            向量索引
data/raw/  ──────▶  data/chunks/  ──────▶  data/vector_store/
                                  (run_ingest.py)
```

---

## 環境需求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 後端 API |
| Node.js | 20+ | 前端 |
| PostgreSQL | 15+ | 使用者與查詢紀錄 |
| Ollama | 最新版 | 本機 LLM 推論 |

---

## 快速啟動

**① Clone 專案**
```bash
git clone https://github.com/shinyaus0703-dot/corp-ai-knowledge.git
cd corp-ai-knowledge
```

**② 設定環境變數**
```bash
cp .env.example .env
# 編輯 .env，填入以下值：
```
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=eaih_app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
JWT_SECRET=your_jwt_secret
OLLAMA_HOST=http://127.0.0.1:11434
```

**③ 安裝後端套件**
```bash
pip install -r requirements.txt
```

**④ 建立資料庫**
```bash
psql -U postgres -c "CREATE DATABASE eaih_app;"
psql -U postgres -d eaih_app -f db/init.sql
```

**⑤ 放入原始資料並產生 chunk JSON**
```
data/raw/altair/       ← Altair PDF
data/raw/siemens-cfd/  ← Siemens CFD PDF
```
> 產生 chunk JSON 後放入 `data/chunks/medium/`

**⑥ 建立向量索引**
```bash
python scripts/data/run_ingest.py
```

**⑦ 啟動後端**
```bash
uvicorn backend.main:app --reload --port 8000
```

**⑧ 啟動前端**
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

| 服務 | 網址 |
|------|------|
| 前端 | http://localhost:3000 |
| API 文件 | http://localhost:8000/docs |

**⑨ 建立管理員帳號**
```bash
python scripts/admin/create_admin.py
```

---

## 專案結構

```
corp-ai-knowledge/
├── backend/       FastAPI 後端（API、向量搜尋、LLM）
├── frontend/      Next.js 前端
├── scripts/
│   ├── data/      向量索引相關腳本
│   ├── db/        資料庫初始化腳本
│   └── admin/     使用者管理腳本
├── db/            PostgreSQL Schema
├── data/          原始 PDF、chunk JSON、向量索引（不進 git）
└── document/      專案規劃文件
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

### Altair

| 產品 | 版本 |
|------|------|
| HyperWorks | 2023.1 / 2024 / 2024.1 / 2025 / 2025.1 / 2026 |
| HyperMesh CFD | 2024 / 2024.1 / 2025 / 2025.1 / 2026 |
| PBS Professional | 2024 / 2025.1 / 2025.2 / 2026 |
| SimLab | 2024 / 2024.1 / 2025 / 2025.1 / 2026 |
| Flux / FluxMotor | 2024 / 2024.1 / 2025 / 2025.1 |
| Inspire | 2024.1 / 2025 / 2025.1 |
| Form / Extrude / Cast / Compose / Mold / PolyFoam | 2024.1 / 2025 / 2025.1 |
| Feko | v24 / v25 / v25.1 |
| PhysicsAI | 2024 / 2025 / 2025.1 |
| ConnectMe | 2024 / 2024.1 / 2025 / 2025.1 |
| EDA | 2025.1 |
| PSIM | 2025.1 |
| Studio | 2025.1 |
| License Management System | v15.5 / v2025 / v2026 |

### Siemens CFD

| 產品 | 版本 |
|------|------|
| Simcenter Flotherm | 2020.1 / 2020.2 / 2210 |
| FLOEFD | 2020 ～ 2512（CATIA V5 / Creo / NX / Solid Edge / SC / Standalone）|
| STAR-CCM+ | 2020 ～ 2602 |

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type ProductItem = { product: string; versions: string[] };

type Source = {
  source_file: string;
  product: string;
  version: string;
  doc_type: string;
  chunk_index: number;
  char_count: number;
};

type AskResponse = {
  query: string;
  answer: string;
  model: string;
  mode: string;
  sources: Source[];
};

type AdminStats = {
  total_users: number;
  total_docs: number;
  total_queries: number;
  total_logins: number;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Home() {
  const router = useRouter();

  // Auth
  const [username, setUsername] = useState("");
  const [role, setRole] = useState("");
  const [token, setToken] = useState("");
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);

  // Product catalog
  const [catalog, setCatalog] = useState<ProductItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("");
  const [docType, setDocType] = useState("");

  // Query
  const [query, setQuery] = useState("");
  const [mode] = useState("medium");
  const [model, setModel] = useState("qwen3:8b");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");

  // Upload
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  // -------------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------------
  useEffect(() => {
    const t = localStorage.getItem("access_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    setUsername(localStorage.getItem("username") || "");
    const r = localStorage.getItem("role") || "user";
    setRole(r);

    // Fetch product catalog (no auth required)
    fetch(`${API}/api/products?mode=medium`)
      .then(res => res.json())
      .then((data: ProductItem[]) => setCatalog(data))
      .catch(console.error);

    if (r === "admin") {
      fetch(`${API}/api/admin/stats`, { headers: { Authorization: `Bearer ${t}` } })
        .then(res => res.json())
        .then(setAdminStats)
        .catch(console.error);
    }
  }, [router]);

  // Reset version when product changes
  useEffect(() => { setSelectedVersion(""); }, [selectedProduct]);

  const currentVersions = catalog.find(p => p.product === selectedProduct)?.versions ?? [];

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------
  const handleLogout = () => {
    localStorage.clear();
    router.push("/login");
  };

  const ask = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          query,
          mode,
          model,
          top_k: 5,
          product: selectedProduct,
          version: selectedVersion,
          doc_type: docType,
        }),
      });
      if (!res.ok) throw new Error(`API 錯誤：${res.status}`);
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "發生錯誤");
    } finally {
      setLoading(false);
    }
  }, [query, mode, model, selectedProduct, selectedVersion, docType, token]);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      const res = await fetch(`${API}/api/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) throw new Error();
      setUploadMsg("✓ 上傳成功");
      setUploadFile(null);
    } catch {
      setUploadMsg("✗ 上傳失敗");
    } finally {
      setUploading(false);
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Altair Knowledge Hub</h1>
          <p className="text-xs text-gray-400">官方技術文件 AI 問答系統</p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">
            <span className="font-medium text-gray-800">{username}</span>
            {role === "admin" && (
              <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">admin</span>
            )}
            {role === "editor" && (
              <span className="ml-2 text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-medium">editor</span>
            )}
          </span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-red-500 transition-colors"
          >
            登出
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        {/* Sidebar */}
        <aside className="space-y-5">
          {/* Filter panel */}
          <div className="bg-white rounded-2xl border p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">篩選條件</h2>
            <div className="space-y-4">
              {/* Product */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">產品</label>
                <select
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                  value={selectedProduct}
                  onChange={e => setSelectedProduct(e.target.value)}
                >
                  <option value="">全部產品</option>
                  {catalog.map(p => (
                    <option key={p.product} value={p.product}>{p.product}</option>
                  ))}
                </select>
              </div>

              {/* Version */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">版本</label>
                <select
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                  value={selectedVersion}
                  onChange={e => setSelectedVersion(e.target.value)}
                  disabled={!selectedProduct}
                >
                  <option value="">全部版本</option>
                  {currentVersions.map(v => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>

              {/* Doc type */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">文件類型（選填）</label>
                <input
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  value={docType}
                  onChange={e => setDocType(e.target.value)}
                  placeholder="InstallGuide、AdminGuide…"
                />
              </div>

              {/* Model */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">推論模型</label>
                <select
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                  value={model}
                  onChange={e => setModel(e.target.value)}
                >
                  <option value="qwen3:8b">qwen3:8b（快速）</option>
                  <option value="qwen3:32b">qwen3:32b（精準）</option>
                  <option value="qwen3:235b-a22b">qwen3:235b-a22b（最強）</option>
                </select>
              </div>
            </div>
          </div>

          {/* Upload panel */}
          {(role === "editor" || role === "admin") && (
            <div className="bg-white rounded-2xl border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">上傳文件</h2>
              <label className="block border-2 border-dashed border-gray-200 rounded-xl p-4 text-center cursor-pointer hover:border-blue-400 transition-colors">
                <span className="text-xs text-gray-400 block mb-1">PDF / DOCX / TXT</span>
                <span className="text-sm text-gray-600 font-medium">
                  {uploadFile ? uploadFile.name : "點擊選擇檔案"}
                </span>
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.txt"
                  onChange={e => { setUploadFile(e.target.files?.[0] || null); setUploadMsg(""); }}
                />
              </label>
              {uploadFile && (
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="mt-3 w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-xl disabled:opacity-50 transition-colors"
                >
                  {uploading ? "上傳中…" : "確認上傳"}
                </button>
              )}
              {uploadMsg && (
                <p className={`mt-2 text-sm text-center ${uploadMsg.startsWith("✓") ? "text-green-600" : "text-red-500"}`}>
                  {uploadMsg}
                </p>
              )}
            </div>
          )}
        </aside>

        {/* Main content */}
        <div className="space-y-5">
          {/* Admin dashboard */}
          {role === "admin" && adminStats && (
            <div className="bg-gray-900 rounded-2xl p-6 text-white">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">系統統計</h2>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "用戶數", value: adminStats.total_users },
                  { label: "文件數", value: adminStats.total_docs },
                  { label: "查詢數", value: adminStats.total_queries },
                  { label: "登入數", value: adminStats.total_logins },
                ].map(item => (
                  <div key={item.label} className="bg-white/10 rounded-xl p-4">
                    <div className="text-xs text-gray-400 mb-1">{item.label}</div>
                    <div className="text-2xl font-bold">{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Query box */}
          <div className="bg-white rounded-2xl border p-6 shadow-sm">
            <label className="text-sm font-semibold text-gray-700 mb-2 block">輸入問題</label>
            <textarea
              className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm min-h-28 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="例：HyperWorks 2024 如何進行 Silent Mode 安裝？"
              onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey) ask(); }}
            />
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={ask}
                disabled={loading || !query.trim()}
                className="bg-gray-900 hover:bg-gray-700 text-white px-5 py-2 rounded-xl text-sm font-semibold disabled:opacity-40 transition-colors"
              >
                {loading ? "查詢中…" : "送出查詢"}
              </button>
              <span className="text-xs text-gray-400">Ctrl + Enter 快速送出</span>
            </div>
            {error && (
              <div className="mt-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                {error}
              </div>
            )}
          </div>

          {/* Answer */}
          <div className="bg-white rounded-2xl border p-6 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700">AI 回答</h2>
              {result && (
                <span className="text-xs text-gray-400">
                  {result.model} · {result.mode}
                </span>
              )}
            </div>
            <div className="text-sm leading-7 text-gray-800 whitespace-pre-wrap min-h-20">
              {loading
                ? <span className="text-gray-400 animate-pulse">模型思考中…</span>
                : result?.answer || <span className="text-gray-300">尚未查詢</span>
              }
            </div>
          </div>

          {/* Sources */}
          {result?.sources && result.sources.length > 0 && (
            <div className="bg-white rounded-2xl border p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                參考來源 <span className="text-gray-400 font-normal">（{result.sources.length} 筆）</span>
              </h2>
              <div className="space-y-3">
                {result.sources.map((s, i) => (
                  <div key={i} className="border border-gray-100 rounded-xl p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-blue-700">
                          {s.product} {s.version}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 truncate">{s.source_file}</div>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {s.doc_type && (
                          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                            {s.doc_type}
                          </span>
                        )}
                        <span className="text-xs text-gray-400">段落 {s.chunk_index}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

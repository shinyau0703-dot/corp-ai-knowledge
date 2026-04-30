"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Section      = "qa" | "training" | "admin";
type ScenarioId   = "general" | "engineer" | "sales" | "cs";
type AdminTab     = "dashboard" | "analytics" | "logs" | "kb";
type TrainingView = "welcome" | "reading" | "quiz";

type ProductItem  = { product: string; versions: string[] };
type Source       = { source_file: string; product: string; version: string; doc_type: string; chunk_index: number; char_count: number };
type AskResponse  = { query: string; answer: string; model: string; mode: string; sources: Source[] };
type Stats        = { total_users: number; total_docs: number; total_queries: number; total_logins: number };
type LogEntry     = { id: number; username: string; query: string; model: string; mode: string; scenario: string; product: string; version: string; created_at: string | null };
type HistoryEntry = { id: string; query: string; result: AskResponse; ts: Date };
type Bookmark     = { id: string; query: string };
type SysStatus    = { db: boolean | null; ollama: boolean | null };
type QuizQ        = { q: string; a: string };
type Analytics    = {
  by_scenario: Record<string, number>;
  by_doc_type: Record<string, number>;
  by_product: { product: string; count: number }[];
  by_model: Record<string, number>;
};

const SCENARIOS: { id: ScenarioId; label: string; active: string; idle: string }[] = [
  { id: "general",  label: "一般",   active: "bg-gray-800 text-white",   idle: "text-gray-500 hover:bg-gray-100" },
  { id: "engineer", label: "工程師", active: "bg-blue-600 text-white",   idle: "text-gray-500 hover:bg-blue-50" },
  { id: "sales",    label: "Sales",  active: "bg-green-600 text-white",  idle: "text-gray-500 hover:bg-green-50" },
  { id: "cs",       label: "客服",   active: "bg-purple-600 text-white", idle: "text-gray-500 hover:bg-purple-50" },
];

const SCENARIO_LABELS: Record<string, string> = {
  general: "一般", engineer: "工程師", sales: "Sales", cs: "客服",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  altair_manual: "Altair 官方手冊",
  cfd_install:   "Siemens CFD",
  未指定:         "未指定",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function Dot({ ok }: { ok: boolean | null }) {
  return <span className={`inline-block w-2 h-2 rounded-full ${ok === null ? "bg-gray-300" : ok ? "bg-green-500" : "bg-red-500"}`} />;
}

function NavItem({ icon, label, active, onClick }: { icon: string; label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
        active ? "bg-[#0066CC] text-white shadow-sm" : "text-gray-500 hover:bg-gray-100 hover:text-gray-800"
      }`}>
      <span className="text-base">{icon}</span>
      {label}
    </button>
  );
}

function StatBar({ label, value, max, color = "bg-blue-500" }: { label: string; value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 text-xs text-gray-600 truncate shrink-0">{label}</div>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-gray-500 w-8 text-right shrink-0">{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
export default function Home() {
  const router = useRouter();

  // ── Shared
  const [section, setSection] = useState<Section>("qa");
  const [user, setUser]       = useState<{ username: string } | null>(null);
  const [token, setToken]     = useState("");
  const [catalog, setCatalog] = useState<ProductItem[]>([]);
  const [sysStatus, setSys]   = useState<SysStatus>({ db: null, ollama: null });

  // ── QA
  const [qaScenario, setQaScenario]   = useState<ScenarioId>("general");
  const [qaProduct, setQaProduct]     = useState("");
  const [qaVersion, setQaVersion]     = useState("");
  const [qaModel, setQaModel]         = useState("qwen3:8b");
  const [qaQuery, setQaQuery]         = useState("");
  const [qaLoading, setQaLoading]     = useState(false);
  const [qaResult, setQaResult]       = useState<AskResponse | null>(null);
  const [qaError, setQaError]         = useState("");
  const [qaHistory, setQaHistory]     = useState<HistoryEntry[]>([]);
  const [qaBookmarks, setQaBookmarks] = useState<Bookmark[]>([]);

  // ── Training
  const [trProduct, setTrProduct]       = useState("");
  const [trVersion, setTrVersion]       = useState("");
  const [trView, setTrView]             = useState<TrainingView>("welcome");
  const [trContent, setTrContent]       = useState<{ docs: string[]; metas: Record<string, string>[] }>({ docs: [], metas: [] });
  const [trLoading, setTrLoading]       = useState(false);
  const [trExpanded, setTrExpanded]     = useState<Set<string>>(new Set());
  const [quizQs, setQuizQs]             = useState<QuizQ[]>([]);
  const [quizIdx, setQuizIdx]           = useState(0);
  const [quizScore, setQuizScore]       = useState({ correct: 0, wrong: 0 });
  const [quizRevealed, setQuizRevealed] = useState(false);
  const [quizDone, setQuizDone]         = useState(false);
  const [quizLoading, setQuizLoading]   = useState(false);
  const [userAnswer, setUserAnswer]     = useState("");

  // ── Admin
  const [adminTab, setAdminTab]               = useState<AdminTab>("dashboard");
  const [adminStats, setAdminStats]           = useState<Stats | null>(null);
  const [adminLogs, setAdminLogs]             = useState<LogEntry[]>([]);
  const [adminAnalytics, setAdminAnalytics]   = useState<Analytics | null>(null);
  const [uploadFile, setUploadFile]           = useState<File | null>(null);
  const [uploading, setUploading]             = useState(false);
  const [uploadMsg, setUploadMsg]             = useState("");
  const [ingestMsg, setIngestMsg]             = useState("");

  // ── Init
  useEffect(() => {
    const t = localStorage.getItem("access_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    const u = localStorage.getItem("user");
    if (u) setUser(JSON.parse(u));
    fetch(`${API}/api/products?mode=medium`).then(r => r.json()).then(setCatalog).catch(console.error);
    const bm = localStorage.getItem("km_bookmarks");
    if (bm) setQaBookmarks(JSON.parse(bm));
  }, [router]);

  useEffect(() => { setQaVersion(""); }, [qaProduct]);

  useEffect(() => {
    const check = () =>
      fetch(`${API}/api/status`).then(r => r.json())
        .then(d => setSys({ db: d.db, ollama: d.ollama }))
        .catch(() => setSys({ db: false, ollama: false }));
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (section !== "admin" || !token) return;
    fetch(`${API}/api/stats`,     { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()).then(setAdminStats).catch(console.error);
    fetch(`${API}/api/logs?limit=100`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()).then(setAdminLogs).catch(console.error);
    fetch(`${API}/api/analytics`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()).then(setAdminAnalytics).catch(console.error);
  }, [section, token]);

  // ── Handlers
  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  };

  const qaAsk = useCallback(async () => {
    if (!qaQuery.trim()) return;
    setQaLoading(true); setQaError(""); setQaResult(null);
    try {
      const res = await fetch(`${API}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: qaQuery, mode: "medium", model: qaModel, scenario: qaScenario,
          top_k: 5, product: qaProduct, version: qaVersion, doc_type: "" }),
      });
      if (!res.ok) throw new Error(`API 錯誤：${res.status}`);
      const data: AskResponse = await res.json();
      setQaResult(data);
      setQaHistory(prev => [{ id: Date.now().toString(), query: qaQuery, result: data, ts: new Date() }, ...prev.slice(0, 19)]);
    } catch (err) {
      setQaError(err instanceof Error ? err.message : "發生錯誤");
    } finally { setQaLoading(false); }
  }, [qaQuery, qaModel, qaScenario, qaProduct, qaVersion, token]);

  const addBookmark = (q: string) => {
    const updated = [{ id: Date.now().toString(), query: q }, ...qaBookmarks.filter(b => b.query !== q)].slice(0, 30);
    setQaBookmarks(updated);
    localStorage.setItem("km_bookmarks", JSON.stringify(updated));
  };
  const removeBookmark = (id: string) => {
    const updated = qaBookmarks.filter(b => b.id !== id);
    setQaBookmarks(updated);
    localStorage.setItem("km_bookmarks", JSON.stringify(updated));
  };

  const loadCourse = async (product: string, version: string) => {
    setTrProduct(product); setTrVersion(version);
    setTrView("reading"); setTrLoading(true);
    setQuizQs([]); setQuizIdx(0); setQuizDone(false); setQuizRevealed(false); setUserAnswer("");
    try {
      const res = await fetch(`${API}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: `${product} ${version} 安裝 設定 操作`, mode: "medium", top_k: 8, product, version }),
      });
      const data = await res.json();
      setTrContent({ docs: data.items.map((i: Record<string, string>) => i.text), metas: data.items });
    } catch { }
    finally { setTrLoading(false); }
  };

  const startQuiz = async () => {
    setQuizLoading(true);
    try {
      const res = await fetch(`${API}/api/quiz/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ product: trProduct, version: trVersion, count: 5 }),
      });
      const data = await res.json();
      setQuizQs(data.questions || []);
      setQuizIdx(0); setQuizScore({ correct: 0, wrong: 0 });
      setQuizDone(false); setQuizRevealed(false); setUserAnswer("");
      setTrView("quiz");
    } catch { }
    finally { setQuizLoading(false); }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true); setUploadMsg("");
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      const res = await fetch(`${API}/api/upload`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      if (!res.ok) throw new Error();
      setUploadMsg("✓ 上傳成功"); setUploadFile(null);
    } catch { setUploadMsg("✗ 上傳失敗"); }
    finally { setUploading(false); }
  };

  const triggerIngest = async () => {
    setIngestMsg("建立中…");
    try {
      await fetch(`${API}/api/ingest?mode=medium`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      setIngestMsg("✓ 索引已觸發，背景執行中");
    } catch { setIngestMsg("✗ 觸發失敗"); }
  };

  const fmt = (iso: string | null) => iso ? new Date(iso).toLocaleString("zh-TW", { hour12: false }) : "—";
  const qaVersions = catalog.find(p => p.product === qaProduct)?.versions ?? [];

  // ===========================================================================
  // Render
  // ===========================================================================
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* ── Left nav ── */}
      <aside className="w-56 bg-white border-r flex flex-col shrink-0">
        <div className="px-5 py-5 border-b">
          <div className="text-[#0066CC] font-bold text-base leading-tight">勢流科技</div>
          <div className="text-[10px] text-gray-400 mt-0.5">AI 技術知識庫</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <NavItem icon="🔍" label="一般問答"  active={section === "qa"}       onClick={() => setSection("qa")} />
          <NavItem icon="📚" label="教育訓練"  active={section === "training"} onClick={() => setSection("training")} />
          <NavItem icon="⚙️" label="系統後台"  active={section === "admin"}    onClick={() => setSection("admin")} />
        </nav>
        <div className="p-4 border-t space-y-3">
          <div className="flex gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1"><Dot ok={sysStatus.db} /> DB</span>
            <span className="flex items-center gap-1"><Dot ok={sysStatus.ollama} /> LLM</span>
          </div>
          <div className="text-sm font-medium text-gray-700 truncate">{user?.username}</div>
          <button onClick={logout} className="text-xs text-gray-400 hover:text-red-500 transition-colors">登出</button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <header className="bg-white border-b px-6 py-3 shrink-0">
          <h2 className="text-sm font-semibold text-gray-800">
            {section === "qa" ? "一般問答" : section === "training" ? "教育訓練" : "系統後台"}
          </h2>
        </header>

        <div className="flex-1 overflow-auto">

          {/* ================================================================
              QA
          ================================================================ */}
          {section === "qa" && (
            <div className="flex h-full">

              {/* Filter sidebar */}
              <aside className="w-64 bg-white border-r p-4 overflow-y-auto shrink-0 space-y-5">
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">查詢場景</p>
                  <div className="grid grid-cols-2 gap-1">
                    {SCENARIOS.map(s => (
                      <button key={s.id} onClick={() => setQaScenario(s.id)}
                        className={`py-1.5 rounded-lg text-xs font-medium transition-colors ${qaScenario === s.id ? s.active : s.idle}`}>
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">篩選</p>
                  <div className="space-y-2">
                    <div>
                      <label className="text-xs text-gray-500">產品</label>
                      <select value={qaProduct} onChange={e => setQaProduct(e.target.value)}
                        className="w-full mt-1 p-1.5 border border-gray-200 rounded-lg text-xs text-gray-700 bg-white focus:outline-none">
                        <option value="">全部</option>
                        {catalog.map(p => <option key={p.product} value={p.product}>{p.product}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500">版本</label>
                      <select value={qaVersion} onChange={e => setQaVersion(e.target.value)} disabled={!qaProduct}
                        className="w-full mt-1 p-1.5 border border-gray-200 rounded-lg text-xs text-gray-700 bg-white focus:outline-none disabled:opacity-40">
                        <option value="">全部</option>
                        {qaVersions.map(v => <option key={v} value={v}>{v}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500">推論模型</label>
                      <select value={qaModel} onChange={e => setQaModel(e.target.value)}
                        className="w-full mt-1 p-1.5 border border-gray-200 rounded-lg text-xs text-gray-700 bg-white focus:outline-none">
                        <option value="qwen3:8b">qwen3:8b（快速）</option>
                        <option value="qwen3:32b">qwen3:32b（精準）</option>
                        <option value="qwen3:235b-a22b">qwen3:235b-a22b（最強）</option>
                      </select>
                    </div>
                  </div>
                </div>

                {qaHistory.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">本次紀錄</p>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {qaHistory.map(h => (
                        <button key={h.id} onClick={() => { setQaQuery(h.query); setQaResult(h.result); }}
                          className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
                          <div className="text-xs text-gray-700 truncate">{h.query}</div>
                          <div className="text-[10px] text-gray-400">{h.ts.toLocaleTimeString("zh-TW", { hour12: false, hour: "2-digit", minute: "2-digit" })}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {qaBookmarks.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">書籤</p>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {qaBookmarks.map(b => (
                        <div key={b.id} className="flex items-center gap-1">
                          <button onClick={() => setQaQuery(b.query)}
                            className="flex-1 text-left px-2 py-1 rounded-lg hover:bg-gray-50 text-xs text-gray-600 truncate">
                            ★ {b.query}
                          </button>
                          <button onClick={() => removeBookmark(b.id)} className="text-gray-300 hover:text-red-400 text-xs px-1">×</button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </aside>

              {/* QA main */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-4xl">
                <div className="bg-white rounded-2xl border p-6 shadow-sm">
                  <textarea rows={4} value={qaQuery} onChange={e => setQaQuery(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey) qaAsk(); }}
                    placeholder="例：HyperWorks 2024 如何進行 Silent Mode 安裝？"
                    className="w-full p-4 border rounded-lg text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
                  <div className="mt-3 flex items-center gap-3 flex-wrap">
                    <button onClick={qaAsk} disabled={qaLoading || !qaQuery.trim()}
                      className="bg-gray-900 hover:bg-gray-700 text-white px-5 py-2 rounded-xl text-sm font-semibold disabled:opacity-40 transition-colors">
                      {qaLoading ? "查詢中…" : "送出查詢"}
                    </button>
                    {qaQuery.trim() && (
                      <button onClick={() => addBookmark(qaQuery)}
                        className={`text-sm px-3 py-2 rounded-xl border transition-colors ${
                          qaBookmarks.some(b => b.query === qaQuery)
                            ? "text-yellow-600 border-yellow-300 bg-yellow-50"
                            : "text-gray-400 border-gray-200 hover:text-yellow-500"
                        }`}>
                        {qaBookmarks.some(b => b.query === qaQuery) ? "★ 已加書籤" : "☆ 加入書籤"}
                      </button>
                    )}
                    <span className="text-xs text-gray-400">Ctrl + Enter 送出</span>
                  </div>
                  {qaError && <div className="mt-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">{qaError}</div>}
                </div>

                <div className="bg-white rounded-2xl border p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <span className="bg-blue-100 text-black px-2 py-1 rounded text-sm font-bold">AI 回答</span>
                    {qaResult && <span className="text-xs text-gray-400">{qaResult.model}</span>}
                  </div>
                  <div className="min-h-20 text-sm leading-7 text-gray-800">
                    {qaLoading
                      ? <span className="text-gray-400 animate-pulse">模型思考中…</span>
                      : qaResult?.answer
                        ? <div className="prose prose-sm max-w-none prose-headings:text-gray-800 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded">
                            <ReactMarkdown>{qaResult.answer}</ReactMarkdown>
                          </div>
                        : <span className="text-gray-400">尚未查詢</span>}
                  </div>
                  {qaResult?.sources && qaResult.sources.length > 0 && (
                    <details className="mt-4 pt-4 border-t border-gray-100 group">
                      <summary className="text-xs font-medium text-gray-500 cursor-pointer list-none flex items-center gap-2 hover:text-blue-600">
                        <span className="group-open:rotate-90 transition-transform text-[10px]">▶</span>
                        參考來源 ({qaResult.sources.length} 筆)
                      </summary>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {qaResult.sources.map((s, i) => (
                          <div key={i} className="border border-gray-100 rounded-xl p-3 text-xs">
                            <div className="font-semibold text-blue-700">{s.product} {s.version}</div>
                            <div className="text-gray-500 truncate mt-0.5">{s.source_file}</div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================================================================
              TRAINING
          ================================================================ */}
          {section === "training" && (
            <div className="flex h-full">
              <aside className="w-64 bg-white border-r overflow-y-auto shrink-0 p-3">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide px-2 py-2">課程目錄</p>
                {catalog.map(p => (
                  <div key={p.product}>
                    <button
                      onClick={() => setTrExpanded(prev => { const s = new Set(prev); s.has(p.product) ? s.delete(p.product) : s.add(p.product); return s; })}
                      className="w-full flex items-center justify-between px-2 py-2 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors">
                      <span className="truncate">{p.product}</span>
                      <span className={`text-[10px] text-gray-400 transition-transform ${trExpanded.has(p.product) ? "rotate-90" : ""}`}>▶</span>
                    </button>
                    {trExpanded.has(p.product) && (
                      <div className="ml-3 space-y-0.5 mb-1">
                        {p.versions.map(v => (
                          <button key={v} onClick={() => loadCourse(p.product, v)}
                            className={`w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors ${
                              trProduct === p.product && trVersion === v
                                ? "bg-blue-50 text-blue-700 font-medium"
                                : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                            }`}>
                            {v}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </aside>

              <div className="flex-1 overflow-y-auto p-6">
                {trView === "welcome" && (
                  <div className="max-w-xl mx-auto text-center mt-24">
                    <div className="text-5xl mb-4">📚</div>
                    <h2 className="text-xl font-bold text-gray-800 mb-2">選擇學習主題</h2>
                    <p className="text-gray-500 text-sm">從左側目錄選擇產品與版本，開始閱讀技術文件並完成課後測驗。</p>
                  </div>
                )}

                {trView === "reading" && (
                  <div className="max-w-3xl space-y-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-xl font-bold text-gray-800">{trProduct} {trVersion}</h2>
                        <p className="text-sm text-gray-500 mt-1">閱讀以下文件內容後，可進行課後測驗</p>
                      </div>
                      <button onClick={startQuiz} disabled={quizLoading || trLoading || trContent.docs.length === 0}
                        className="bg-[#0066CC] hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-40 transition-colors">
                        {quizLoading ? "出題中…" : "📝 開始測驗"}
                      </button>
                    </div>
                    {trLoading ? (
                      <div className="text-center py-12 text-gray-400 animate-pulse">載入文件中…</div>
                    ) : trContent.docs.length === 0 ? (
                      <div className="text-center py-12 text-gray-400">查無相關文件</div>
                    ) : trContent.docs.map((doc, i) => (
                      <div key={i} className="bg-white rounded-2xl border p-6 shadow-sm">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded-full">段落 {i + 1}</span>
                          <span className="text-xs text-gray-400 truncate">{(trContent.metas[i] as Record<string, string>)?.source_file}</span>
                        </div>
                        <p className="text-sm text-gray-700 leading-7 whitespace-pre-wrap">{doc}</p>
                      </div>
                    ))}
                  </div>
                )}

                {trView === "quiz" && (
                  <div className="max-w-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-lg font-bold text-gray-800">{trProduct} {trVersion} 課後測驗</h2>
                        <p className="text-xs text-gray-500 mt-0.5">共 {quizQs.length} 題・自我評估</p>
                      </div>
                      <button onClick={() => setTrView("reading")} className="text-sm text-gray-400 hover:text-gray-700 transition-colors">← 回文件</button>
                    </div>

                    {quizDone ? (
                      <div className="bg-white rounded-2xl border p-8 text-center shadow-sm">
                        <div className="text-4xl mb-3">{quizScore.correct >= quizQs.length * 0.8 ? "🎉" : quizScore.correct >= quizQs.length * 0.6 ? "👍" : "📖"}</div>
                        <h3 className="text-xl font-bold text-gray-800 mb-1">測驗完成</h3>
                        <p className="text-gray-500 text-sm mb-6">
                          答對 <span className="text-green-600 font-bold text-lg">{quizScore.correct}</span> 題 ／
                          答錯 <span className="text-red-500 font-bold text-lg">{quizScore.wrong}</span> 題（共 {quizQs.length} 題）
                        </p>
                        <div className="flex gap-3 justify-center">
                          <button onClick={startQuiz} className="bg-[#0066CC] text-white px-5 py-2 rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors">重新測驗</button>
                          <button onClick={() => setTrView("reading")} className="border border-gray-200 text-gray-600 px-5 py-2 rounded-xl text-sm font-semibold hover:bg-gray-50 transition-colors">回顧文件</button>
                        </div>
                      </div>
                    ) : quizQs.length === 0 ? (
                      <div className="text-center py-12 text-gray-400">出題失敗，請重試</div>
                    ) : (
                      <div className="bg-white rounded-2xl border p-6 shadow-sm space-y-5">
                        <div className="flex items-center gap-3">
                          <div className="flex-1 bg-gray-100 rounded-full h-2">
                            <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${(quizIdx / quizQs.length) * 100}%` }} />
                          </div>
                          <span className="text-xs text-gray-500 shrink-0">{quizIdx + 1} / {quizQs.length}</span>
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-blue-600 uppercase mb-2">第 {quizIdx + 1} 題</p>
                          <p className="text-base font-medium text-gray-800 leading-relaxed">{quizQs[quizIdx].q}</p>
                        </div>
                        {!quizRevealed && (
                          <textarea rows={3} value={userAnswer} onChange={e => setUserAnswer(e.target.value)} placeholder="寫下你的答案…"
                            className="w-full p-3 border border-gray-200 rounded-xl text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none" />
                        )}
                        {quizRevealed && (
                          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                            <p className="text-xs font-semibold text-blue-600 mb-1">標準答案</p>
                            <p className="text-sm text-gray-800 leading-relaxed">{quizQs[quizIdx].a}</p>
                          </div>
                        )}
                        {!quizRevealed ? (
                          <button onClick={() => setQuizRevealed(true)}
                            className="w-full bg-gray-800 hover:bg-gray-700 text-white py-2.5 rounded-xl text-sm font-semibold transition-colors">
                            查看解答
                          </button>
                        ) : (
                          <div className="grid grid-cols-2 gap-3">
                            <button onClick={() => {
                              setQuizScore(p => ({ ...p, correct: p.correct + 1 }));
                              if (quizIdx + 1 >= quizQs.length) setQuizDone(true);
                              else { setQuizIdx(i => i + 1); setQuizRevealed(false); setUserAnswer(""); }
                            }} className="bg-green-600 hover:bg-green-700 text-white py-2.5 rounded-xl text-sm font-semibold transition-colors">
                              ✓ 答對了
                            </button>
                            <button onClick={() => {
                              setQuizScore(p => ({ ...p, wrong: p.wrong + 1 }));
                              if (quizIdx + 1 >= quizQs.length) setQuizDone(true);
                              else { setQuizIdx(i => i + 1); setQuizRevealed(false); setUserAnswer(""); }
                            }} className="bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 py-2.5 rounded-xl text-sm font-semibold transition-colors">
                              ✗ 繼續複習
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ================================================================
              ADMIN
          ================================================================ */}
          {section === "admin" && (
            <div className="flex flex-col h-full">

              {/* Tab bar */}
              <div className="bg-white border-b px-6 py-2 flex gap-1 shrink-0">
                {([
                  { id: "dashboard", label: "儀表板" },
                  { id: "analytics", label: "查詢分析" },
                  { id: "logs",      label: "查詢紀錄" },
                  { id: "kb",        label: "知識庫管理" },
                ] as { id: AdminTab; label: string }[]).map(t => (
                  <button key={t.id} onClick={() => setAdminTab(t.id)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${adminTab === t.id ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-800"}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto p-6">

                {/* 儀表板 */}
                {adminTab === "dashboard" && (
                  <div className="space-y-6 max-w-4xl">
                    {adminStats && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {([["使用者數", adminStats.total_users], ["文件數", adminStats.total_docs],
                          ["查詢總數", adminStats.total_queries], ["登入次數", adminStats.total_logins]] as [string, number][]).map(([l, v]) => (
                          <div key={l} className="bg-white rounded-xl border p-5 shadow-sm">
                            <div className="text-xs text-gray-500 mb-1">{l}</div>
                            <div className="text-3xl font-bold text-gray-900">{v}</div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="bg-white rounded-2xl border p-6 shadow-sm">
                      <h3 className="text-sm font-semibold text-gray-700 mb-4">服務狀態</h3>
                      <div className="grid grid-cols-2 gap-3">
                        {[{ label: "PostgreSQL 資料庫", ok: sysStatus.db }, { label: "Ollama LLM", ok: sysStatus.ollama }].map(s => (
                          <div key={s.label} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                            <span className="text-sm text-gray-700 flex items-center gap-2"><Dot ok={s.ok} />{s.label}</span>
                            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${s.ok === null ? "bg-gray-100 text-gray-400" : s.ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                              {s.ok === null ? "確認中" : s.ok ? "運行中" : "離線"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* 查詢分析 */}
                {adminTab === "analytics" && (
                  <div className="space-y-6 max-w-4xl">
                    {!adminAnalytics ? (
                      <div className="text-center py-12 text-gray-400 animate-pulse">載入中…</div>
                    ) : (
                      <div className="grid md:grid-cols-2 gap-6">
                        <div className="bg-white rounded-2xl border p-6 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-700 mb-4">查詢場景分布</h3>
                          <div className="space-y-3">
                            {(() => {
                              const max = Math.max(...Object.values(adminAnalytics.by_scenario), 1);
                              const colors: Record<string, string> = { general: "bg-gray-500", engineer: "bg-blue-500", sales: "bg-green-500", cs: "bg-purple-500" };
                              return Object.entries(adminAnalytics.by_scenario).map(([k, v]) => (
                                <StatBar key={k} label={SCENARIO_LABELS[k] ?? k} value={v} max={max} color={colors[k] ?? "bg-gray-400"} />
                              ));
                            })()}
                          </div>
                        </div>

                        <div className="bg-white rounded-2xl border p-6 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-700 mb-4">手冊類型分布</h3>
                          <div className="space-y-3">
                            {(() => {
                              const max = Math.max(...Object.values(adminAnalytics.by_doc_type), 1);
                              return Object.entries(adminAnalytics.by_doc_type).map(([k, v]) => (
                                <StatBar key={k} label={DOC_TYPE_LABELS[k] ?? k} value={v} max={max} color="bg-teal-500" />
                              ));
                            })()}
                          </div>
                        </div>

                        <div className="bg-white rounded-2xl border p-6 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-700 mb-4">常查產品 Top 10</h3>
                          {adminAnalytics.by_product.length === 0 ? (
                            <p className="text-xs text-gray-400">尚無資料</p>
                          ) : (
                            <div className="space-y-3">
                              {(() => {
                                const max = Math.max(...adminAnalytics.by_product.map(p => p.count), 1);
                                return adminAnalytics.by_product.map(p => (
                                  <StatBar key={p.product} label={p.product} value={p.count} max={max} color="bg-orange-400" />
                                ));
                              })()}
                            </div>
                          )}
                        </div>

                        <div className="bg-white rounded-2xl border p-6 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-700 mb-4">使用模型分布</h3>
                          <div className="space-y-3">
                            {(() => {
                              const max = Math.max(...Object.values(adminAnalytics.by_model), 1);
                              return Object.entries(adminAnalytics.by_model).map(([k, v]) => (
                                <StatBar key={k} label={k} value={v} max={max} color="bg-indigo-400" />
                              ));
                            })()}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 查詢紀錄 */}
                {adminTab === "logs" && (
                  <div className="bg-white rounded-2xl border p-6 shadow-sm overflow-x-auto max-w-5xl">
                    <h3 className="font-semibold text-gray-800 mb-4 text-sm">查詢紀錄（最近 100 筆）</h3>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-xs text-gray-500 text-left">
                          <th className="pb-2 pr-4">時間</th>
                          <th className="pb-2 pr-4">使用者</th>
                          <th className="pb-2 pr-4">場景</th>
                          <th className="pb-2 pr-4">產品</th>
                          <th className="pb-2 pr-4">問題</th>
                          <th className="pb-2">模型</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminLogs.map(l => (
                          <tr key={l.id} className="border-b last:border-0 hover:bg-gray-50">
                            <td className="py-2 pr-4 text-xs text-gray-400 whitespace-nowrap">{fmt(l.created_at)}</td>
                            <td className="py-2 pr-4 font-medium text-gray-700 whitespace-nowrap">{l.username}</td>
                            <td className="py-2 pr-4 text-xs text-gray-500 whitespace-nowrap">{SCENARIO_LABELS[l.scenario] ?? l.scenario}</td>
                            <td className="py-2 pr-4 text-xs text-gray-500 whitespace-nowrap">{l.product || "—"}</td>
                            <td className="py-2 pr-4 text-gray-600 max-w-xs truncate">{l.query}</td>
                            <td className="py-2 text-xs text-gray-400 whitespace-nowrap">{l.model}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* 知識庫管理 */}
                {adminTab === "kb" && (
                  <div className="grid md:grid-cols-2 gap-6 max-w-4xl">
                    <div className="bg-white rounded-2xl border p-6 shadow-sm">
                      <h3 className="text-sm font-semibold text-gray-700 mb-4">知識庫目錄</h3>
                      <div className="space-y-1 max-h-80 overflow-y-auto">
                        {catalog.map(p => (
                          <div key={p.product}>
                            <button
                              onClick={() => setTrExpanded(prev => { const s = new Set(prev); s.has(p.product) ? s.delete(p.product) : s.add(p.product); return s; })}
                              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors">
                              <span className={`text-[10px] text-gray-400 transition-transform ${trExpanded.has(p.product) ? "rotate-90" : ""}`}>▶</span>
                              <span>📁 {p.product}</span>
                              <span className="ml-auto text-xs text-gray-400">{p.versions.length} 版本</span>
                            </button>
                            {trExpanded.has(p.product) && (
                              <div className="ml-6 space-y-0.5">
                                {p.versions.map(v => (
                                  <div key={v} className="flex items-center gap-2 px-2 py-1 text-xs text-gray-500">
                                    <span>📄</span> {v}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="bg-white rounded-2xl border p-6 shadow-sm">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">上傳文件</h3>
                        <label className="block border-2 border-dashed border-gray-200 rounded-xl p-4 text-center cursor-pointer hover:border-blue-400 transition-colors">
                          <div className="text-2xl mb-1">📎</div>
                          <div className="text-xs text-gray-400 mb-1">PDF / DOCX / TXT</div>
                          <div className="text-sm text-gray-600 font-medium">{uploadFile ? uploadFile.name : "點擊選擇檔案"}</div>
                          <input type="file" className="hidden" accept=".pdf,.docx,.txt"
                            onChange={e => { setUploadFile(e.target.files?.[0] || null); setUploadMsg(""); }} />
                        </label>
                        {uploadFile && (
                          <button onClick={handleUpload} disabled={uploading}
                            className="mt-3 w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-xl disabled:opacity-50 transition-colors">
                            {uploading ? "上傳中…" : "確認上傳"}
                          </button>
                        )}
                        {uploadMsg && <p className={`mt-2 text-sm text-center ${uploadMsg.startsWith("✓") ? "text-green-600" : "text-red-500"}`}>{uploadMsg}</p>}
                      </div>

                      <div className="bg-white rounded-2xl border p-6 shadow-sm">
                        <h3 className="text-sm font-semibold text-gray-700 mb-2">重建向量索引</h3>
                        <p className="text-xs text-gray-400 mb-4">上傳新文件後需重建索引，背景執行不影響查詢</p>
                        <button onClick={triggerIngest}
                          className="w-full bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium py-2 rounded-xl transition-colors">
                          🔄 觸發重建
                        </button>
                        {ingestMsg && <p className={`mt-2 text-sm text-center ${ingestMsg.startsWith("✓") ? "text-green-600" : "text-gray-500"}`}>{ingestMsg}</p>}
                      </div>
                    </div>
                  </div>
                )}

              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

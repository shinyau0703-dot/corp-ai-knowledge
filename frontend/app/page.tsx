"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Section      = "qa" | "training" | "admin";
type AdminTab     = "dashboard" | "analytics" | "logs" | "kb";
type TrainingView = "welcome" | "reading" | "quiz";

type ProductItem  = { product: string; versions: string[] };
type Source       = { source_file: string; product: string; version: string; doc_type: string; chunk_index: number; char_count: number };
type AskResponse  = { query: string; answer: string; model: string; mode: string; sources: Source[] };
type Stats        = { total_users: number; total_docs: number; total_queries: number; total_logins: number };
type LogEntry     = { id: number; username: string; query: string; model: string; mode: string; scenario: string; product: string; version: string; created_at: string | null };
type SysStatus    = { db: boolean | null; ollama: boolean | null };
type QuizQ        = { q: string; a: string };
type Analytics    = {
  by_scenario: Record<string, number>;
  by_doc_type: Record<string, number>;
  by_product: { product: string; count: number }[];
  by_model: Record<string, number>;
};
type TreeNode     = { label: string; type: "vendor" | "dir" | "file"; total_files?: number; children?: TreeNode[] };
type ChatMessage  = {
  id: string;
  role: "user" | "ai" | "error";
  content: string;
  sources?: Source[];
  model?: string;
  ts: Date;
};

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

function FileTreeNode({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const [open, setOpen] = useState(depth === 0);
  const isFile = node.type === "file";

  if (isFile) {
    return (
      <div className="flex items-center gap-1.5 py-0.5 px-2 rounded hover:bg-gray-50 group"
           style={{ paddingLeft: `${depth * 16 + 8}px` }}>
        <span className="text-gray-300 text-xs shrink-0">📄</span>
        <span className="text-xs text-gray-500 truncate group-hover:text-gray-700">{node.label}</span>
      </div>
    );
  }

  const isVendor = node.type === "vendor";
  return (
    <div>
      <button onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-2 py-1.5 px-2 rounded-lg text-left transition-colors hover:bg-gray-50
          ${isVendor ? "font-semibold text-gray-800" : "font-medium text-gray-600"}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}>
        <span className={`text-[10px] text-gray-400 transition-transform shrink-0 ${open ? "rotate-90" : ""}`}>▶</span>
        <span className={`text-sm shrink-0 ${isVendor ? "text-base" : ""}`}>{isVendor ? "📂" : "📁"}</span>
        <span className="truncate">{node.label}</span>
        <span className="ml-auto text-xs text-gray-300 shrink-0 tabular-nums">{node.total_files}</span>
      </button>
      {open && node.children && (
        <div>
          {node.children.map((c, i) => (
            <FileTreeNode key={`${c.label}-${i}`} node={c} depth={depth + 1} />
          ))}
        </div>
      )}
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

  // ── Chat
  const [messages, setMessages]       = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput]     = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const bottomRef                     = useRef<HTMLDivElement>(null);

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
  const [adminTab, setAdminTab]             = useState<AdminTab>("dashboard");
  const [adminStats, setAdminStats]         = useState<Stats | null>(null);
  const [adminLogs, setAdminLogs]           = useState<LogEntry[]>([]);
  const [adminAnalytics, setAdminAnalytics] = useState<Analytics | null>(null);
  const [fileTree, setFileTree]             = useState<TreeNode[]>([]);
  const [uploadFile, setUploadFile]         = useState<File | null>(null);
  const [uploading, setUploading]           = useState(false);
  const [uploadMsg, setUploadMsg]           = useState("");
  const [ingestMsg, setIngestMsg]           = useState("");

  // ── Init
  useEffect(() => {
    const t = localStorage.getItem("access_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    const u = localStorage.getItem("user");
    if (u) setUser(JSON.parse(u));
    fetch(`${API}/api/products?mode=medium`).then(r => r.json()).then(setCatalog).catch(console.error);
  }, [router]);

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
    const h = { Authorization: `Bearer ${token}` };
    const safe = (url: string) => fetch(url, { headers: h }).then(r => r.ok ? r.json() : null).catch(() => null);
    safe(`${API}/api/stats`).then(d => { if (d && typeof d.total_users === "number") setAdminStats(d); });
    safe(`${API}/api/logs?limit=100`).then(d => { if (Array.isArray(d)) setAdminLogs(d); });
    safe(`${API}/api/analytics`).then(d => { if (d && typeof d.by_scenario === "object") setAdminAnalytics(d); });
    safe(`${API}/api/filetree`).then(d => { if (Array.isArray(d)) setFileTree(d); });
  }, [section, token]);

  // auto-scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  // ── Handlers
  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  };

  const chatSend = useCallback(async () => {
    if (!chatInput.trim() || chatLoading) return;
    const query = chatInput.trim();
    setChatInput("");
    setMessages(prev => [...prev, { id: Date.now().toString(), role: "user", content: query, ts: new Date() }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query, mode: "medium", model: "qwen3:8b", scenario: "general", top_k: 5, product: "", version: "", doc_type: "" }),
      });
      if (!res.ok) throw new Error(`API 錯誤：${res.status}`);
      const data: AskResponse = await res.json();
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(), role: "ai",
        content: data.answer, sources: data.sources, model: data.model, ts: new Date(),
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(), role: "error",
        content: err instanceof Error ? err.message : "發生錯誤", ts: new Date(),
      }]);
    } finally { setChatLoading(false); }
  }, [chatInput, chatLoading, token]);

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
          <NavItem icon="💬" label="一般問答"  active={section === "qa"}       onClick={() => setSection("qa")} />
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

        {/* ================================================================
            QA — Chat Interface
        ================================================================ */}
        {section === "qa" && (
          <div className="flex flex-col h-full">

            {/* Clear button bar */}
            {messages.length > 0 && (
              <div className="bg-white border-b px-5 py-2 flex justify-end shrink-0">
                <button onClick={() => setMessages([])}
                  className="text-xs text-gray-300 hover:text-red-400 transition-colors">
                  清除對話
                </button>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 select-none">
                  <div className="text-4xl mb-3">💬</div>
                  <p className="text-sm font-medium text-gray-500">有任何技術問題，直接問我</p>
                  <p className="text-xs mt-1">支援 Altair、Siemens CFD 所有產品文件</p>
                </div>
              )}

              {messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  {msg.role !== "user" && (
                    <div className="w-7 h-7 rounded-full bg-[#0066CC] text-white text-xs flex items-center justify-center shrink-0 mr-3 mt-1">AI</div>
                  )}
                  <div className={`max-w-2xl ${msg.role === "user" ? "max-w-lg" : ""}`}>
                    {msg.role === "user" && (
                      <div className="bg-gray-900 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
                        {msg.content}
                      </div>
                    )}
                    {msg.role === "ai" && (
                      <div className="bg-white border rounded-2xl rounded-tl-sm shadow-sm px-5 py-4">
                        <div className="prose prose-sm max-w-none prose-headings:text-gray-800 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded text-gray-800 leading-7">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <details className="mt-3 pt-3 border-t border-gray-100 group">
                            <summary className="text-xs font-medium text-gray-400 cursor-pointer list-none flex items-center gap-1.5 hover:text-blue-500 transition-colors">
                              <span className="group-open:rotate-90 transition-transform text-[10px]">▶</span>
                              參考來源 ({msg.sources.length} 筆)
                            </summary>
                            <div className="mt-2 grid grid-cols-2 gap-2">
                              {msg.sources.map((s, i) => (
                                <div key={i} className="border border-gray-100 rounded-lg p-2.5 text-xs bg-gray-50">
                                  <div className="font-semibold text-blue-600">{s.product} {s.version}</div>
                                  <div className="text-gray-400 truncate mt-0.5">{s.source_file}</div>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                        {msg.model && <div className="mt-2 text-[10px] text-gray-300">{msg.model}</div>}
                      </div>
                    )}
                    {msg.role === "error" && (
                      <div className="bg-red-50 border border-red-100 text-red-600 rounded-2xl rounded-tl-sm px-4 py-3 text-sm">
                        {msg.content}
                      </div>
                    )}
                    <div className={`text-[10px] text-gray-300 mt-1 ${msg.role === "user" ? "text-right" : ""}`}>
                      {msg.ts.toLocaleTimeString("zh-TW", { hour12: false, hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="w-7 h-7 rounded-full bg-[#0066CC] text-white text-xs flex items-center justify-center shrink-0 mr-3 mt-1">AI</div>
                  <div className="bg-white border rounded-2xl rounded-tl-sm shadow-sm px-5 py-4">
                    <span className="inline-flex gap-1">
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div className="bg-white border-t px-6 py-4 shrink-0">
              <div className="flex items-end gap-3 max-w-3xl mx-auto">
                <textarea
                  rows={1}
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chatSend(); } }}
                  placeholder="輸入問題… (Enter 送出，Shift+Enter 換行)"
                  className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-3 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 max-h-40 overflow-y-auto"
                  style={{ height: "auto", minHeight: "48px" }}
                  onInput={e => {
                    const el = e.currentTarget;
                    el.style.height = "auto";
                    el.style.height = Math.min(el.scrollHeight, 160) + "px";
                  }}
                />
                <button onClick={chatSend} disabled={chatLoading || !chatInput.trim()}
                  className="bg-[#0066CC] hover:bg-blue-700 text-white rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-40 transition-colors shrink-0">
                  送出
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================
            TRAINING
        ================================================================ */}
        {section === "training" && (
          <div className="flex h-full overflow-hidden">
            <aside className="w-64 bg-white border-r overflow-y-auto shrink-0">
              {(() => {
                const CFD = new Set(["Flotherm", "FLOEFD", "STAR-CCM+"]);
                const groups = [
                  { label: "Altair",       items: catalog.filter(p => !CFD.has(p.product)) },
                  { label: "Siemens CFD",  items: catalog.filter(p =>  CFD.has(p.product)) },
                ];
                const ProductRow = ({ p }: { p: ProductItem }) => (
                  <div key={p.product}>
                    <button
                      onClick={() => setTrExpanded(prev => { const s = new Set(prev); s.has(p.product) ? s.delete(p.product) : s.add(p.product); return s; })}
                      className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 text-sm text-gray-700 transition-colors">
                      <span className="truncate">{p.product}</span>
                      <span className={`text-[10px] text-gray-400 transition-transform shrink-0 ${trExpanded.has(p.product) ? "rotate-90" : ""}`}>▶</span>
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
                );
                return groups.map(g => g.items.length === 0 ? null : (
                  <div key={g.label} className="mb-2">
                    <div className="px-4 pt-4 pb-1.5 flex items-center gap-2">
                      <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{g.label}</span>
                      <div className="flex-1 border-t border-gray-100" />
                    </div>
                    <div className="px-2 space-y-0.5">
                      {g.items.map(p => <ProductRow key={p.product} p={p} />)}
                    </div>
                  </div>
                ));
              })()}
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
          <div className="flex flex-col h-full overflow-hidden">

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
                            const data = adminAnalytics.by_scenario ?? {};
                            const max = Math.max(...Object.values(data), 1);
                            const colors: Record<string, string> = { general: "bg-gray-500", engineer: "bg-blue-500", sales: "bg-green-500", cs: "bg-purple-500" };
                            return Object.entries(data).map(([k, v]) => (
                              <StatBar key={k} label={SCENARIO_LABELS[k] ?? k} value={v} max={max} color={colors[k] ?? "bg-gray-400"} />
                            ));
                          })()}
                        </div>
                      </div>

                      <div className="bg-white rounded-2xl border p-6 shadow-sm">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">手冊類型分布</h3>
                        <div className="space-y-3">
                          {(() => {
                            const data = adminAnalytics.by_doc_type ?? {};
                            const max = Math.max(...Object.values(data), 1);
                            return Object.entries(data).map(([k, v]) => (
                              <StatBar key={k} label={DOC_TYPE_LABELS[k] ?? k} value={v} max={max} color="bg-teal-500" />
                            ));
                          })()}
                        </div>
                      </div>

                      <div className="bg-white rounded-2xl border p-6 shadow-sm">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">常查產品 Top 10</h3>
                        {(adminAnalytics.by_product ?? []).length === 0 ? (
                          <p className="text-xs text-gray-400">尚無資料</p>
                        ) : (
                          <div className="space-y-3">
                            {(() => {
                              const data = adminAnalytics.by_product ?? [];
                              const max = Math.max(...data.map(p => p.count), 1);
                              return data.map(p => (
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
                            const data = adminAnalytics.by_model ?? {};
                            const max = Math.max(...Object.values(data), 1);
                            return Object.entries(data).map(([k, v]) => (
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
              {adminTab === "kb" && (() => {
                const CFD_PRODUCTS = new Set(["Flotherm", "FLOEFD", "STAR-CCM+"]);
                const altair  = catalog.filter(p => !CFD_PRODUCTS.has(p.product));
                const siemens = catalog.filter(p =>  CFD_PRODUCTS.has(p.product));
                const totalVersions = catalog.reduce((a, p) => a + p.versions.length, 0);

                const ProductCard = ({ p, accent }: { p: ProductItem; accent: string }) => (
                  <div className={`rounded-xl border p-4 hover:shadow-md transition-shadow bg-white`}>
                    <div className="flex items-start justify-between mb-3">
                      <span className="text-sm font-semibold text-gray-800 leading-tight">{p.product}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ml-2 ${accent}`}>
                        {p.versions.length}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {p.versions.map(v => (
                        <span key={v} className="text-[10px] bg-gray-50 border border-gray-200 text-gray-500 px-2 py-0.5 rounded-full">
                          {v}
                        </span>
                      ))}
                    </div>
                  </div>
                );

                return (
                  <div className="space-y-6 max-w-5xl">

                    {/* Stats strip */}
                    <div className="flex gap-4">
                      <div className="bg-white border rounded-xl px-5 py-3 flex items-center gap-3">
                        <span className="text-2xl font-bold text-gray-900">{catalog.length}</span>
                        <span className="text-xs text-gray-400 leading-tight">個<br/>產品</span>
                      </div>
                      <div className="bg-white border rounded-xl px-5 py-3 flex items-center gap-3">
                        <span className="text-2xl font-bold text-gray-900">{totalVersions}</span>
                        <span className="text-xs text-gray-400 leading-tight">個<br/>版本</span>
                      </div>
                    </div>

                    {/* File tree */}
                    <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
                      <div className="flex items-center justify-between px-6 py-4 border-b">
                        <h3 className="text-sm font-semibold text-gray-700">原始資料目錄</h3>
                        <span className="text-xs text-gray-400">
                          {fileTree.reduce((a, v) => a + (v.total_files ?? 0), 0)} 個 PDF
                        </span>
                      </div>
                      <div className="overflow-y-auto max-h-[480px] p-3">
                        {fileTree.length === 0
                          ? <p className="text-xs text-gray-400 text-center py-8">載入中…</p>
                          : fileTree.map((node, i) => <FileTreeNode key={`${node.label}-${i}`} node={node} depth={0} />)
                        }
                      </div>
                    </div>

                    {/* Upload + Ingest */}
                    <div className="grid md:grid-cols-2 gap-4">
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
                );
              })()}

            </div>
          </div>
        )}

      </div>
    </div>
  );
}

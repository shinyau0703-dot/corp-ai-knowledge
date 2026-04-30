"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "登入失敗");
      }
      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "發生錯誤");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm p-8 bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl">
        <div className="mb-8 text-center">
          <div className="text-3xl font-bold text-white tracking-tight">勢流科技</div>
          <div className="mt-1 text-sm text-gray-400">AI 技術知識庫 — 技術文件問答系統</div>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">使用者名稱</label>
            <input
              type="text"
              required
              autoComplete="username"
              autoFocus
              className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="輸入你的名稱"
              value={username}
              onChange={e => setUsername(e.target.value)}
            />
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-950/50 border border-red-800 px-4 py-3 rounded-xl">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim()}
            className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-3 transition-colors disabled:opacity-50 mt-2"
          >
            {loading ? "登入中…" : "進入系統"}
          </button>
        </form>
      </div>
    </main>
  );
}

import React from 'react';
import Link from 'next/link'; // Assuming Next.js Link for navigation

// Define a type for the user object, matching the backend role definition
interface User {
  username: string;
  role: 'user' | 'admin';
  // In a real app, you might have an 'id' for the user as well
  id: number;
}

interface SidebarProps {
  // In a real application, this user object would likely come from an authentication context
  // For this example, we'll pass it as a prop.
  user: User | null;
}

const Sidebar: React.FC<SidebarProps> = ({ user }) => {
  // Placeholder for logout function
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    window.location.href = '/login';
  };

  return (
    <nav className="flex flex-col h-full bg-gray-900 text-white p-4 shadow-lg w-64">
      <div className="flex-grow space-y-4">
        {/* Logo or App Title */}
        <div className="text-2xl font-bold text-center mb-6 text-blue-400">
          Altair Hub
        </div>

        {/* 所有人共用區（User & Admin） */}
        <nav className="chat-section space-y-1">
          <p className="text-[10px] font-semibold text-gray-500 uppercase px-3 mb-2">服務選單</p>
          <Link href="/" className="block w-full text-left py-2 px-3 rounded text-sm hover:bg-gray-800 transition-colors">
            💬 開始問答
          </Link>
          <Link href="/history" className="block w-full text-left py-2 px-3 rounded text-sm hover:bg-gray-800 transition-colors">
            📜 歷史紀錄
          </Link>
        </nav>

        {/* 管理者 aa 專屬區：只在身分為 admin 時顯示 */}
        {user?.role === 'admin' && (
          <div className="admin-zone border-t border-gray-800 mt-4 pt-4 space-y-1">
            <h3 className="text-[10px] font-semibold text-red-500 uppercase px-3 mb-2">系統管理</h3>
            <Link href="/upload" className="block w-full text-left py-2 px-3 rounded text-sm hover:bg-gray-800 transition-colors">
              📁 上傳知識庫
            </Link>
            <Link href="/users" className="block w-full text-left py-2 px-3 rounded text-sm hover:bg-gray-800 transition-colors">
              👥 帳號管理
            </Link>
          </div>
        )}
      </div>

      {/* 底部：登入/登出 */}
      <div className="bottom-menu pt-4 border-t border-gray-700">
        {user ? (
          <button onClick={handleLogout} className="w-full text-left py-2 px-3 rounded text-sm bg-red-900/30 text-red-400 hover:bg-red-900/50 transition-colors border border-red-900/50">
            登出 ({user.username})
          </button>
        ) : (
          <Link href="/login" className="block w-full text-center py-2 px-3 rounded bg-blue-600 hover:bg-blue-700 transition-colors">
            登入
          </Link>
        )}
      </div>
    </nav>
  );
};

export default Sidebar;
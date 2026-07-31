import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'

export default function NavBar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [adminMenuOpen, setAdminMenuOpen] = useState(false)

  const linkCls = (path: string) =>
    `px-3 py-1.5 rounded text-sm transition-colors ${
      location.pathname === path
        ? 'bg-blue-50 text-brand font-semibold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/upload" className="text-lg font-bold tracking-tight select-none">
            ◆ RAG<span className="text-brand">Portal</span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link to="/upload" className={linkCls('/upload')}>上传</Link>
            <Link to="/my-uploads" className={linkCls('/my-uploads')}>我的记录</Link>
            {user?.role === 'admin' && (
              <div
                className="relative"
                onMouseEnter={() => setAdminMenuOpen(true)}
                onMouseLeave={() => setAdminMenuOpen(false)}
              >
                <button className={`px-3 py-1.5 rounded text-sm ${adminMenuOpen ? 'bg-slate-100 text-slate-900' : 'text-slate-600'}`}>
                  后台 <span className="text-xs">▾</span>
                </button>
                {adminMenuOpen && (
                  <div className="absolute top-full left-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg py-1 min-w-[140px] z-50">
                    <Link to="/admin/dashboard" className="block px-3 py-2 text-sm hover:bg-slate-50">仪表盘</Link>
                    <Link to="/admin/uploads" className="block px-3 py-2 text-sm hover:bg-slate-50">上传记录</Link>
                  </div>
                )}
              </div>
            )}
          </nav>
        </div>
        <div
          className="relative"
          onMouseEnter={() => setUserMenuOpen(true)}
          onMouseLeave={() => setUserMenuOpen(false)}
        >
          {user ? (
            <>
              <button className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-slate-100 transition-colors">
                <div className="w-7 h-7 rounded-full bg-brand text-white flex items-center justify-center text-xs font-semibold">
                  {user.username[0]?.toUpperCase() || '?'}
                </div>
                <span className="text-sm text-slate-700">{user.username}</span>
                <span className="text-xs text-slate-400">▾</span>
              </button>
              {userMenuOpen && (
                <div className="absolute top-full right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg py-1 min-w-[200px] z-50">
                  <div className="px-4 py-2.5 border-b border-slate-100">
                    <div className="text-sm font-semibold text-slate-800">{user.username}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{user.organization || '—'}</div>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    退出登录
                  </button>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </header>
  )
}

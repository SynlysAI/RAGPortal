import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const loginWithPassword = useAuthStore((s) => s.loginWithPassword)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [portalUrl, setPortalUrl] = useState('')

  useEffect(() => {
    authApi.getConfig().then((c) => setPortalUrl(c.portal_url)).catch(() => {})
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await loginWithPassword(username, password)
      navigate('/upload', { replace: true })
    } catch (err: any) {
      setError(err.response?.data?.detail || '登录失败,请检查用户名密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight">
            ◆ RAG<span className="text-brand">Portal</span>
          </h1>
          <p className="text-sm text-slate-500 mt-2">AI⁴MS 知识库文档上传门户</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              placeholder="AI⁴MS 账号"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              placeholder="••••••"
              required
            />
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-2.5 rounded-md border border-red-100">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-brand hover:bg-brand-dark text-white font-semibold rounded-md transition-colors disabled:opacity-50 shadow-sm"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        {portalUrl && (
          <div className="mt-6 text-center text-sm text-slate-500">
            没有 AI⁴MS 账号?
            <a href={portalUrl} className="text-brand hover:underline ml-1 font-medium">前往门户注册</a>
          </div>
        )}
      </div>
    </div>
  )
}

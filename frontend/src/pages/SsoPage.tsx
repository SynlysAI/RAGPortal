import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken, consumeTokenFromHash, getToken } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'

export default function SsoPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('正在验证登录令牌...')

  useEffect(() => {
    consumeTokenFromHash()
    if (!getToken()) {
      setStatus('未检测到 SSO 令牌,即将跳转到登录页...')
      setTimeout(() => navigate('/login', { replace: true }), 1500)
      return
    }

    useAuthStore.getState().initialize()
      .then(() => {
        if (useAuthStore.getState().isAuthenticated) {
          navigate('/upload', { replace: true })
          return
        }
        clearToken()
        setStatus('令牌无效或已过期,即将跳转到登录页...')
        setTimeout(() => navigate('/login', { replace: true }), 2000)
      })
      .catch(() => {
        clearToken()
        setStatus('令牌无效或已过期,即将跳转到登录页...')
        setTimeout(() => navigate('/login', { replace: true }), 2000)
      })
  }, [navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center">
        <div className="text-4xl mb-4">🔄</div>
        <h2 className="text-lg font-semibold text-slate-700 mb-2">RAGPortal</h2>
        <p className="text-sm text-slate-500">{status}</p>
      </div>
    </div>
  )
}

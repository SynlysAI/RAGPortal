import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { setToken } from '@/api/client'

export default function SsoPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('正在验证登录令牌...')

  useEffect(() => {
    const hash = window.location.hash || ''
    const match = hash.match(/[#&]token=([^&]+)/)
    if (!match) {
      setStatus('未检测到 SSO 令牌,即将跳转到登录页...')
      setTimeout(() => navigate('/login', { replace: true }), 1500)
      return
    }
    const token = decodeURIComponent(match[1])
    setToken(token)

    authApi.me()
      .then(() => {
        window.history.replaceState(null, '', '/upload')
        window.location.reload()
      })
      .catch(() => {
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

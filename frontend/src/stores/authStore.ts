import { create } from 'zustand'
import { authApi, type UserInfo } from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/client'

interface AuthState {
  isInitialized: boolean
  isAuthenticated: boolean
  user: UserInfo | null
  initialize: () => Promise<void>
  loginWithPassword: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isInitialized: false,
  isAuthenticated: false,
  user: null,

  initialize: async () => {
    if (!getToken()) {
      set({ isInitialized: true, isAuthenticated: false, user: null })
      return
    }
    try {
      const user = await authApi.me()
      set({ isInitialized: true, isAuthenticated: true, user })
    } catch {
      clearToken()
      set({ isInitialized: true, isAuthenticated: false, user: null })
    }
  },

  loginWithPassword: async (username, password) => {
    const data = await authApi.login(username, password)
    setToken(data.token)
    try {
      // 自检:确认本地签发的 token 能被后端识别,密钥不对或认证服务异常时
      // 立即失败,避免登录成功却被静默弹回登录页、无任何提示。
      const user = await authApi.me()
      set({ isAuthenticated: true, user })
    } catch {
      clearToken()
      set({ isAuthenticated: false, user: null })
      throw new Error('登录成功,但认证配置异常(AUTH_SECRET 不一致或认证服务不可用),无法建立会话,请稍后重试')
    }
  },

  logout: () => {
    clearToken()
    set({ isAuthenticated: false, user: null })
  },
}))

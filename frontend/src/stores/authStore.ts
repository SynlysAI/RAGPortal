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
    set({ isAuthenticated: true, user: data.user })
  },

  logout: () => {
    clearToken()
    set({ isAuthenticated: false, user: null })
  },
}))

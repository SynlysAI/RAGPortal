import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'ai4ms_token'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function consumeTokenFromHash(): string | null {
  // 从 URL hash 中提取并持久化门户 token。
  if (typeof window === 'undefined') {
    return null
  }
  const hash = window.location.hash || ''
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  const token = params.get('token')
  if (!token) {
    return null
  }
  setToken(token)
  params.delete('token')
  const remaining = params.toString()
  const newUrl =
    window.location.pathname +
    window.location.search +
    (remaining ? `#${remaining}` : '')
  window.history.replaceState(null, '', newUrl)
  return token
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken()
      if (
        !window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/sso')
      ) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

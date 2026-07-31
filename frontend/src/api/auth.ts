import { api } from './client'

export interface UserInfo {
  user_id: string
  username: string
  role: 'admin' | 'user'
  status: string
  organization: string
}

export interface PublicConfig {
  portal_url: string
  max_size_mb: number
  allowed_file_types: string[]
}

export const authApi = {
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    const resp = await api.post('/auth/login', { username, password })
    return resp.data
  },
  async me(): Promise<UserInfo> {
    const resp = await api.get('/auth/me')
    return resp.data
  },
  async getConfig(): Promise<PublicConfig> {
    const resp = await api.get('/config')
    return resp.data
  },
}

import { api } from './client'

export const TOKEN_PERMISSIONS = [
  { key: 'knowledge-bases:list', label: '知识库列表' },
  { key: 'documents:list', label: '文档列表' },
  { key: 'documents:search', label: '文档检索' },
  { key: 'documents:read', label: '文档读取' },
  { key: 'documents:download', label: '文件下载' },
  { key: 'documents:write', label: '文档写入' },
  { key: 'documents:update', label: '文档更新' },
] as const

export interface ApiToken {
  id: number
  name: string
  token_prefix: string
  permissions: string[]
  knowledge_base_ids: string[]
  status: 'active' | 'revoked'
  created_at: string
  expires_at: string
  last_used_at: string
  revoked_at: string
}

export const apiTokensApi = {
  async list(): Promise<{ items: ApiToken[] }> {
    const response = await api.get('/api-tokens')
    return response.data
  },
  async create(name: string, permissions: string[], knowledgeBaseIds: string[], expiresAt = ''): Promise<{ token: ApiToken; secret: string }> {
    const response = await api.post('/api-tokens', {
      name,
      permissions,
      knowledge_base_ids: knowledgeBaseIds,
      expires_at: expiresAt,
    })
    return response.data
  },
  async revoke(id: number): Promise<void> {
    await api.post(`/api-tokens/${id}/revoke`)
  },
}

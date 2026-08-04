import { api } from './client'

export interface KbInfo {
  id: string
  name: string
  type: string
}

export const kbApi = {
  async list(refresh = false): Promise<KbInfo[]> {
    const resp = await api.get('/kb/list', { params: { refresh } })
    return resp.data.items
  },
}

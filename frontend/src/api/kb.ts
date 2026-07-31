import { api } from './client'

export interface KbInfo {
  id: string
  name: string
  type: string
}

export const kbApi = {
  async list(): Promise<KbInfo[]> {
    const resp = await api.get('/kb/list')
    return resp.data.items
  },
}

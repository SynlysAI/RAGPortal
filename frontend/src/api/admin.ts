import { api } from './client'
import type { UploadRecord } from './uploads'

export interface AdminListParams {
  page?: number
  page_size?: number
  uploader?: string
  kb_id?: string
  status?: string
  filename?: string
  start?: string
  end?: string
}

export const adminApi = {
  async list(params: AdminListParams): Promise<{ items: UploadRecord[]; total: number }> {
    const resp = await api.get('/admin/uploads', { params })
    return resp.data
  },
  async exportCsv(params: Omit<AdminListParams, 'page' | 'page_size'>): Promise<Blob> {
    const resp = await api.get('/admin/uploads/export', { params, responseType: 'blob' })
    return resp.data
  },
  async syncStatus(limit = 50): Promise<{ synced: number }> {
    const resp = await api.post('/admin/uploads/sync-status', null, { params: { limit } })
    return resp.data
  },
  async overview(): Promise<{ total: number; week_count: number; failed: number; active_users_7d: number }> {
    const resp = await api.get('/admin/stats/overview')
    return resp.data
  },
  async dailyTrend(days = 30): Promise<{ items: { date: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/daily-trend', { params: { days } })
    return resp.data
  },
  async topUploaders(n = 5): Promise<{ items: { user_id: string; username: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/top-uploaders', { params: { n } })
    return resp.data
  },
  async kbDistribution(): Promise<{ items: { kb_id: string; kb_name: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/kb-distribution')
    return resp.data
  },
}

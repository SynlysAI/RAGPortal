import { api } from './client'
import type { UploadRecord } from './uploads'

export interface AdminUserInfo {
  user_id: string
  username: string
  role: 'admin' | 'user'
  status: string
  organization: string
}

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

export interface BackfillResult {
  scanned: number
  created: number
  updated: number
  skipped: number
  deleted?: number
}

export interface UploaderRankItem {
  user_id: string
  username: string
  count: number
}

export interface KbRankItem {
  kb_id: string
  kb_name: string
  count: number
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
  async backfillUploads(pageSize = 100): Promise<BackfillResult> {
    const resp = await api.post('/admin/uploads/backfill', null, { params: { page_size: pageSize } })
    return resp.data
  },
  async listUsers(): Promise<AdminUserInfo[]> {
    const resp = await api.get('/admin/users')
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
  async topUploaders(n = 5): Promise<{ items: UploaderRankItem[] }> {
    const resp = await api.get('/admin/stats/top-uploaders', { params: { n } })
    return resp.data
  },
  async userKbDistribution(userId: string): Promise<{ items: KbRankItem[] }> {
    const resp = await api.get('/admin/stats/user-kb-distribution', { params: { user_id: userId } })
    return resp.data
  },
  async kbUploaders(kbId: string, n = 50): Promise<{ items: UploaderRankItem[] }> {
    const resp = await api.get('/admin/stats/kb-uploaders', { params: { kb_id: kbId, n } })
    return resp.data
  },
  async kbDistribution(): Promise<{ items: KbRankItem[] }> {
    const resp = await api.get('/admin/stats/kb-distribution')
    return resp.data
  },
}

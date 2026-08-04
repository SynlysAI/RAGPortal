import { api } from './client'

export interface KbRequestRecord {
  id: number
  requester_user_id: string
  requester_username: string
  requester_organization: string
  requested_name: string
  requested_description: string
  request_reason: string
  status: 'pending' | 'approved' | 'rejected' | 'created' | 'failed'
  reviewer_user_id: string
  reviewer_username: string
  review_reason: string
  approved_kb_id: string
  approved_kb_name: string
  create_error: string
  created_at: string
  updated_at: string
}

export interface SubmitKbRequestBody {
  requested_name: string
  requested_description: string
  request_reason: string
}

export const kbRequestApi = {
  async submit(body: SubmitKbRequestBody): Promise<KbRequestRecord> {
    const resp = await api.post('/kb-requests', body)
    return resp.data
  },
  async mine(page = 1, pageSize = 20): Promise<{ items: KbRequestRecord[]; total: number; page: number; page_size: number }> {
    const resp = await api.get('/kb-requests/mine', { params: { page, page_size: pageSize } })
    return resp.data
  },
  async list(page = 1, pageSize = 20, status = ''): Promise<{ items: KbRequestRecord[]; total: number; page: number; page_size: number }> {
    const resp = await api.get('/admin/kb-requests', { params: { page, page_size: pageSize, status } })
    return resp.data
  },
  async approve(id: number): Promise<KbRequestRecord> {
    const resp = await api.post(`/admin/kb-requests/${id}/approve`)
    return resp.data
  },
  async reject(id: number, reason = ''): Promise<KbRequestRecord> {
    const resp = await api.post(`/admin/kb-requests/${id}/reject`, { reason })
    return resp.data
  },
}

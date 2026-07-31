import { api } from './client'

export interface UploadRecord {
  id: number
  knowledge_id: string
  kb_id: string
  kb_name: string
  uploader_user_id?: string
  uploader_username?: string
  uploader_organization?: string
  file_name: string
  file_type: string
  file_size: number
  parse_status: 'pending' | 'processing' | 'success' | 'failed'
  parse_error: string
  uploaded_at: string
}

export const uploadsApi = {
  async upload(file: File, kbId: string, onProgress?: (pct: number) => void): Promise<UploadRecord> {
    const form = new FormData()
    form.append('file', file)
    form.append('kb_id', kbId)
    const resp = await api.post('/uploads', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
    return resp.data
  },
  async mine(page = 1, pageSize = 20): Promise<{ items: UploadRecord[]; page: number; page_size: number }> {
    const resp = await api.get('/uploads/mine', { params: { page, page_size: pageSize } })
    return resp.data
  },
  async get(id: number): Promise<UploadRecord> {
    const resp = await api.get(`/uploads/${id}`)
    return resp.data
  },
}

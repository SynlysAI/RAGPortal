import { create } from 'zustand'
import { uploadsApi } from '@/api/uploads'
import { filterValidFiles } from '@/utils/fileFilter'

type UploadItemStatus = 'pending' | 'uploading' | 'success' | 'failed'

export interface UploadItem {
  id: string
  file: File
  kbId: string
  uploaderUserId?: string
  progress: number
  status: UploadItemStatus
  error: string
  result?: Record<string, unknown>
}

interface UploadState {
  items: UploadItem[]
  addFiles: (files: File[], kbId: string, uploaderUserId?: string) => void
  clearCompleted: () => void
}

const MAX_CONCURRENCY = 5

export const useUploadStore = create<UploadState>((set, get) => ({
  items: [],

  addFiles: (files, kbId, uploaderUserId) => {
    const valid = filterValidFiles(Array.from(files))
    if (valid.length === 0) return
    const newItems: UploadItem[] = valid.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      kbId,
      uploaderUserId,
      progress: 0,
      status: 'pending',
      error: '',
    }))
    set({ items: [...get().items, ...newItems] })
    // 启动初始并发
    const pending = get().items.filter((it) => it.status === 'pending')
    let running = get().items.filter((it) => it.status === 'uploading').length
    for (const it of pending) {
      if (running >= MAX_CONCURRENCY) break
      startUpload(it.id, set, get)
      running++
    }
  },

  clearCompleted: () => {
    set({ items: get().items.filter((it) => it.status !== 'success' && it.status !== 'failed') })
  },
}))

async function startUpload(id: string, set: any, get: any) {
  const update = (patch: Partial<UploadItem>) =>
    set({ items: get().items.map((it: UploadItem) => (it.id === id ? { ...it, ...patch } : it)) })

  const item = get().items.find((it: UploadItem) => it.id === id)
  if (!item) return

  update({ status: 'uploading', progress: 0 })

  try {
    const result = await uploadsApi.upload(
      item.file,
      item.kbId,
      item.uploaderUserId,
      (pct) => update({ progress: pct }),
    )
    update({ status: 'success', progress: 100, result: result as any })
  } catch (err: any) {
    const msg = err.response?.data?.detail || err.message || '上传失败'
    update({ status: 'failed', error: msg })
  }

  // 启动下一条排队中的文件
  const next = get().items.find((it: UploadItem) => it.status === 'pending')
  if (next) startUpload(next.id, set, get)
}

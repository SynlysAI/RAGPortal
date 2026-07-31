import { useEffect, useState } from 'react'
import { uploadsApi, type UploadRecord } from '@/api/uploads'
import StatusBadge from '@/components/StatusBadge'
import { formatFileSize, formatTime } from '@/utils/format'

const PAGE_SIZE = 20

export default function MyUploadsPage() {
  const [items, setItems] = useState<UploadRecord[]>([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    uploadsApi.mine(page, PAGE_SIZE)
      .then((data) => setItems(data.items))
      .finally(() => setLoading(false))
  }, [page])

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">我的上传记录</h2>

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        {/* 表头 */}
        <div className="grid grid-cols-[2fr_1.4fr_0.8fr_0.9fr_1.2fr] gap-3 px-4 py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wide">
          <div>文件名</div>
          <div>知识库</div>
          <div className="text-right">大小</div>
          <div className="text-center">状态</div>
          <div className="text-right">上传时间</div>
        </div>

        {loading ? (
          <div className="px-4 py-16 text-center text-sm text-slate-500">加载中...</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-16 text-center">
            <div className="text-3xl mb-2">📭</div>
            <p className="text-sm text-slate-500">还没有上传记录</p>
            <p className="text-xs text-slate-400 mt-1">去上传页上传你的第一个文档</p>
          </div>
        ) : (
          items.map((u) => (
            <div
              key={u.id}
              className="grid grid-cols-[2fr_1.4fr_0.8fr_0.9fr_1.2fr] gap-3 px-4 py-3 border-t border-slate-100 text-sm"
            >
              <div className="truncate font-medium text-slate-800" title={u.file_name}>
                {u.file_name}
              </div>
              <div className="truncate text-slate-600">{u.kb_name}</div>
              <div className="text-right text-slate-500 tabular-nums">{formatFileSize(u.file_size)}</div>
              <div className="text-center">
                <StatusBadge status={u.parse_status} />
                {u.parse_status === 'failed' && u.parse_error && (
                  <div className="text-xs text-red-600 mt-1 max-w-[120px] truncate mx-auto" title={u.parse_error}>
                    {u.parse_error}
                  </div>
                )}
              </div>
              <div className="text-right text-slate-500 tabular-nums">{formatTime(u.uploaded_at)}</div>
            </div>
          ))
        )}
      </div>

      {/* 简易分页 */}
      {items.length > 0 && (
        <div className="flex justify-between items-center pt-1 text-xs text-slate-500">
          <span>每页 {PAGE_SIZE} 条</span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-2.5 py-1.5 border border-slate-300 rounded bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
            >
              ‹
            </button>
            <span className="px-2.5 py-1.5">{page}</span>
            <button
              disabled={items.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1.5 border border-slate-300 rounded bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

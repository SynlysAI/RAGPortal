import { useEffect, useState } from 'react'
import KbSelector from '@/components/KbSelector'
import UploadDropzone from '@/components/UploadDropzone'
import { useUploadStore } from '@/stores/uploadStore'
import { authApi } from '@/api/auth'
import { formatFileSize } from '@/utils/format'

export default function UploadPage() {
  const [kbId, setKbId] = useState('')
  const [config, setConfig] = useState<{ max_size_mb: number; allowed_file_types: string[] } | null>(null)
  const { items, addFiles, clearCompleted } = useUploadStore()

  useEffect(() => {
    authApi.getConfig().then((c) => {
      setConfig({ max_size_mb: c.max_size_mb, allowed_file_types: c.allowed_file_types })
    }).catch(() => {})
  }, [])

  const completed = items.filter((it) => it.status === 'success' || it.status === 'failed').length
  const totalProgress = items.length > 0 ? Math.round((completed / items.length) * 100) : 0

  function handleFiles(files: File[]) {
    if (!kbId) {
      alert('请先选择知识库')
      return
    }
    addFiles(files, kbId)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-700">上传到:</span>
        <KbSelector value={kbId} onChange={setKbId} />
      </div>

      {config && (
        <UploadDropzone
          onFiles={handleFiles}
          maxSizeMb={config.max_size_mb}
          allowedTypes={config.allowed_file_types}
          disabled={!kbId}
        />
      )}

      {items.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">
              本次上传 ({completed} / {items.length} 完成)
            </h3>
            <div className="flex items-center gap-4">
              <span className="text-xs text-slate-500">总进度 {totalProgress}%</span>
              {completed > 0 && (
                <button
                  onClick={clearCompleted}
                  className="text-xs text-slate-500 hover:text-slate-700 hover:underline"
                >
                  清空已完成
                </button>
              )}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
            {items.map((it) => {
              const displayName = (it.file as any).webkitRelativePath || it.file.name
              return (
                <div key={it.id} className="grid grid-cols-[24px_1fr_90px_80px] gap-3 items-center px-4 py-3">
                  {/* 状态图标 */}
                  <span className="text-sm text-center">
                    {it.status === 'success' && <span className="text-green-600">✓</span>}
                    {it.status === 'failed' && <span className="text-red-600">✗</span>}
                    {it.status === 'uploading' && <span className="text-blue-600">⏳</span>}
                    {it.status === 'pending' && <span className="text-slate-400">⌛</span>}
                  </span>

                  {/* 文件名 + 进度 */}
                  <div className="min-w-0">
                    <div className="text-sm text-slate-900 truncate" title={displayName}>
                      {displayName}
                    </div>
                    {it.status === 'uploading' && (
                      <div className="mt-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand rounded-full transition-all duration-300"
                          style={{ width: `${it.progress}%` }}
                        />
                      </div>
                    )}
                    {it.status === 'failed' && it.error && (
                      <div className="text-xs text-red-600 mt-0.5 truncate" title={it.error}>
                        {it.error}
                      </div>
                    )}
                  </div>

                  {/* 文件大小 */}
                  <span className="text-xs text-slate-500 text-right">
                    {formatFileSize(it.file.size)}
                  </span>

                  {/* 状态徽标 */}
                  <div className="text-right">
                    {it.status === 'success' && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-700">完成</span>
                    )}
                    {it.status === 'failed' && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-700">失败</span>
                    )}
                    {it.status === 'uploading' && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">{it.progress}%</span>
                    )}
                    {it.status === 'pending' && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold text-slate-500">等待中</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

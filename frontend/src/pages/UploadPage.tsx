import { useEffect, useState } from 'react'
import KbSelector from '@/components/KbSelector'
import UploadDropzone from '@/components/UploadDropzone'
import { useUploadStore } from '@/stores/uploadStore'
import { useAuthStore } from '@/stores/authStore'
import { adminApi, type AdminUserInfo } from '@/api/admin'
import { authApi } from '@/api/auth'
import { formatFileSize } from '@/utils/format'

export default function UploadPage() {
  const [kbId, setKbId] = useState('')
  const [selectedUploaderId, setSelectedUploaderId] = useState('')
  const [users, setUsers] = useState<AdminUserInfo[]>([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [usersError, setUsersError] = useState('')
  const [config, setConfig] = useState<{ max_size_mb: number; allowed_file_types: string[] } | null>(null)
  const { items, addFiles, clearCompleted } = useUploadStore()
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    authApi.getConfig().then((c) => {
      setConfig({ max_size_mb: c.max_size_mb, allowed_file_types: c.allowed_file_types })
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!isAdmin) {
      setSelectedUploaderId('')
      setUsers([])
      setUsersError('')
      return
    }
    setSelectedUploaderId(user?.user_id || '')
    setUsersLoading(true)
    setUsersError('')
    adminApi.listUsers()
      .then((items) => {
        setUsers(items.filter((item) => item.status !== 'disabled'))
      })
      .catch((err) => {
        setUsersError(err.response?.data?.detail || err.message || '用户列表加载失败')
      })
      .finally(() => setUsersLoading(false))
  }, [isAdmin, user?.user_id])

  const completed = items.filter(
    (it) => it.status === 'success' || it.status === 'failed' || it.status === 'duplicate',
  ).length
  const totalProgress = items.length > 0 ? Math.round((completed / items.length) * 100) : 0

  function handleFiles(files: File[]) {
    if (!kbId) {
      alert('请先选择知识库')
      return
    }
    const uploaderUserId =
      isAdmin && selectedUploaderId !== user?.user_id ? selectedUploaderId : undefined
    addFiles(files, kbId, uploaderUserId)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-700">上传到:</span>
          <KbSelector value={kbId} onChange={setKbId} />
        </div>
        {isAdmin && (
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-slate-700">上传者:</span>
            <select
              value={selectedUploaderId}
              onChange={(e) => setSelectedUploaderId(e.target.value)}
              disabled={usersLoading || users.length === 0}
              title={usersError || undefined}
              className="px-3 py-2 border border-slate-300 rounded-md bg-white text-sm min-w-[200px] focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent disabled:bg-slate-100 disabled:text-slate-500"
            >
              <option value={user?.user_id || ''}>
                {user?.username || '当前管理员'}
              </option>
              {users
                .filter((item) => item.user_id !== user?.user_id)
                .map((item) => (
                  <option key={item.user_id} value={item.user_id}>
                    {item.username}{item.organization ? ` - ${item.organization}` : ''}
                  </option>
                ))}
            </select>
          </div>
        )}
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
                    {it.status === 'duplicate' && <span className="text-amber-600">⧉</span>}
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
                      <span
                        title={it.error || undefined}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-700"
                      >
                        失败
                      </span>
                    )}
                    {it.status === 'duplicate' && (
                      <span
                        title={it.error || '文件已存在，已跳过重复上传'}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-700"
                      >
                        已存在
                      </span>
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

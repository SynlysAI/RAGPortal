import { useEffect, useState } from 'react'
import KbSelector from '@/components/KbSelector'
import UploadDropzone from '@/components/UploadDropzone'
import { kbRequestApi, type KbRequestRecord } from '@/api/kbRequests'
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
  const [requestModalOpen, setRequestModalOpen] = useState(false)
  const [requestSubmitting, setRequestSubmitting] = useState(false)
  const [myRequests, setMyRequests] = useState<KbRequestRecord[]>([])
  const [myRequestsLoading, setMyRequestsLoading] = useState(false)
  const [requestForm, setRequestForm] = useState({
    requested_name: '',
    requested_description: '',
    request_reason: '',
  })
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

  useEffect(() => {
    setMyRequestsLoading(true)
    kbRequestApi.mine(1, 5)
      .then((data) => setMyRequests(data.items))
      .catch(() => setMyRequests([]))
      .finally(() => setMyRequestsLoading(false))
  }, [])

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

  function openRequestModal() {
    setRequestForm({ requested_name: '', requested_description: '', request_reason: '' })
    setRequestModalOpen(true)
  }

  async function handleSubmitRequest() {
    if (!requestForm.requested_name.trim()) {
      alert('请填写知识库名称')
      return
    }
    setRequestSubmitting(true)
    try {
      await kbRequestApi.submit(requestForm)
      const data = await kbRequestApi.mine(1, 5)
      setMyRequests(data.items)
      setRequestModalOpen(false)
      alert('申请已提交，等待管理员审批')
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || '提交申请失败')
    } finally {
      setRequestSubmitting(false)
    }
  }

  function requestStatusClass(status: KbRequestRecord['status']) {
    switch (status) {
      case 'approved':
        return 'bg-blue-100 text-blue-700'
      case 'created':
        return 'bg-emerald-100 text-emerald-700'
      case 'rejected':
        return 'bg-slate-100 text-slate-600'
      case 'failed':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-amber-100 text-amber-700'
    }
  }

  function requestStatusText(status: KbRequestRecord['status']) {
    switch (status) {
      case 'approved':
        return '已通过'
      case 'created':
        return '已创建'
      case 'rejected':
        return '已驳回'
      case 'failed':
        return '创建失败'
      default:
        return '待审核'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-700">上传到:</span>
          <KbSelector value={kbId} onChange={setKbId} />
          <button
            type="button"
            onClick={openRequestModal}
            className="px-3 py-2 text-sm font-medium text-brand border border-brand/20 bg-brand/5 rounded-md hover:bg-brand/10 transition-colors"
          >
            申请新知识库
          </button>
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

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">我的知识库申请</h3>
            <p className="mt-1 text-xs text-slate-500">只提交名称、描述和申请理由，管理员通过后会在 WeKnora 手工创建知识库。</p>
          </div>
          <span className="text-xs text-slate-500">{myRequestsLoading ? '加载中...' : `${myRequests.length} 条`}</span>
        </div>
        <div className="mt-3 space-y-2">
          {myRequestsLoading ? (
            <div className="py-8 text-center text-sm text-slate-500">加载中...</div>
          ) : myRequests.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">暂无申请记录</div>
          ) : (
            myRequests.map((item) => (
              <div key={item.id} className="flex items-start justify-between gap-4 rounded-md border border-slate-200 px-3 py-2.5">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-800">{item.requested_name}</div>
                  <div className="mt-1 truncate text-xs text-slate-500" title={item.request_reason || item.requested_description || '未填写申请说明'}>
                    {item.request_reason || item.requested_description || '未填写申请说明'}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${requestStatusClass(item.status)}`}>
                    {item.status === 'approved' ? '已通过' : requestStatusText(item.status)}
                  </div>
                  {item.status === 'approved' && (
                    <div className="mt-1 text-xs text-slate-500">待管理员手工创建</div>
                  )}
                  {item.approved_kb_name && (
                    <div className="mt-1 text-xs text-slate-500">创建为: {item.approved_kb_name}</div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {requestModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-800">申请新知识库</h3>
              <button
                type="button"
                onClick={() => setRequestModalOpen(false)}
                className="text-slate-400 hover:text-slate-700"
              >
                ×
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-slate-600">知识库名称</span>
                <input
                  value={requestForm.requested_name}
                  onChange={(e) => setRequestForm({ ...requestForm, requested_name: e.target.value })}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                  placeholder="例如：高分子学术资料库"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-slate-600">知识库描述</span>
                <textarea
                  value={requestForm.requested_description}
                  onChange={(e) => setRequestForm({ ...requestForm, requested_description: e.target.value })}
                  rows={3}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                  placeholder="可选，简单说明这个知识库要放什么内容"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-slate-600">申请理由</span>
                <textarea
                  value={requestForm.request_reason}
                  onChange={(e) => setRequestForm({ ...requestForm, request_reason: e.target.value })}
                  rows={3}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                  placeholder="例如：用于整理高分子方向论文、实验记录和课程资料"
                />
              </label>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setRequestModalOpen(false)}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSubmitRequest}
                disabled={requestSubmitting}
                className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
              >
                {requestSubmitting ? '提交中...' : '提交申请'}
              </button>
            </div>
          </div>
        </div>
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

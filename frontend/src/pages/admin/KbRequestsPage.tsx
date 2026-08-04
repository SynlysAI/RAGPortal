import { useEffect, useMemo, useState } from 'react'
import { kbRequestApi, type KbRequestRecord } from '@/api/kbRequests'
import { useAuthStore } from '@/stores/authStore'
import { formatTime } from '@/utils/format'

const PAGE_SIZE = 20

const STATUS_LABELS: Record<KbRequestRecord['status'], { text: string; cls: string }> = {
  pending: { text: '待审核', cls: 'bg-amber-100 text-amber-700' },
  approved: { text: '已通过', cls: 'bg-blue-100 text-blue-700' },
  rejected: { text: '已驳回', cls: 'bg-slate-100 text-slate-600' },
  created: { text: '已创建', cls: 'bg-emerald-100 text-emerald-700' },
  failed: { text: '创建失败', cls: 'bg-red-100 text-red-700' },
}

export default function KbRequestsPage() {
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const [items, setItems] = useState<KbRequestRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [approvingId, setApprovingId] = useState<number | null>(null)
  const [rejectingItem, setRejectingItem] = useState<KbRequestRecord | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const totalPages = useMemo(() => Math.ceil(total / PAGE_SIZE), [total])

  function load() {
    setLoading(true)
    kbRequestApi.list(page, PAGE_SIZE, status)
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [page, status])

  async function handleApprove(item: KbRequestRecord) {
    if (!window.confirm(`通过知识库申请「${item.requested_name}」？通过后请在 WeKnora 手工创建知识库并选择模型。`)) {
      return
    }
    setApprovingId(item.id)
    try {
      await kbRequestApi.approve(item.id)
      load()
      alert('已通过申请，请到 WeKnora 手工创建知识库')
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || '审批失败')
    } finally {
      setApprovingId(null)
    }
  }

  async function handleReject() {
    if (!rejectingItem) return
    setApprovingId(rejectingItem.id)
    try {
      await kbRequestApi.reject(rejectingItem.id, rejectReason)
      setRejectingItem(null)
      setRejectReason('')
      load()
      alert('已驳回申请')
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || '驳回失败')
    } finally {
      setApprovingId(null)
    }
  }

  if (!isAdmin) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
        仅管理员可查看知识库申请审批页。
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-800">知识库申请审批</h2>
          <p className="mt-1 text-sm text-slate-500">普通用户只填必要信息，管理员通过后请在 WeKnora 手工创建知识库并选择 embedding 模型。</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={status}
            onChange={(e) => {
              setPage(1)
              setStatus(e.target.value)
            }}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
          >
            <option value="">全部状态</option>
            <option value="pending">待审核</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
            <option value="created">已创建</option>
            <option value="failed">创建失败</option>
          </select>
          <button
            onClick={load}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            刷新
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="grid grid-cols-[1.3fr_1fr_1.2fr_1.2fr_1fr_0.9fr] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
          <div>申请信息</div>
          <div>申请人</div>
          <div>说明</div>
          <div>状态</div>
          <div>创建状态</div>
          <div className="text-right">操作</div>
        </div>

        {loading ? (
          <div className="px-4 py-16 text-center text-sm text-slate-500">加载中...</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-16 text-center text-sm text-slate-500">没有符合条件的申请</div>
        ) : (
          items.map((item) => (
            <div key={item.id} className="grid grid-cols-[1.3fr_1fr_1.2fr_1.2fr_1fr_0.9fr] gap-3 border-t border-slate-100 px-4 py-3 text-sm">
              <div>
                <div className="font-semibold text-slate-800">{item.requested_name}</div>
                <div className="mt-1 text-xs text-slate-500">申请时间 {formatTime(item.created_at)}</div>
              </div>
              <div>
                <div className="font-medium text-slate-800">{item.requester_username}</div>
                <div className="text-xs text-slate-500">{item.requester_organization || '—'}</div>
              </div>
              <div className="truncate text-slate-600" title={item.request_reason || item.requested_description || '—'}>
                {item.request_reason || item.requested_description || '—'}
              </div>
              <div>
                <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${STATUS_LABELS[item.status].cls}`}>
                  {STATUS_LABELS[item.status].text}
                </span>
                {item.review_reason && (
                  <div className="mt-1 text-xs text-slate-500">驳回原因: {item.review_reason}</div>
                )}
              </div>
              <div>
                {item.approved_kb_name ? (
                  <div className="text-slate-700">{item.approved_kb_name}</div>
                ) : (
                  <div className="text-slate-400">待手工创建</div>
                )}
                {item.status === 'approved' && !item.approved_kb_name && (
                  <div className="mt-1 text-xs text-slate-500">完成后可直接在上传页选择新知识库</div>
                )}
                {item.create_error && (
                  <div className="mt-1 text-xs text-red-600" title={item.create_error}>
                    {item.create_error}
                  </div>
                )}
              </div>
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={() => handleApprove(item)}
                  disabled={approvingId === item.id || item.status !== 'pending'}
                  className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {approvingId === item.id ? '处理中' : '通过'}
                </button>
                <button
                  onClick={() => setRejectingItem(item)}
                  disabled={approvingId === item.id || item.status !== 'pending'}
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  驳回
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {total > 0 && (
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>共 {total.toLocaleString()} 条</span>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-slate-300 bg-white px-2.5 py-1.5 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ‹
            </button>
            <span className="px-2">{page} / {totalPages || 1}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-slate-300 bg-white px-2.5 py-1.5 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      )}

      {rejectingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-base font-semibold text-slate-800">驳回知识库申请</h3>
            <div className="mt-3 text-sm text-slate-600">
              <div className="font-medium text-slate-800">{rejectingItem.requested_name}</div>
              <div className="mt-1 text-xs text-slate-500">申请人: {rejectingItem.requester_username}</div>
            </div>
            <label className="mt-4 block">
              <span className="mb-1 block text-xs font-medium text-slate-600">驳回原因</span>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={4}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                placeholder="填写驳回说明"
              />
            </label>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setRejectingItem(null)
                  setRejectReason('')
                }}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={approvingId === rejectingItem.id}
                className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {approvingId === rejectingItem.id ? '提交中...' : '确认驳回'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

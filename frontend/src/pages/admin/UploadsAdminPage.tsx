import { useEffect, useMemo, useState } from 'react'
import { adminApi, type AdminListParams } from '@/api/admin'
import { kbApi, type KbInfo } from '@/api/kb'
import type { UploadRecord } from '@/api/uploads'
import StatusBadge from '@/components/StatusBadge'
import { useAuthStore } from '@/stores/authStore'
import { formatFileSize, formatTime } from '@/utils/format'

const PAGE_SIZE = 20

export default function UploadsAdminPage() {
  const [items, setItems] = useState<UploadRecord[]>([])
  const [total, setTotal] = useState(0)
  const [kbs, setKbs] = useState<KbInfo[]>([])
  const [users, setUsers] = useState<{ user_id: string; organization: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [backfilling, setBackfilling] = useState(false)
  const isAdmin = useAuthStore((state) => state.user?.role === 'admin')
  const [filters, setFilters] = useState<AdminListParams>({
    page: 1,
    page_size: PAGE_SIZE,
    uploader: '',
    kb_id: '',
    status: '',
    filename: '',
    start: '',
    end: '',
  })

  useEffect(() => {
    kbApi.list().then(setKbs).catch(() => {})
  }, [])

  useEffect(() => {
    adminApi.listUsers()
      .then((items) => {
        setUsers(items.map((item) => ({ user_id: item.user_id, organization: item.organization })))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    adminApi.list(filters)
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .finally(() => setLoading(false))
  }, [filters])

  const organizationByUserId = useMemo(() => {
    return new Map(users.map((item) => [item.user_id, item.organization]))
  }, [users])

  function update<K extends keyof AdminListParams>(key: K, value: AdminListParams[K]) {
    setFilters({ ...filters, [key]: value, page: 1 })
  }

  async function handleExport() {
    const blob = await adminApi.exportCsv(filters)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `uploads_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleSync() {
    const r = await adminApi.syncStatus(50)
    alert(`已同步 ${r.synced} 条记录`)
    setFilters({ ...filters })
  }

  async function handleBackfill() {
    if (!window.confirm('将从 WeKnora 扫描历史知识并回写到本地记录。缺失上传者会标记为“系统上传 / 来源未知”。是否继续?')) {
      return
    }
    setBackfilling(true)
    try {
      const r = await adminApi.backfillUploads(100)
      alert(`历史回写完成: 扫描 ${r.scanned} 条, 新增 ${r.created} 条, 更新 ${r.updated} 条, 标记上游已删除 ${r.deleted || 0} 条, 跳过 ${r.skipped} 条`)
      setFilters({ ...filters, page: 1 })
    } finally {
      setBackfilling(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-slate-800">全部上传记录</h2>
          {!isAdmin && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
              只读预览
            </span>
          )}
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleBackfill}
              disabled={backfilling}
              className="text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5 border border-slate-300 rounded-md bg-white hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {backfilling ? '回写中...' : '历史回写'}
            </button>
            <button
              onClick={handleSync}
              className="text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5 border border-slate-300 rounded-md bg-white hover:bg-slate-50 transition-colors"
            >
              ↻ 刷新状态
            </button>
          </div>
        )}
      </div>

      {/* 筛选条 */}
      <div className="bg-white border border-slate-200 rounded-lg p-3 grid grid-cols-6 gap-2 text-xs">
        <input
          placeholder="上传者(用户名)"
          value={filters.uploader || ''}
          onChange={(e) => update('uploader', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-brand"
        />
        <select
          value={filters.kb_id || ''}
          onChange={(e) => update('kb_id', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-brand"
        >
          <option value="">全部 KB</option>
          {kbs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
        </select>
        <select
          value={filters.status || ''}
          onChange={(e) => update('status', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-brand"
        >
          <option value="">全部状态</option>
          <option value="pending">等待中</option>
          <option value="processing">处理中</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
          <option value="deleted">上游已删除</option>
        </select>
        <input
          type="date"
          value={filters.start || ''}
          onChange={(e) => update('start', e.target.value ? e.target.value + 'T00:00:00' : '')}
          className="border border-slate-300 rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-brand"
        />
        <input
          type="date"
          value={filters.end || ''}
          onChange={(e) => update('end', e.target.value ? e.target.value + 'T23:59:59' : '')}
          className="border border-slate-300 rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-brand"
        />
        <input
          placeholder="文件名搜索"
          value={filters.filename || ''}
          onChange={(e) => update('filename', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-brand"
        />
      </div>

      {isAdmin && (
        <div className="flex justify-end">
          <button
            onClick={handleExport}
            className="bg-brand hover:bg-brand-dark text-white text-sm font-semibold px-4 py-2 rounded-md transition-colors shadow-sm"
          >
            ⬇ 导出 CSV
          </button>
        </div>
      )}

      {/* 表格 */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[1.2fr_1.5fr_1.2fr_0.8fr_0.8fr_1fr] gap-3 px-4 py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wide">
          <div>上传者</div>
          <div>文件名</div>
          <div>知识库</div>
          <div className="text-right">大小</div>
          <div className="text-center">状态</div>
          <div className="text-right">上传时间</div>
        </div>

        {loading ? (
          <div className="px-4 py-16 text-center text-sm text-slate-500">加载中...</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-16 text-center text-sm text-slate-500">没有符合条件的记录</div>
        ) : (
          items.map((u) => (
            <div
              key={u.id}
              className="grid grid-cols-[1.2fr_1.5fr_1.2fr_0.8fr_0.8fr_1fr] gap-3 px-4 py-3 border-t border-slate-100 text-sm"
            >
              <div>
                <div className="font-semibold text-slate-800">{u.uploader_username}</div>
                <div className="text-xs text-slate-500">
                  {u.uploader_organization || organizationByUserId.get(u.uploader_user_id || '') || '—'}
                </div>
              </div>
              <div className="truncate" title={u.file_name}>{u.file_name}</div>
              <div className="truncate text-slate-600">{u.kb_name}</div>
              <div className="text-right text-slate-500 tabular-nums">{formatFileSize(u.file_size)}</div>
              <div className="text-center">
                <StatusBadge status={u.parse_status} tooltip={u.parse_error} />
              </div>
              <div className="text-right text-slate-500 tabular-nums">{formatTime(u.uploaded_at)}</div>
            </div>
          ))
        )}
      </div>

      {/* 分页 */}
      {total > 0 && (
        <div className="flex justify-between items-center pt-1 text-xs text-slate-500">
          <span>共 {total.toLocaleString()} 条</span>
          <div className="flex gap-1">
            <button
              disabled={(filters.page || 1) <= 1}
              onClick={() => setFilters({ ...filters, page: (filters.page || 1) - 1 })}
              className="px-2.5 py-1.5 border border-slate-300 rounded bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50"
            >
              ‹
            </button>
            <span className="px-2.5 py-1.5">{filters.page || 1} / {totalPages || 1}</span>
            <button
              disabled={(filters.page || 1) >= totalPages}
              onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })}
              className="px-2.5 py-1.5 border border-slate-300 rounded bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

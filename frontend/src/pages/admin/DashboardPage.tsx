import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { AlertCircle, Database, FileText, ListOrdered, RefreshCw, TrendingUp, Users, X } from 'lucide-react'
import { adminApi, type KbRankItem, type UploaderRankItem } from '@/api/admin'

interface Overview {
  total: number
  week_count: number
  failed: number
  active_users_7d: number
}

interface TrendItem {
  date: string
  count: number
}

interface TopUploader {
  user_id: string
  username: string
  count: number
}

interface KbDistribution {
  kb_id: string
  kb_name: string
  count: number
}

interface KpiCardProps {
  label: string
  value: number
  hint: string
  tone: 'blue' | 'green' | 'red' | 'violet'
  icon: ReactNode
}

const TONE_STYLES = {
  blue: {
    icon: 'bg-blue-50 text-blue-600',
    accent: 'bg-blue-500',
    text: 'text-blue-600',
  },
  green: {
    icon: 'bg-emerald-50 text-emerald-600',
    accent: 'bg-emerald-500',
    text: 'text-emerald-600',
  },
  red: {
    icon: 'bg-red-50 text-red-600',
    accent: 'bg-red-500',
    text: 'text-red-600',
  },
  violet: {
    icon: 'bg-violet-50 text-violet-600',
    accent: 'bg-violet-500',
    text: 'text-violet-600',
  },
}

const DONUT_COLORS = ['#1677ff', '#22c55e', '#8b5cf6', '#f97316', '#14b8a6', '#64748b']

type DrawerKind = 'uploaders' | 'user-kbs' | 'kb-uploaders'

interface DrawerState {
  kind: DrawerKind
  title: string
  subtitle: string
}

interface DrawerRankItem {
  id: string
  name: string
  count: number
}

function rankBadgeClass(index: number) {
  const classes = [
    'bg-amber-100 text-amber-700',
    'bg-blue-100 text-blue-700',
    'bg-violet-100 text-violet-700',
  ]
  return classes[index] || 'bg-slate-100 text-slate-500'
}

function KpiCard({ label, value, hint, tone, icon }: KpiCardProps) {
  const styles = TONE_STYLES[tone]

  return (
    <section className="relative overflow-hidden rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <div className={`absolute inset-x-0 top-0 h-0.5 ${styles.accent}`} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-slate-500">{label}</div>
          <div className={`mt-3 text-3xl font-semibold tracking-normal ${tone === 'red' ? styles.text : 'text-slate-900'}`}>
            {value.toLocaleString()}
          </div>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${styles.icon}`}>
          {icon}
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${styles.accent}`} />
        {hint}
      </div>
    </section>
  )
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) {
    return null
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-slate-700">{label}</div>
      <div className="text-blue-600">上传量：{payload[0].value}</div>
    </div>
  )
}

function DonutTooltip({ active, payload }: any) {
  if (!active || !payload?.length) {
    return null
  }
  const item = payload[0]

  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-slate-700">{item.name}</div>
      <div className="text-blue-600">上传量：{item.value}</div>
    </div>
  )
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <div className="flex h-full min-h-[220px] items-center justify-center text-sm text-slate-400">
      {text}
    </div>
  )
}

function RankRows({
  items,
  loading,
  emptyText,
  onItemClick,
}: {
  items: DrawerRankItem[]
  loading?: boolean
  emptyText: string
  onItemClick?: (item: DrawerRankItem) => void
}) {
  const maxCount = Math.max(...items.map((item) => item.count), 1)

  if (loading) {
    return <div className="py-16 text-center text-sm text-slate-400">加载排行数据中...</div>
  }

  if (items.length === 0) {
    return <div className="py-16 text-center text-sm text-slate-400">{emptyText}</div>
  }

  return (
    <div className="space-y-4">
      {items.map((item, index) => {
        const width = Math.round((item.count / maxCount) * 100)
        const content = (
          <>
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${rankBadgeClass(index)}`}>
              {index + 1}
            </span>
            <div className="min-w-0">
              <div className="mb-2 flex items-center justify-between gap-3">
                <span className="truncate text-sm font-medium text-slate-700" title={item.name}>
                  {item.name || '未命名'}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-blue-500" style={{ width: `${width}%` }} />
              </div>
            </div>
            <span className="text-sm font-semibold tabular-nums text-slate-900">
              {item.count.toLocaleString()}
            </span>
          </>
        )

        if (onItemClick) {
          return (
            <button
              type="button"
              key={item.id || item.name}
              onClick={() => onItemClick(item)}
              className="grid w-full grid-cols-[34px_1fr_auto] items-center gap-3 rounded-md py-1 text-left transition-colors hover:bg-slate-50"
            >
              {content}
            </button>
          )
        }

        return (
          <div key={item.id || item.name} className="grid grid-cols-[34px_1fr_auto] items-center gap-3">
            {content}
          </div>
        )
      })}
    </div>
  )
}

function RankingDrawer({
  state,
  items,
  loading,
  error,
  onClose,
  onItemClick,
}: {
  state: DrawerState | null
  items: DrawerRankItem[]
  loading: boolean
  error: string
  onClose: () => void
  onItemClick?: (item: DrawerRankItem) => void
}) {
  if (!state) {
    return null
  }

  return (
    <div className="fixed inset-0 z-[100]">
      <button
        type="button"
        aria-label="关闭排行抽屉遮罩"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/25"
      />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[520px] flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">{state.title}</h3>
            <p className="mt-1 text-sm text-slate-500">{state.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : (
            <RankRows
              items={items}
              loading={loading}
              emptyText="暂无排行数据"
              onItemClick={onItemClick}
            />
          )}
        </div>
      </aside>
    </div>
  )
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [trend, setTrend] = useState<TrendItem[]>([])
  const [top, setTop] = useState<TopUploader[]>([])
  const [kbs, setKbs] = useState<KbDistribution[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [drawer, setDrawer] = useState<DrawerState | null>(null)
  const [drawerItems, setDrawerItems] = useState<DrawerRankItem[]>([])
  const [drawerLoading, setDrawerLoading] = useState(false)
  const [drawerError, setDrawerError] = useState('')

  /** 加载管理员仪表盘数据。 */
  async function loadDashboard() {
    setLoading(true)
    setError('')
    try {
      const [overviewData, trendData, topData, kbData] = await Promise.all([
        adminApi.overview(),
        adminApi.dailyTrend(30),
        adminApi.topUploaders(5),
        adminApi.kbDistribution(),
      ])
      setOverview(overviewData)
      setTrend(trendData.items)
      setTop(topData.items)
      setKbs(kbData.items)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  /** 打开完整上传者排行抽屉。 */
  async function openUploaderRanking() {
    setDrawer({
      kind: 'uploaders',
      title: '上传者总排名',
      subtitle: '按累计上传量排序，最多展示前 50 名。',
    })
    setDrawerItems([])
    setDrawerError('')
    setDrawerLoading(true)
    try {
      const data = await adminApi.topUploaders(50)
      setDrawerItems(data.items.map((item: UploaderRankItem) => ({
        id: item.user_id,
        name: item.username,
        count: item.count,
      })))
    } catch (err: any) {
      setDrawerError(err.response?.data?.detail || err.message || '上传者排行加载失败')
    } finally {
      setDrawerLoading(false)
    }
  }

  /** 打开指定用户在各知识库的上传分布抽屉。 */
  async function openUserKbDistribution(item: TopUploader | UploaderRankItem) {
    setDrawer({
      kind: 'user-kbs',
      title: `${item.username || '未命名用户'} 的知识库分布`,
      subtitle: '该上传者在各知识库中的上传数量。',
    })
    setDrawerItems([])
    setDrawerError('')
    setDrawerLoading(true)
    try {
      const data = await adminApi.userKbDistribution(item.user_id)
      setDrawerItems(data.items.map((kb: KbRankItem) => ({
        id: kb.kb_id,
        name: kb.kb_name,
        count: kb.count,
      })))
    } catch (err: any) {
      setDrawerError(err.response?.data?.detail || err.message || '用户知识库分布加载失败')
    } finally {
      setDrawerLoading(false)
    }
  }

  /** 打开指定知识库下的上传者排行抽屉。 */
  async function openKbUploaders(item: KbDistribution | KbRankItem) {
    setDrawer({
      kind: 'kb-uploaders',
      title: `${item.kb_name || '未命名知识库'} 的上传者排行`,
      subtitle: '该知识库内各用户的上传数量。',
    })
    setDrawerItems([])
    setDrawerError('')
    setDrawerLoading(true)
    try {
      const data = await adminApi.kbUploaders(item.kb_id, 50)
      setDrawerItems(data.items.map((uploader: UploaderRankItem) => ({
        id: uploader.user_id,
        name: uploader.username,
        count: uploader.count,
      })))
    } catch (err: any) {
      setDrawerError(err.response?.data?.detail || err.message || '知识库上传者排行加载失败')
    } finally {
      setDrawerLoading(false)
    }
  }

  /** 根据当前抽屉上下文继续下钻排行项。 */
  function handleDrawerItemClick(item: DrawerRankItem) {
    if (!drawer) {
      return
    }
    if (drawer.kind === 'uploaders' || drawer.kind === 'kb-uploaders') {
      openUserKbDistribution({
        user_id: item.id,
        username: item.name,
        count: item.count,
      })
      return
    }
    openKbUploaders({
      kb_id: item.id,
      kb_name: item.name,
      count: item.count,
    })
  }

  const maxUploaderCount = useMemo(
    () => Math.max(...top.map((item) => item.count), 1),
    [top],
  )
  const totalKbCount = useMemo(
    () => kbs.reduce((sum, item) => sum + item.count, 0),
    [kbs],
  )
  const failureRate = overview && overview.total > 0
    ? Math.round((overview.failed / overview.total) * 100)
    : 0

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-sm text-slate-500">加载数据概览中...</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-slate-900">数据概览</h2>
          <p className="mt-1 text-sm text-slate-500">上传、解析和知识库使用情况</p>
        </div>
        <button
          onClick={loadDashboard}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:border-blue-400 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          刷新数据
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {overview && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="总上传数"
            value={overview.total}
            hint="全部本地记录"
            tone="blue"
            icon={<FileText size={18} />}
          />
          <KpiCard
            label="本周上传"
            value={overview.week_count}
            hint="近 7 天新增"
            tone="green"
            icon={<TrendingUp size={18} />}
          />
          <KpiCard
            label="解析失败"
            value={overview.failed}
            hint={`失败率 ${failureRate}%`}
            tone="red"
            icon={<AlertCircle size={18} />}
          />
          <KpiCard
            label="活跃用户"
            value={overview.active_users_7d}
            hint="近 7 天上传者"
            tone="violet"
            icon={<Users size={18} />}
          />
        </div>
      )}

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">上传趋势</h3>
            <p className="mt-1 text-xs text-slate-500">近 30 天每日上传量</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            上传量
          </div>
        </div>
        <div className="h-[300px] px-2 py-4">
          {trend.length === 0 ? (
            <EmptyPanel text="暂无趋势数据" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 14, right: 24, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="uploadTrend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1677ff" stopOpacity={0.24} />
                    <stop offset="95%" stopColor="#1677ff" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#eef2f7" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: '#e2e8f0' }}
                  minTickGap={28}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#1677ff"
                  strokeWidth={2.4}
                  fill="url(#uploadTrend)"
                  activeDot={{ r: 4, strokeWidth: 0, fill: '#1677ff' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_1.2fr]">
        <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">上传者 Top 5</h3>
              <p className="mt-1 text-xs text-slate-500">按累计上传量排序</p>
            </div>
            <button
              type="button"
              onClick={openUploaderRanking}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100"
            >
              <ListOrdered size={14} />
              更多
            </button>
          </div>
          <div className="px-5 py-4">
            {top.length === 0 ? (
              <EmptyPanel text="暂无上传者数据" />
            ) : (
              <div className="space-y-4">
                {top.map((item, index) => {
                  const width = Math.round((item.count / maxUploaderCount) * 100)
                  return (
                    <button
                      type="button"
                      key={item.user_id || item.username}
                      onClick={() => openUserKbDistribution(item)}
                      className="grid w-full grid-cols-[32px_1fr_auto] items-center gap-3 rounded-md py-1 text-left transition-colors hover:bg-slate-50"
                    >
                      <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${rankBadgeClass(index)}`}>
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate text-sm font-medium text-slate-700" title={item.username}>
                            {item.username || '未命名用户'}
                          </span>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-blue-500"
                            style={{ width: `${width}%` }}
                          />
                        </div>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-slate-900">
                        {item.count.toLocaleString()}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">知识库上传分布</h3>
              <p className="mt-1 text-xs text-slate-500">点击知识库查看上传者排行</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-md bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-700">
              <Database size={14} />
              共 {kbs.length} 个知识库
            </div>
          </div>
          {kbs.length === 0 ? (
            <EmptyPanel text="暂无知识库分布数据" />
          ) : (
            <div className="grid grid-cols-1 gap-0 xl:grid-cols-[1fr_240px]">
              <div className="px-5 py-4">
                <div className="mb-3 border-b border-slate-100 pb-2 text-xs font-medium text-slate-400">
                  知识库
                </div>
                <div className="space-y-3">
                  {kbs.map((item, index) => {
                    const percent = totalKbCount > 0
                      ? Math.round((item.count / totalKbCount) * 100)
                      : 0
                    return (
                      <button
                        type="button"
                        key={item.kb_id}
                        onClick={() => openKbUploaders(item)}
                        className="block w-full rounded-md p-1 text-left transition-colors hover:bg-slate-50"
                      >
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <span
                            className="flex min-w-0 items-center gap-2 truncate text-sm font-medium text-slate-700"
                            title={item.kb_name}
                          >
                            <span
                              className="h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ backgroundColor: DONUT_COLORS[index % DONUT_COLORS.length] }}
                            />
                            {item.kb_name || '未命名知识库'}
                          </span>
                          <span className="shrink-0 text-sm text-slate-500">
                            {item.count.toLocaleString()} / {percent}%
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-blue-500"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="relative border-t border-slate-100 px-5 py-4 xl:border-l xl:border-t-0">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={kbs}
                      dataKey="count"
                      nameKey="kb_name"
                      innerRadius={58}
                      outerRadius={84}
                      paddingAngle={2}
                      stroke="#fff"
                      strokeWidth={3}
                      onClick={(_: any, index: number) => {
                        const item = kbs[index]
                        if (item) openKbUploaders(item)
                      }}
                    >
                      {kbs.map((_, index) => (
                        <Cell
                          key={index}
                          fill={DONUT_COLORS[index % DONUT_COLORS.length]}
                          className="cursor-pointer outline-none"
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<DonutTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-x-5 top-[92px] text-center">
                  <div className="text-2xl font-semibold tabular-nums text-slate-900">
                    {totalKbCount.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">总上传</div>
                </div>
              </div>
              <div className="col-span-full border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
                列表用于精确读取，环形图用于查看整体结构。
              </div>
            </div>
          )}
        </section>
      </div>

      <RankingDrawer
        state={drawer}
        items={drawerItems}
        loading={drawerLoading}
        error={drawerError}
        onClose={() => setDrawer(null)}
        onItemClick={handleDrawerItemClick}
      />
    </div>
  )
}

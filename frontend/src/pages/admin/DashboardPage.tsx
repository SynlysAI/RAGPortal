import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar,
  PieChart, Pie, Cell as PieCell, Legend,
} from 'recharts'
import { adminApi } from '@/api/admin'

interface Overview { total: number; week_count: number; failed: number; active_users_7d: number }

const PIE_COLORS = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']

function KpiCard({ label, value, valueClass = '' }: { label: string; value: number; valueClass?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-1.5">{label}</div>
      <div className={`text-2xl font-bold ${valueClass || 'text-slate-900'}`}>
        {value.toLocaleString()}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [trend, setTrend] = useState<{ date: string; count: number }[]>([])
  const [top, setTop] = useState<{ user_id: string; username: string; count: number }[]>([])
  const [kbs, setKbs] = useState<{ kb_id: string; kb_name: string; count: number }[]>([])

  useEffect(() => {
    Promise.all([
      adminApi.overview(),
      adminApi.dailyTrend(30),
      adminApi.topUploaders(5),
      adminApi.kbDistribution(),
    ]).then(([o, t, tp, k]) => {
      setOverview(o)
      setTrend(t.items)
      setTop(tp.items)
      setKbs(k.items)
    }).catch(() => {})
  }, [])

  if (!overview) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-sm text-slate-500">加载中...</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-slate-800">数据概览</h2>

      {/* KPI 卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="总上传数" value={overview.total} />
        <KpiCard label="本周上传" value={overview.week_count} />
        <KpiCard label="解析失败" value={overview.failed} valueClass="text-red-600" />
        <KpiCard label="活跃用户 (7天)" value={overview.active_users_7d} />
      </div>

      {/* 趋势 + Top */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">每日上传量趋势 (近 30 天)</h3>
          {trend.length === 0 ? (
            <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">暂无数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">上传者 Top 5</h3>
          {top.length === 0 ? (
            <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">暂无数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={top}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="username" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* KB 分布 */}
      <div className="bg-white border border-slate-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">各知识库上传分布</h3>
        {kbs.length === 0 ? (
          <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">暂无数据</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={kbs} dataKey="count" nameKey="kb_name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }: any) => `${name} (${value})`}>
                {kbs.map((_, i) => (
                  <PieCell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

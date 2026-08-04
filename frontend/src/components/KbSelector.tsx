import { useEffect, useState } from 'react'
import { RotateCw } from 'lucide-react'
import { kbApi, type KbInfo } from '@/api/kb'

interface Props {
  value: string
  onChange: (id: string) => void
}

export default function KbSelector({ value, onChange }: Props) {
  const [kbs, setKbs] = useState<KbInfo[]>([])
  const [loading, setLoading] = useState(true)

  function loadKbs(refresh = false) {
    setLoading(true)
    kbApi.list(refresh)
      .then(setKbs)
      .catch(() => setKbs([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadKbs()
  }, [])

  if (loading) {
    return <div className="text-sm text-slate-500">加载知识库列表中...</div>
  }

  if (kbs.length === 0) {
    return (
      <div className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded border border-amber-200">
        当前 API Key 没有可访问的知识库,无法上传。请联系管理员确认 API Key 范围。
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 border border-slate-300 rounded-md bg-white text-sm min-w-[240px] focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
      >
        <option value="">请选择知识库</option>
        {kbs.map((kb) => (
          <option key={kb.id} value={kb.id}>{kb.name}</option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => loadKbs(true)}
        disabled={loading}
        title="刷新知识库列表"
        className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RotateCw size={16} className={loading ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}

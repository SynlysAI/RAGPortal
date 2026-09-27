import { useEffect, useState } from 'react'
import { Copy, KeyRound, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { apiTokensApi, TOKEN_PERMISSIONS, type ApiToken } from '@/api/apiTokens'
import { kbApi, type KbInfo } from '@/api/kb'

export default function ApiTokensPage() {
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [name, setName] = useState('外部 MCP 客户端')
  const [permissions, setPermissions] = useState<string[]>(['knowledge-bases:list', 'documents:list', 'documents:search', 'documents:read', 'documents:download'])
  const [knowledgeBases, setKnowledgeBases] = useState<KbInfo[]>([])
  const [knowledgeBaseIds, setKnowledgeBaseIds] = useState<string[]>([])
  const [secret, setSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    try {
      const [tokenData, kbData] = await Promise.all([apiTokensApi.list(), kbApi.list()])
      setTokens(tokenData.items)
      setKnowledgeBases(kbData)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Token 列表加载失败')
    }
  }

  useEffect(() => { load() }, [])

  function togglePermission(key: string) {
    setPermissions((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key])
  }

  function toggleKnowledgeBase(id: string) {
    setKnowledgeBaseIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  async function createToken() {
    if (!name.trim()) return
    setLoading(true)
    setError('')
    try {
      const result = await apiTokensApi.create(name, permissions, knowledgeBaseIds)
      setSecret(result.secret)
      setName('外部 MCP 客户端')
      setKnowledgeBaseIds([])
      await load()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Token 创建失败')
    } finally {
      setLoading(false)
    }
  }

  async function revokeToken(token: ApiToken) {
    if (!window.confirm(`确定撤销“${token.name}”吗？`)) return
    await apiTokensApi.revoke(token.id)
    await load()
  }

  async function copySecret() {
    await navigator.clipboard.writeText(secret)
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">API Token</h2>
        <p className="mt-1 text-sm text-slate-500">为外部 MCP 客户端创建受控访问凭据。</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {secret && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-center gap-2 font-semibold text-amber-900"><ShieldCheck size={18} /> Token 只显示这一次</div>
          <p className="mt-2 text-sm text-amber-800">请立即复制并保存，离开此页面后无法再次查看明文。</p>
          <div className="mt-3 flex gap-2">
            <code className="min-w-0 flex-1 break-all rounded border border-amber-300 bg-white px-3 py-2 text-sm text-slate-800">{secret}</code>
            <button onClick={copySecret} className="inline-flex items-center gap-1 rounded bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-700"><Copy size={15} />复制</button>
          </div>
          <button onClick={() => setSecret('')} className="mt-3 text-xs text-amber-800 underline">我已保存，关闭提示</button>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-base font-semibold text-slate-900"><KeyRound size={18} />创建 Token</div>
        <label className="mt-4 block text-sm font-medium text-slate-700">名称<input value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="例如 外部客户端只读" /></label>
        <div className="mt-4 text-sm font-medium text-slate-700">权限</div>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {TOKEN_PERMISSIONS.map((permission) => <label key={permission.key} className="flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700"><input type="checkbox" checked={permissions.includes(permission.key)} onChange={() => togglePermission(permission.key)} />{permission.label}<span className="ml-auto text-xs text-slate-400">{permission.key}</span></label>)}
        </div>
        <div className="mt-4 text-sm font-medium text-slate-700">绑定知识库</div>
        <p className="mt-1 text-xs text-slate-500">外部客户端只能查询和操作勾选的知识库。</p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {knowledgeBases.length === 0 && <div className="text-sm text-slate-400">暂无可绑定知识库</div>}
          {knowledgeBases.map((kb) => <label key={kb.id} className="flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700"><input type="checkbox" checked={knowledgeBaseIds.includes(kb.id)} onChange={() => toggleKnowledgeBase(kb.id)} /><span className="truncate">{kb.name}</span><code className="ml-auto text-xs text-slate-400">{kb.id}</code></label>)}
        </div>
        <button onClick={createToken} disabled={loading || !name.trim() || knowledgeBaseIds.length === 0} className="mt-5 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"><Plus size={16} />{loading ? '创建中...' : '创建 Token'}</button>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4 text-base font-semibold text-slate-900">已创建 Token</div>
        <div className="divide-y divide-slate-100">
          {tokens.length === 0 && <div className="px-5 py-10 text-center text-sm text-slate-400">暂无 Token</div>}
          {tokens.map((token) => <div key={token.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"><div><div className="font-medium text-slate-800">{token.name} <code className="ml-2 text-xs text-slate-400">{token.token_prefix}...</code></div><div className="mt-1 text-xs text-slate-500">权限：{token.permissions.join('、')} · 知识库：{token.knowledge_base_ids.length} 个 · 创建于 {new Date(token.created_at).toLocaleString()}</div></div><button disabled={token.status !== 'active'} onClick={() => revokeToken(token)} className="inline-flex items-center gap-1 rounded border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"><Trash2 size={14} />{token.status === 'active' ? '撤销' : '已撤销'}</button></div>)}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600"><div className="font-semibold text-slate-800">MCP 客户端配置</div><pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-4 text-xs text-slate-100">{`{\n  "mcpServers": {\n    "ragportal": {\n      "type": "streamable-http",\n      "url": "https://你的域名/api/mcp",\n      "headers": {\n        "Authorization": "Bearer YOUR_API_TOKEN"\n      }\n    }\n  }\n}`}</pre></section>
    </div>
  )
}

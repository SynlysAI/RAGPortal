/* RAGPortal 操作指导文档（飞书知识库） */
const GUIDE_DOC_URL = 'https://gcnpf55d0gns.feishu.cn/wiki/ZNANwsqxBiNnhUkjKl0cjKacnMh'

/** 打开的书本图标（与其它子平台保持一致的视觉语义）。 */
function GuideIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="15"
      height="15"
    >
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  )
}

/** 顶栏操作指导入口：新窗口打开平台操作指导文档。 */
export default function GuideButton() {
  return (
    <button
      type="button"
      aria-label="操作指导"
      title="操作指导"
      onClick={() => window.open(GUIDE_DOC_URL, '_blank', 'noopener,noreferrer')}
      className="w-8 h-8 rounded-full border border-slate-200 text-brand
                 flex items-center justify-center transition-colors
                 hover:bg-blue-50 hover:border-blue-200"
    >
      <GuideIcon />
    </button>
  )
}

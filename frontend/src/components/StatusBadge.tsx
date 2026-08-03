type Status = 'pending' | 'processing' | 'success' | 'failed'

const LABELS: Record<Status, { text: string; cls: string; icon: string }> = {
  pending:    { text: '等待中', cls: 'bg-yellow-100 text-yellow-700', icon: '⌛' },
  processing: { text: '处理中', cls: 'bg-blue-100 text-blue-700',   icon: '⏳' },
  success:    { text: '成功',   cls: 'bg-green-100 text-green-700', icon: '✓' },
  failed:     { text: '失败',   cls: 'bg-red-100 text-red-700',     icon: '✗' },
}

interface Props {
  status: Status | string
  tooltip?: string
}

export default function StatusBadge({ status, tooltip }: Props) {
  const cfg = LABELS[status as Status] || LABELS.pending
  const title = status === 'failed' ? (tooltip || '上传失败') : undefined
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${
        title ? 'cursor-help' : ''
      } ${cfg.cls}`}
      title={title}
      aria-label={title}
    >
      <span>{cfg.icon}</span>
      {cfg.text}
    </span>
  )
}

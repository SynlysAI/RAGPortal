import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { getToken } from '@/api/client'

const AI4MS_API_BASE = String(
  import.meta.env.VITE_AI4MS_API_URL || 'https://ai4ms.xmuzc.com',
).replace(/\/+$/, '')
const AI4MS_FEEDBACK_URL = `${AI4MS_API_BASE}/api/v1/feedback`

/** 平台标识（与 AI4MS 后端 FEEDBACK_PLATFORMS 对应）。 */
const FEEDBACK_PLATFORM = 'ragportal'

const FEEDBACK_TYPES = [
  { value: 'bug', label: '功能异常' },
  { value: 'ux', label: '体验问题' },
  { value: 'idea', label: '功能建议' },
  { value: 'other', label: '其他' },
] as const

const MAX_CONTENT_LENGTH = 500

/** 气泡 + 感叹号图标（与其它子平台保持一致的视觉语义）。 */
function FeedbackIcon() {
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
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="12" y1="7" x2="12" y2="12" />
      <line x1="12" y1="15" x2="12.01" y2="15" />
    </svg>
  )
}

type FeedbackType = (typeof FEEDBACK_TYPES)[number]['value']

/**
 * 顶栏意见反馈入口：按钮 + 弹窗，提交至 AI4MS 统一门户后端。
 *
 * Returns:
 *     圆形图标按钮，点击后弹出反馈提交弹窗。
 */
export default function FeedbackButton() {
  const user = useAuthStore((s) => s.user)
  const [open, setOpen] = useState(false)
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('bug')
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [toast, setToast] = useState<'success' | 'error' | null>(null)

  const canSubmit = content.trim().length > 0 && !submitting

  /** 打开弹窗并重置表单。 */
  function openDialog() {
    setFeedbackType('bug')
    setContent('')
    setOpen(true)
  }

  /** 显示轻量提示，2.2 秒后自动消失。 */
  function showToast(kind: 'success' | 'error') {
    setToast(kind)
    window.setTimeout(() => setToast(null), 2200)
  }

  /** 提交反馈。 */
  async function handleSubmit() {
    const text = content.trim()
    if (!text) {
      return
    }
    setSubmitting(true)
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = getToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
      const resp = await fetch(AI4MS_FEEDBACK_URL, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          platform: FEEDBACK_PLATFORM,
          feedback_type: feedbackType,
          content: text,
        }),
      })
      if (resp.status === 401) {
        showToast('error')
        setOpen(false)
        return
      }
      if (!resp.ok) {
        showToast('error')
        return
      }
      setOpen(false)
      showToast('success')
    } catch {
      showToast('error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="意见反馈"
        title="意见反馈"
        onClick={openDialog}
        className="w-8 h-8 rounded-full border border-slate-200 text-brand
                   flex items-center justify-center transition-colors
                   hover:bg-blue-50 hover:border-blue-200"
      >
        <FeedbackIcon />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-[480px] rounded-xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 pt-5">
              <h3 className="text-base font-semibold text-slate-800">意见反馈</h3>
              <button
                type="button"
                aria-label="关闭"
                onClick={() => setOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="px-6 pt-1 text-xs text-slate-400">
              您的反馈将提交至 AI4MS 平台管理员，感谢帮助我们一起改进
            </div>

            <div className="px-6 pt-4">
              <div className="text-[13px] text-slate-600 mb-2">
                <span className="text-red-500 mr-0.5">*</span>反馈类型
              </div>
              <div className="flex gap-2 flex-wrap mb-4">
                {FEEDBACK_TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setFeedbackType(t.value)}
                    className={`text-xs px-3.5 py-1.5 rounded-full border transition-colors ${
                      feedbackType === t.value
                        ? 'bg-blue-50 text-brand border-blue-300 font-medium'
                        : 'bg-slate-50 text-slate-500 border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="text-[13px] text-slate-600 mb-2">
                <span className="text-red-500 mr-0.5">*</span>反馈内容
              </div>
              <textarea
                rows={5}
                maxLength={MAX_CONTENT_LENGTH}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="请详细描述您遇到的问题或建议，如操作路径、预期效果、实际现象…"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700
                           focus:outline-none focus:border-brand focus:ring-2 focus:ring-blue-100 resize-none"
              />
              <div className="text-right text-[11px] text-slate-400 mt-1">
                {content.length} / {MAX_CONTENT_LENGTH}
              </div>

              <div className="flex items-center gap-2 mt-3 mb-1 text-xs text-slate-400">
                提交人：<b className="text-slate-600 font-medium">{user?.username || '当前登录用户'}</b>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-6 pb-5 pt-3">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-4 py-2 rounded-lg text-sm text-slate-500 border border-slate-200
                           hover:text-slate-700 hover:border-slate-300 transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="px-4 py-2 rounded-lg text-sm text-white bg-brand
                           hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? '提交中…' : '提交反馈'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={`fixed top-6 left-1/2 -translate-x-1/2 z-[110] px-5 py-2.5 rounded-lg text-sm
                      border shadow-lg ${
                        toast === 'success'
                          ? 'bg-sky-50 text-sky-700 border-sky-200'
                          : 'bg-red-50 text-red-600 border-red-200'
                      }`}
        >
          {toast === 'success'
            ? '提交成功，感谢您的反馈'
            : '提交失败，请检查登录状态后重试'}
        </div>
      )}
    </>
  )
}

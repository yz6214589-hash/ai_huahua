import { cn } from '@/lib/utils'
import { Bot, X } from 'lucide-react'
import { useMemo, useState } from 'react'

export function AssistantDrawer() {
  const [open, setOpen] = useState(false)
  const src = useMemo(() => {
    const base = 'http://127.0.0.1:8501/'
    return `${base}?embed=true`
  }, [])

  return (
    <>
      <button
        onDoubleClick={() => setOpen(true)}
        title="双击打开 AI 对话机器人"
        className="fixed bottom-6 right-6 z-40 inline-flex select-none items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-900 shadow-[0_10px_30px_rgba(0,0,0,0.12)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(0,0,0,0.16)]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white">
          <Bot className="h-5 w-5" />
        </span>
        <span>AI 投资助手</span>
      </button>

      <div
        className={cn(
          'fixed bottom-24 right-6 z-50 w-[420px] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_18px_48px_rgba(0,0,0,0.22)] transition duration-200',
          open ? 'pointer-events-auto translate-y-0 opacity-100' : 'pointer-events-none translate-y-3 opacity-0'
        )}
      >
        <div className="flex h-12 items-center justify-between gap-2 border-b border-zinc-200 px-3">
          <div className="truncate text-sm font-semibold text-zinc-900">AI 对话机器人</div>
          <button
            onClick={() => setOpen(false)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
            title="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <iframe title="assistant-streamlit" src={src} className="h-[600px] w-full" />
      </div>
    </>
  )
}

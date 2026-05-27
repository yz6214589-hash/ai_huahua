import { cn } from '@/lib/utils'
import { Bot, Maximize2, Minimize2, X } from 'lucide-react'
import { useMemo, useState } from 'react'

export function AssistantDrawer() {
  const [open, setOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const STREAMLIT_URL = import.meta.env.VITE_STREAMLIT_URL || 'http://127.0.0.1:8501/'
  const src = useMemo(() => {
    return `${STREAMLIT_URL}?embed=true&fullscreen=${fullscreen}`
  }, [fullscreen, STREAMLIT_URL])

  return (
    <>
      <button
        onDoubleClick={() => setOpen((v) => !v)}
        onClick={() => { if (!open) setOpen(true) }}
        title="AI 对话机器人（双击打开/关闭）"
        className="fixed bottom-6 right-6 z-40 inline-flex select-none items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-900 shadow-[0_10px_30px_rgba(0,0,0,0.12)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(0,0,0,0.16)]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white">
          <Bot className="h-5 w-5" />
        </span>
        <span>AI 投资助手</span>
      </button>

      <div
        className={cn(
          'fixed z-50 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_18px_48px_rgba(0,0,0,0.22)] transition-all duration-200',
          open ? 'pointer-events-auto translate-y-0 opacity-100' : 'pointer-events-none translate-y-3 opacity-0',
          fullscreen
            ? 'inset-4 md:inset-8'
            : 'bottom-24 right-6 w-[420px]',
          fullscreen ? '' : 'h-[600px]'
        )}
        onDoubleClick={() => setOpen(false)}
      >
        <div className="flex h-12 items-center justify-between gap-2 border-b border-zinc-200 px-3">
          <div className="truncate text-sm font-semibold text-zinc-900">AI 对话机器人</div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setFullscreen((v) => !v)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              title={fullscreen ? '取消全屏' : '全屏'}
            >
              {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
            <button
              onClick={() => setOpen(false)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              title="关闭"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <iframe
          title="assistant-streamlit"
          src={src}
          className={cn('w-full border-0', fullscreen ? 'h-[calc(100%-48px)]' : 'h-[548px]')}
        />
      </div>
    </>
  )
}

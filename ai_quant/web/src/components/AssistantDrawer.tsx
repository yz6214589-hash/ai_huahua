import { cn } from '@/lib/utils'
import { Bot, ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'

export function AssistantDrawer() {
  const [collapsed, setCollapsed] = useState(false)
  const [open, setOpen] = useState(false)

  const STREAMLIT_URL = import.meta.env.VITE_STREAMLIT_URL || 'http://127.0.0.1:8501/'
  const src = useMemo(() => {
    return `${STREAMLIT_URL}?embed=true&fullscreen=${open}`
  }, [open, STREAMLIT_URL])

  return (
    <>
      {/* 收起状态 - 显示一个小按钮在右侧边缘，点击可展开 */}
      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          title="展开AI投资助手"
          className="fixed right-0 top-1/2 -translate-y-1/2 z-50 flex h-20 w-10 items-center justify-center rounded-l-xl rounded-r-none border border-r-0 border-zinc-300/60 bg-white/90 backdrop-blur-md text-zinc-800 shadow-lg transition-all hover:bg-white hover:shadow-xl hover:w-12"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
      )}

      {/* 展开状态 - 显示原来的大按钮样式 */}
      {!collapsed && (
        <>
          {/* 主按钮 */}
          <button
            onClick={() => setOpen(true)}
            title="AI 投资助手"
            className="fixed bottom-6 right-6 z-40 inline-flex select-none items-center gap-2 rounded-full border border-zinc-200 bg-white/92 backdrop-blur-md px-4 py-3 text-sm font-semibold text-zinc-900 shadow-[0_10px_30px_rgba(0,0,0,0.12)] transition-all hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(0,0,0,0.16)]"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white">
              <Bot className="h-5 w-5" />
            </span>
            <span>AI 投资助手</span>
            {/* 收起按钮 */}
            <button
              onClick={(e) => { e.stopPropagation(); setCollapsed(true) }}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors"
              title="收起"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </button>

          {/* 对话窗口 */}
          {open && (
            <>
              <div
                className={cn(
                  'fixed bottom-24 right-6 z-50 w-[420px] overflow-hidden rounded-2xl border border-zinc-200 bg-white/95 backdrop-blur-md shadow-[0_18px_48px_rgba(0,0,0,0.22)] transition-all duration-200'
                )}
              >
                <div className="flex h-12 items-center justify-between gap-2 border-b border-zinc-200 px-3">
                  <div className="truncate text-sm font-semibold text-zinc-900">AI 对话机器人</div>
                  <button
                    onClick={() => setOpen(false)}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
                    title="关闭"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
                <iframe
                  title="assistant-streamlit"
                  src={src}
                  className="w-full h-[560px] border-0"
                />
              </div>
              {/* 点击外部关闭 */}
              <div
                className="fixed inset-0 z-45"
                onClick={() => setOpen(false)}
              />
            </>
          )}
        </>
      )}
    </>
  )
}

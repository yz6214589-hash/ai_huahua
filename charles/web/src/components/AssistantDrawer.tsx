import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight, MessageSquare } from 'lucide-react'
import { useMemo, useState } from 'react'

export function AssistantDrawer() {
  const [collapsed, setCollapsed] = useState(false)
  const src = useMemo(() => {
    const base = 'http://127.0.0.1:8501/'
    return `${base}?embed=true`
  }, [])

  return (
    <div
      className={cn(
        'fixed right-0 top-0 z-50 h-screen border-l border-zinc-200 bg-white shadow-[-12px_0_28px_rgba(0,0,0,0.08)] transition-[width] duration-200',
        collapsed ? 'w-14' : 'w-[420px]'
      )}
    >
      <div className="flex h-14 items-center justify-between gap-2 border-b border-zinc-200 px-2">
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
          title={collapsed ? '展开' : '折叠'}
        >
          {collapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        {collapsed ? (
          <MessageSquare className="h-5 w-5 text-zinc-500" />
        ) : (
          <div className="truncate text-sm font-semibold text-zinc-900">对话机器人</div>
        )}
        <div className="w-10" />
      </div>
      {collapsed ? null : <iframe title="assistant-streamlit" src={src} className="h-[calc(100vh-56px)] w-full" />}
    </div>
  )
}


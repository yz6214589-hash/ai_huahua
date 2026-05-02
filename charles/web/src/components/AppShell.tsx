import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Activity, Database, FileText, Gauge, PlayCircle, Search, Star } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import { AssistantDrawer } from '@/components/AssistantDrawer'

function Sidebar() {
  const items = [
    { to: '/', label: '总览', icon: Gauge },
    { to: '/jobs', label: '采集任务', icon: PlayCircle },
    { to: '/reports', label: '智能研报', icon: FileText },
    { to: '/sentiment', label: '舆情监控', icon: Activity },
    { to: '/data', label: '数据与交付', icon: Database },
    { to: '/watchlist', label: '自选股', icon: Star },
  ]

  return (
    <aside className="hidden h-screen w-60 flex-col border-r border-zinc-200 bg-white md:flex">
      <div className="flex items-center gap-2 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-900 text-white">
          C
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-zinc-900">Charles</div>
          <div className="text-xs text-zinc-500">数据情报官</div>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3 pb-4">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition',
                isActive ? 'bg-zinc-100 text-zinc-900' : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
              )
            }
          >
            <it.icon className="h-4 w-4" />
            {it.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 pb-4 text-xs text-zinc-500">API: /api</div>
    </aside>
  )
}

function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const [q, setQ] = useState(params.get('stock_code') || '')

  const title = useMemo(() => {
    if (location.pathname.startsWith('/jobs')) return '采集任务'
    if (location.pathname.startsWith('/reports')) return '智能研报'
    if (location.pathname.startsWith('/sentiment')) return '舆情监控'
    if (location.pathname.startsWith('/data')) return '数据与交付'
    if (location.pathname.startsWith('/watchlist')) return '自选股'
    if (location.pathname.startsWith('/stock/')) return '个股详情'
    return '总览'
  }, [location.pathname])

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-3 md:px-6">
      <div>
        <div className="text-sm font-semibold text-zinc-900">{title}</div>
        <div className="text-xs text-zinc-500">{new Date().toLocaleDateString()}</div>
      </div>
      <div className="flex w-full items-center gap-2 md:w-auto">
        <div className="relative flex-1 md:w-96">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const v = q.trim()
                navigate(v ? `/data?stock_code=${encodeURIComponent(v)}` : '/data')
              }
            }}
            placeholder="输入股票代码或名称"
            className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm outline-none transition focus:border-zinc-400"
          />
        </div>
        <button
          onClick={() => {
            const v = q.trim()
            navigate(v ? `/watchlist?q=${encodeURIComponent(v)}` : '/watchlist')
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-zinc-800"
        >
          <Search className="h-4 w-4" />
          搜索
        </button>
        <Link
          to="/jobs"
          className="hidden rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 md:inline"
        >
          去跑任务
        </Link>
      </div>
    </header>
  )
}

export default function AppShell() {
  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="flex">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <Topbar />
          <main className="flex-1 px-4 py-6 md:px-6">
            <Outlet />
          </main>
        </div>
      </div>
      <AssistantDrawer />
    </div>
  )
}


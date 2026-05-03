import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Activity, Bot, ChartCandlestick, ChevronLeft, ChevronRight, Database, FileText, Gauge, PlayCircle, Search, Shield, Star, Workflow } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import { AssistantDrawer } from '@/components/AssistantDrawer'

function isCnMarketOpen(now: Date): boolean {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = fmt.formatToParts(now)
  const weekday = parts.find((x) => x.type === 'weekday')?.value || ''
  const hh = Number(parts.find((x) => x.type === 'hour')?.value || '0')
  const mm = Number(parts.find((x) => x.type === 'minute')?.value || '0')
  const total = hh * 60 + mm
  const isWeekday = weekday !== 'Sat' && weekday !== 'Sun'
  if (!isWeekday) return false
  const amOpen = total >= 9 * 60 + 30 && total < 11 * 60 + 30
  const pmOpen = total >= 13 * 60 && total < 15 * 60
  return amOpen || pmOpen
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const items = [
    { to: '/', label: '总览', icon: Gauge },
    { to: '/jobs', label: '采集任务', icon: PlayCircle },
    { to: '/reports', label: '智能研报', icon: FileText },
    { to: '/sentiment', label: '舆情监控', icon: Activity },
    { to: '/execution', label: '执行监控', icon: Workflow },
    { to: '/risk', label: '风控中心', icon: Shield },
    { to: '/strategy', label: '策略分析', icon: ChartCandlestick },
    { to: '/morning', label: '晨会简报', icon: FileText },
    { to: '/chat', label: 'AI 对话', icon: Bot },
    { to: '/data', label: '数据与交付', icon: Database },
    { to: '/watchlist', label: '自选股', icon: Star },
  ]
  const [marketOpen, setMarketOpen] = useState(() => isCnMarketOpen(new Date()))

  useEffect(() => {
    const timer = window.setInterval(() => {
      setMarketOpen(isCnMarketOpen(new Date()))
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [])

  const avatarSrc = marketOpen ? '/hua-hua-avatar-gold.svg' : '/hua-hua-avatar-black.svg'

  return (
    <aside className={cn('hidden h-screen flex-col border-r border-zinc-200 bg-white transition-all duration-200 md:flex', collapsed ? 'w-20' : 'w-60')}>
      <div className={cn('flex items-center py-4', collapsed ? 'justify-center px-2' : 'gap-2 px-5')}>
        <img src={avatarSrc} alt="hua hua avatar" className="h-9 w-9 rounded-xl border border-zinc-200 bg-white object-cover" />
        {!collapsed ? (
          <div className="leading-tight">
            <div className="text-sm font-semibold text-zinc-900">Hua Hua</div>
            <div className="text-xs text-zinc-500">统一量化系统</div>
          </div>
        ) : null}
      </div>
      <div className={cn('pb-2', collapsed ? 'px-2' : 'px-3')}>
        <button
          onClick={onToggle}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
          title={collapsed ? '展开导航' : '折叠导航'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed ? '折叠导航' : null}
        </button>
      </div>
      <nav className={cn('flex flex-1 flex-col gap-1 pb-4', collapsed ? 'px-2' : 'px-3')}>
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            title={collapsed ? it.label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center rounded-lg py-2 text-sm transition',
                collapsed ? 'justify-center px-2' : 'gap-2 px-3',
                isActive ? 'bg-zinc-100 text-zinc-900' : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
              )
            }
          >
            <it.icon className="h-4 w-4" />
            {!collapsed ? it.label : null}
          </NavLink>
        ))}
      </nav>
      <div className={cn('pb-4 text-xs text-zinc-500', collapsed ? 'px-2 text-center' : 'px-5')}>API: /api</div>
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
    if (location.pathname.startsWith('/execution')) return '执行监控'
    if (location.pathname.startsWith('/risk')) return '风控中心'
    if (location.pathname.startsWith('/strategy')) return '策略分析'
    if (location.pathname.startsWith('/morning')) return '晨会简报'
    if (location.pathname.startsWith('/chat')) return 'AI 对话'
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="flex">
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((v) => !v)} />
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


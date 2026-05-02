import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { FileText, Gauge, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

function Sidebar() {
  const items = [
    { to: '/', label: '订单审批', icon: ShieldCheck },
    { to: '/dashboard', label: '风控看板', icon: Gauge },
    { to: '/audit', label: '审计日志', icon: FileText },
  ]

  return (
    <aside className="hidden h-screen w-60 flex-col border-r border-zinc-200 bg-white md:flex">
      <div className="flex items-center gap-2 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-900 text-white">K</div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-zinc-900">Kirs</div>
          <div className="text-xs text-zinc-500">风控师</div>
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
  const location = useLocation()
  const title = (() => {
    if (location.pathname.startsWith('/dashboard')) return '风控看板'
    if (location.pathname.startsWith('/audit')) return '审计日志'
    return '订单审批'
  })()

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-3 md:px-6">
      <div>
        <div className="text-sm font-semibold text-zinc-900">{title}</div>
        <div className="text-xs text-zinc-500">资金与风险管理 · 合规一票否决 · 可追溯审计</div>
      </div>
      <div className="text-xs text-zinc-500">{new Date().toLocaleString()}</div>
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
    </div>
  )
}

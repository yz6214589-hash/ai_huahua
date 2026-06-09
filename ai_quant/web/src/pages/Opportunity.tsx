import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { key: 'signals', label: '信号中心', path: '/opportunity/signals' },
  { key: 'unusual', label: '异动监控', path: '/opportunity/unusual' },
  { key: 'limitup', label: '涨停追踪', path: '/opportunity/limitup' },
  { key: 'sector', label: '板块轮动', path: '/opportunity/sector' },
]

export default function Opportunity() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = TABS.find((t) => location.pathname.startsWith(t.path))?.key || 'unusual'

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 border-b border-zinc-200 bg-white">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => navigate(tab.path)}
              className={cn(
                'border-b-2 px-4 py-2.5 text-sm font-medium transition',
                activeKey === tab.key
                  ? 'border-zinc-900 text-zinc-900'
                  : 'border-transparent text-zinc-500 hover:text-zinc-800'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <Outlet />
      </div>
    </div>
  )
}

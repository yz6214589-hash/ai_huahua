import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { key: 'library', label: '策略库', path: '/strategy/library' },
  { key: 'instances', label: '策略实例', path: '/strategy/instances' },
  { key: 'backtest', label: '回测', path: '/strategy/backtest' },
  { key: 'walk-forward', label: '滚动验证', path: '/strategy/walk-forward' },
  { key: 'param-optimizer', label: '参数优化', path: '/strategy/param-optimizer' },
  { key: 'performance', label: '绩效报告', path: '/strategy/performance' },
]

export default function StrategyAnalysis() {
  const navigate = useNavigate()
  const location = useLocation()
  // 精确匹配优先，避免子路径被父路径误匹配
  const activeKey = TABS.find((t) => location.pathname === t.path)?.key
    || TABS.find((t) => location.pathname.startsWith(t.path))?.key
    || 'library'

  return (
    <div>
      <div className="mb-4 border-b border-zinc-200">
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
      <Outlet />
    </div>
  )
}

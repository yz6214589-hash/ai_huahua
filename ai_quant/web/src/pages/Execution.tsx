import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useState } from 'react'

const TABS = [
  { key: 'positions', label: '账户持仓', path: '/execution/positions' },
  { key: 'tasks', label: '执行任务', path: '/execution/tasks' },
  { key: 'records', label: '交易记录', path: '/execution/records' },
  { key: 'sim-account', label: '模拟盘', path: '/execution/sim-account' },
]

export default function Execution() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = TABS.find((t) => location.pathname.startsWith(t.path))?.key || 'positions'

  return (
    <div>
      <div className="sticky top-0 z-10 mb-4 border-b border-zinc-200 bg-white">
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

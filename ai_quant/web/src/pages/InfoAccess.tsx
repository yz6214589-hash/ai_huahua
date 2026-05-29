import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { key: 'data-collection', label: '数据采集', path: '/info-access/data-collection' },
  { key: 'sentiment', label: '舆情监控', path: '/info-access/sentiment' },
  { key: 'macro', label: '宏观数据', path: '/info-access/macro' },
  { key: 'financial-hot', label: '财经热点', path: '/info-access/financial-hot' },
  { key: 'data-delivery', label: '数据与交付', path: '/info-access/data-delivery' },
]

export default function InfoAccess() {
  const navigate = useNavigate()
  const location = useLocation()

  const activeKey = TABS.find((t) => location.pathname === t.path)?.key || 'data-collection'

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

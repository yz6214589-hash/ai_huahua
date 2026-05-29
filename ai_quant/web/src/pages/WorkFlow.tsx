import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { key: 'team', label: '交易团队工作流', path: '/workflow/team' },
  { key: 'morning', label: '晨会简报', path: '/workflow/morning' },
  { key: 'dragon', label: '龙头战法', path: '/workflow/dragon' },
]

export default function WorkFlow() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = TABS.find((t) => location.pathname.startsWith(t.path))?.key || 'team'

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

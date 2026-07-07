import { cn } from '@/lib/utils'
import { MessageSquare, Cpu, Wrench, Users, FileText, MessageCircle, Key, Settings, Activity, Clock } from 'lucide-react'

interface NavItem {
  key: string
  label: string
  icon: typeof MessageSquare
}

const NAV_ITEMS: NavItem[] = [
  { key: 'conversations', label: '会话管理', icon: MessageSquare },
  { key: 'models', label: '模型管理', icon: Cpu },
  { key: 'tools', label: '工具与技能', icon: Wrench },
  { key: 'agents', label: '智能体配置', icon: Users },
  { key: 'prompts', label: '提示词管理', icon: FileText },
  { key: 'feishu', label: '飞书集成', icon: MessageCircle },
  { key: 'api-keys', label: 'API密钥', icon: Key },
  { key: 'settings', label: '系统配置', icon: Settings },
  { key: 'logs', label: '日志与监控', icon: Activity },
  { key: 'schedules', label: '定时任务', icon: Clock },
]

interface AdminSidebarProps {
  activeKey: string
  collapsed: boolean
  onNavigate: (key: string) => void
}

export function AdminSidebar({ activeKey, collapsed, onNavigate }: AdminSidebarProps) {
  return (
    <aside
      className={cn(
        'flex flex-col border-r border-zinc-200 bg-white transition-all duration-200',
        collapsed ? 'w-16' : 'w-52'
      )}
    >
      <div className={cn('flex items-center border-b border-zinc-100 py-3', collapsed ? 'justify-center px-2' : 'px-4')}>
        <Settings className="h-4 w-4 text-zinc-500" />
        {!collapsed && <span className="ml-2 text-sm font-semibold text-zinc-900">管理后台</span>}
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto py-2">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => onNavigate(item.key)}
            title={collapsed ? item.label : undefined}
            className={cn(
              'flex items-center rounded-md py-2 text-sm transition',
              collapsed ? 'justify-center px-2 mx-1' : 'gap-2 px-3 mx-1',
              activeKey === item.key
                ? 'bg-zinc-100 text-zinc-900 font-medium'
                : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
            )}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed && item.label}
          </button>
        ))}
      </nav>
    </aside>
  )
}

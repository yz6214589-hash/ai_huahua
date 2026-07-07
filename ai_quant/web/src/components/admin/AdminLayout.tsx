import { useState, useMemo, useCallback } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { AdminSidebar } from './AdminSidebar'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_TITLES: Record<string, string> = {
  conversations: '会话管理',
  models: '模型管理',
  tools: '工具与技能',
  agents: '智能体配置',
  prompts: '提示词管理',
  feishu: '飞书集成',
  'api-keys': 'API密钥',
  settings: '系统配置',
  logs: '日志与监控',
  schedules: '定时任务',
}

const KEY_TO_PATH: Record<string, string> = {
  conversations: '/ai-admin/conversations',
  models: '/ai-admin/models',
  tools: '/ai-admin/tools',
  agents: '/ai-admin/agents',
  prompts: '/ai-admin/prompts',
  feishu: '/ai-admin/feishu',
  'api-keys': '/ai-admin/api-keys',
  settings: '/ai-admin/settings',
  logs: '/ai-admin/monitor',
  schedules: '/ai-admin/scheduled-jobs',
}

function getActiveKey(pathname: string): string {
  const parts = pathname.replace('/ai-admin/', '').split('/')
  return parts[0] || 'conversations'
}

export default function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const activeKey = useMemo(() => getActiveKey(location.pathname), [location.pathname])
  const pageTitle = PAGE_TITLES[activeKey] || '管理后台'

  const handleNavigate = useCallback(
    (key: string) => {
      const path = KEY_TO_PATH[key]
      if (path) navigate(path)
    },
    [navigate]
  )

  return (
    <div className="flex h-screen bg-zinc-50">
      <AdminSidebar activeKey={activeKey} collapsed={sidebarCollapsed} onNavigate={handleNavigate} />
      <div className="flex flex-1 flex-col min-w-0">
        <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-2.5">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSidebarCollapsed((v) => !v)}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-400 hover:text-zinc-600"
            >
              {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            </button>
            <span className="text-sm font-medium text-zinc-600">{pageTitle}</span>
          </div>
        </div>
        <div className={cn('flex-1 overflow-y-auto p-4 md:p-6')}>
          <Outlet />
        </div>
      </div>
    </div>
  )
}

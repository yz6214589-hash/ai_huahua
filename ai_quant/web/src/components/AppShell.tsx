/**
 * 应用外壳组件
 * 提供应用的整体布局结构，包括侧边栏导航和顶部栏
 * 侧边栏可折叠，包含市场开盘状态检测和导航菜单
 */

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Brain, ChartCandlestick, ChevronLeft, ChevronRight, Download, ExternalLink, Gauge, GitBranch, Settings, Shield, Star, Target, Workflow, Zap } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import { AssistantDrawer } from '@/components/AssistantDrawer'
import { ToastContainer } from '@/components/Toast'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { memo } from 'react'

// 判断当前时间是否为中国股市开盘时间
// 开盘时间：工作日 9:30-11:30 和 13:00-15:00
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
  // 检查是否为工作日
  const isWeekday = weekday !== 'Sat' && weekday !== 'Sun'
  if (!isWeekday) return false
  // 检查上午盘（9:30-11:30）
  const amOpen = total >= 9 * 60 + 30 && total < 11 * 60 + 30
  // 检查下午盘（13:00-15:00）
  const pmOpen = total >= 13 * 60 && total < 15 * 60
  return amOpen || pmOpen
}

// 侧边栏组件，包含导航菜单和折叠功能
const Sidebar = memo(function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  // 导航菜单项配置
  const items = [
    { to: '/home', label: '首页', icon: Gauge },
    { to: '/watchlist', label: '自选股', icon: Star },
    { to: '/info-access', label: '信息获取', icon: Download },
    { to: '/strategy', label: '策略分析', icon: ChartCandlestick },
    { to: '/stock-select', label: '选股', icon: Target },
    { to: '/opportunity', label: '机会捕捉', icon: Zap },
    { to: '/ml-training', label: 'ML训练', icon: Brain },
    { to: '/risk', label: '风控中心', icon: Shield },
    { to: '/execution', label: '交易终端', icon: Workflow },
    { to: '/workflow', label: '工作流', icon: GitBranch },
  ]
  // 市场开盘状态，开盘时显示金色头像
  const [marketOpen, setMarketOpen] = useState(() => isCnMarketOpen(new Date()))

  // 每分钟检查一次市场开盘状态
  useEffect(() => {
    const timer = window.setInterval(() => {
      setMarketOpen(isCnMarketOpen(new Date()))
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [])

  // 根据开盘状态选择不同颜色的头像
  const avatarSrc = marketOpen ? '/hua-hua-avatar-gold.svg' : '/hua-hua-avatar-black.svg'

  return (
    <aside className={cn('hidden h-screen flex-col border-r border-zinc-200 bg-white transition-all duration-200 md:flex', collapsed ? 'w-20' : 'w-60')}>
      {/* Logo 和品牌区域 */}
      <div className={cn('flex items-center py-4', collapsed ? 'justify-center px-2' : 'gap-2 px-5')}>
        <img src={avatarSrc} alt="hua hua avatar" className="h-9 w-9 rounded-xl border border-zinc-200 bg-white object-cover" />
        {!collapsed ? (
          <div className="leading-tight">
            <div className="text-sm font-semibold text-zinc-900">Hua Hua</div>
            <div className="text-xs text-zinc-500">统一量化系统</div>
          </div>
        ) : null}
      </div>
      {/* 导航菜单 */}
      <nav className={cn('flex flex-1 flex-col gap-1', collapsed ? 'px-2' : 'px-3')}>
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
      {/* 底部折叠按钮 */}
      <div className={cn('flex justify-center pb-3', collapsed ? 'px-2' : 'px-3')}>
        <button
          onClick={onToggle}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-500 transition hover:border-zinc-400 hover:bg-zinc-50"
          title={collapsed ? '展开导航' : '折叠导航'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  )
})

// 顶部栏组件，包含页面标题、全局搜索和快捷操作
const Topbar = memo(function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedStock, setSelectedStock] = useState<StockSearchItem | null>(null)

  // 根据当前路由计算页面标题
  const title = useMemo(() => {
    if (location.pathname.startsWith('/home')) return '首页'
    if (location.pathname.startsWith('/info-access')) return '信息获取'
    if (location.pathname.startsWith('/reports')) return '智能研报'
    if (location.pathname.startsWith('/execution')) return '交易终端'
    if (location.pathname.startsWith('/risk')) return '风控中心'
    if (location.pathname.startsWith('/workflow')) return '工作流'
    if (location.pathname.startsWith('/strategy/backtest-history')) return '回测历史'
    if (location.pathname.startsWith('/strategy')) return '策略分析'
    if (location.pathname.startsWith('/stock-select')) return '选股'
    if (location.pathname.startsWith('/opportunity')) return '机会捕捉'
    if (location.pathname.startsWith('/watchlist')) return '自选股'
    if (location.pathname.startsWith('/performance')) return '绩效报告'
    if (location.pathname.startsWith('/ml-training')) return 'ML训练'
    if (location.pathname.startsWith('/admin')) return '管理后台'
    if (location.pathname.startsWith('/stock/')) return '个股详情'
    return '首页'
  }, [location.pathname])

  // 处理股票选择变化
  const handleStockChange = useCallback((val: StockSearchItem | StockSearchItem[] | null) => {
    setSelectedStock(val as StockSearchItem | null)
  }, [])

  // 跳转到股票详情页
  const handleViewStock = useCallback(() => {
    if (selectedStock) {
      console.log('[AppShell][Search] 跳转到个股详情页:', selectedStock.code, 'from:', location.pathname)
      console.log('[AppShell][Search] navigate 前 window.history.length =', window.history.length)
      sessionStorage.setItem('stock_detail_from', location.pathname)
      navigate(`/stock/${selectedStock.code}`)
    }
  }, [selectedStock, navigate, location.pathname])

  return (
    <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-3 md:px-6">
      {/* 左侧：页面标题和日期 */}
      <div>
        <div className="text-sm font-semibold text-zinc-900">{title}</div>
        <div className="text-xs text-zinc-500">{new Date().toLocaleDateString()}</div>
      </div>
      {/* 右侧：股票选择 + 查看详情 */}
      <div className="flex w-full items-center gap-2 md:w-auto">
        <div className="w-full md:w-72">
          <StockPicker
            value={selectedStock}
            onChange={handleStockChange}
            mode="single"
            placeholder="搜索股票代码或名称"
          />
        </div>
        <button
          onClick={handleViewStock}
          disabled={!selectedStock}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ExternalLink className="h-4 w-4" />
          查看
        </button>
      </div>
    </header>
  )
})

// 应用外壳主组件，整合侧边栏、顶部栏和页面内容
export default function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // 切换侧边栏折叠状态
  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((v) => !v)
  }, [])

  return (
    /** 外层容器固定为视口高度，隐藏溢出，防止全页滚动 */
    <div className="h-screen overflow-hidden bg-zinc-50">
      <div className="flex h-full">
        {/* 侧边栏，可折叠（固定左侧） */}
        <Sidebar collapsed={sidebarCollapsed} onToggle={handleToggleSidebar} />
        {/* 主内容区域 */}
        <div className="flex flex-1 flex-col min-w-0">
          <Topbar />
          {/* 页面内容，通过路由 Outlet 渲染（可滚动区域） */}
          <main className="flex-1 overflow-y-auto px-4 pb-6 md:px-6 min-w-0">
            <Outlet />
          </main>
        </div>
      </div>
      {/* AI 助手抽屉组件 */}
      <AssistantDrawer />
      {/* Toast 通知 */}
      <ToastContainer />
    </div>
  )
}

import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'

const navItems = [
  { to: '/login', label: '连接页' },
  { to: '/dashboard', label: '账户总览' },
  { to: '/task/new', label: '新建执行任务' },
  { to: '/execution', label: '执行监控' },
  { to: '/research', label: '训练与回测' },
]

export default function AppShell() {
  return (
    <div className="min-h-full bg-gradient-to-b from-[#0b1220] to-[#070b14]">
      <div className="mx-auto w-full max-w-[1200px] px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[#4c7dff] to-[#20c997]" />
            <div className="flex flex-col">
              <div className="text-[15px] font-semibold">数字员工 - 交易官 Ethan</div>
              <div className="text-xs text-[#9fb0d0]">
                交易执行终端 / 实盘 MiniQMT / 智能拆单 / 训练与回测闭环
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-[#1f2c4d] px-3 py-1 text-xs text-[#9fb0d0]">
              AI 编排：langgraph
            </span>
            <span className="rounded-full border border-[#1f2c4d] px-3 py-1 text-xs text-[#9fb0d0]">
              后端：FastAPI
            </span>
            <span className="rounded-full border border-[#1f2c4d] px-3 py-1 text-xs text-[#9fb0d0]">
              前端：React
            </span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              className={({ isActive }) =>
                clsx(
                  'rounded-xl border px-3 py-2 text-sm',
                  isActive
                    ? 'border-[#2b4ea6] bg-[rgba(76,125,255,.18)] text-[#eaf0ff]'
                    : 'border-[#1f2c4d] bg-[rgba(15,26,51,.7)] text-[#eaf0ff]',
                )
              }
            >
              {it.label}
            </NavLink>
          ))}
        </div>

        <div className="mt-4">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

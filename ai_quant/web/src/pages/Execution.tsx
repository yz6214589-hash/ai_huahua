import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useState, useEffect, useCallback, createContext, useContext } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Link, Unlink, RefreshCcw } from 'lucide-react'

/* ============================================================
 *  类型定义
 * ============================================================ */

/** 账户列表返回格式 */
interface AccountsResponse {
  accounts: Record<string, { account_id: string; connected: boolean }>
  default: string
}

/** 连接接口返回格式 */
interface ConnectResponse {
  ok: boolean
  connected: boolean
  account_id: string
  account_type: string
  session_id: number
}

/** TradingContext 提供的数据 */
interface TradingContextValue {
  /** 当前连接的账户名 */
  connectedAccount: string | null
  /** 当前连接的账户名（别名） */
  accountType: string | null
  /** 当前账户ID */
  accountId: string | null
  /** 断开连接函数 */
  disconnect: () => void
  /** 所有账户列表 */
  accounts: Record<string, { account_id: string; connected: boolean }>
  /** 刷新数据回调 */
  onRefresh: (() => void) | null
  /** 设置刷新回调 */
  setRefreshCallback: (cb: (() => void) | null) => void
}

/* ============================================================
 *  Context & Hook
 * ============================================================ */

const TradingContext = createContext<TradingContextValue>({
  connectedAccount: null,
  accountType: null,
  accountId: null,
  disconnect: () => {},
  accounts: {},
  onRefresh: null,
  setRefreshCallback: () => {},
})

/** 供子页面使用的 hook，获取交易连接状态 */
export function useTrading() {
  return useContext(TradingContext)
}

/* ============================================================
 *  Tab 配置（移除模拟盘）
 * ============================================================ */

const TABS = [
  { key: 'positions', label: '账户持仓', path: '/execution/positions' },
  { key: 'tasks', label: '执行任务', path: '/execution/tasks' },
  { key: 'records', label: '交易记录', path: '/execution/records' },
]

/* ============================================================
 *  主组件
 * ============================================================ */

export default function Execution() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = TABS.find((t) => location.pathname.startsWith(t.path))?.key || 'positions'

  /* ----- 状态：账户 & 连接 ----- */
  const [accounts, setAccounts] = useState<Record<string, { account_id: string; connected: boolean }>>({})
  const [defaultAccount, setDefaultAccount] = useState<string>('')
  const [selectedAccount, setSelectedAccount] = useState<string>('')
  const [connectedAccount, setConnectedAccount] = useState<string | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [accountsLoading, setAccountsLoading] = useState(true)
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [switchHint, setSwitchHint] = useState<string | null>(null)

  /* 子页面的刷新回调 */
  const [refreshCallback, setRefreshCallback] = useState<(() => void) | null>(null)

  /* ============================================================
   *  加载账户列表
   * ============================================================ */
  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true)
    setAccountsError(null)
    try {
      const data = await fetchJson<AccountsResponse>('/api/v1/trading/accounts')
      setAccounts(data.accounts || {})
      setDefaultAccount(data.default || '')
      // 如果当前没有选中账户，则自动选中 default
      if (!selectedAccount && data.default) {
        setSelectedAccount(data.default)
      }
      // 检查是否有已连接的账户，同步状态
      for (const [name, info] of Object.entries(data.accounts || {})) {
        if (info.connected) {
          setConnectedAccount(name)
          setAccountId(info.account_id)
          break
        }
      }
    } catch (e) {
      setAccountsError(e instanceof Error ? e.message : '获取账户列表失败')
    } finally {
      setAccountsLoading(false)
    }
  }, [selectedAccount])

  /* ============================================================
   *  连接
   * ============================================================ */
  const handleConnect = useCallback(async () => {
    if (!selectedAccount) return
    setConnecting(true)
    setAccountsError(null)
    try {
      const res = await postJson<ConnectResponse>(
        `/api/v1/trading/connect?account_type=${encodeURIComponent(selectedAccount)}`,
        {}
      )
      setConnectedAccount(res.account_type || selectedAccount)
      setAccountId(res.account_id || null)
      // 连接成功后再次确认账户状态
      try {
        const data = await fetchJson<AccountsResponse>('/api/v1/trading/accounts')
        setAccounts(data.accounts || {})
      } catch {
        // 确认状态失败不影响连接结果
      }
    } catch (e) {
      setAccountsError(e instanceof Error ? e.message : '连接失败')
    } finally {
      setConnecting(false)
    }
  }, [selectedAccount])

  /* ============================================================
   *  断开连接
   * ============================================================ */
  const handleDisconnect = useCallback(async () => {
    if (!connectedAccount) return
    try {
      await postJson(
        `/api/v1/trading/disconnect?account_type=${encodeURIComponent(connectedAccount)}`,
        {}
      )
    } catch {
      // 即使后端报错，前端也重置为未连接状态
    }
    setConnectedAccount(null)
    setAccountId(null)
  }, [connectedAccount])

  /* ============================================================
   *  刷新（通知子页面）
   * ============================================================ */
  const handleRefresh = useCallback(() => {
    if (refreshCallback) {
      refreshCallback()
    }
  }, [refreshCallback])

  /* ============================================================
   *  下拉框切换
   * ============================================================ */
  const handleAccountChange = (value: string) => {
    if (connectedAccount) {
      setSwitchHint('请先断开当前连接再切换账户')
      setTimeout(() => setSwitchHint(null), 3000)
      return
    }
    setSelectedAccount(value)
  }

  /* ============================================================
   *  页面初始化：加载账户列表
   * ============================================================ */
  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  /* ============================================================
   *  Context 值
   * ============================================================ */
  const contextValue: TradingContextValue = {
    connectedAccount,
    accountType: connectedAccount,
    accountId,
    disconnect: handleDisconnect,
    accounts,
    onRefresh: refreshCallback,
    setRefreshCallback,
  }

  /* ============================================================
   *  账户连接组件（Tab 栏右侧）
   * ============================================================ */
  const accountKeys = Object.keys(accounts)

  const renderAccountConnector = () => {
    // 账户列表加载中
    if (accountsLoading) {
      return (
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-transparent" />
          加载账户...
        </div>
      )
    }

    // 已连接状态
    if (connectedAccount) {
      return (
        <div className="flex items-center gap-2">
          {/* 蓝色小标签：显示当前连接信息 */}
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 border border-blue-200">
            <Link className="h-3 w-3" />
            当前连接: {connectedAccount}
            <span className="text-blue-500">(账号: {accountId ?? '--'})</span>
          </span>

          {/* 刷新按钮 */}
          <button
            onClick={handleRefresh}
            title="刷新数据"
            className="inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white p-1.5 text-zinc-500 transition hover:bg-zinc-50 hover:text-zinc-700"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
          </button>

          {/* 断开按钮 */}
          <button
            onClick={handleDisconnect}
            className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs text-red-600 transition hover:bg-red-50"
          >
            <Unlink className="h-3.5 w-3.5" />
            断开
          </button>
        </div>
      )
    }

    // 未连接状态
    return (
      <div className="flex items-center gap-2">
        {/* 下拉框 */}
        <select
          value={selectedAccount}
          onChange={(e) => handleAccountChange(e.target.value)}
          className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-700 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        >
          {accountKeys.length === 0 && (
            <option value="">暂无可用账户</option>
          )}
          {accountKeys.map((key) => (
            <option key={key} value={key}>
              {key} ({accounts[key].account_id})
            </option>
          ))}
        </select>

        {/* 连接按钮 */}
        <button
          onClick={handleConnect}
          disabled={connecting || !selectedAccount}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {connecting ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              连接中...
            </>
          ) : (
            <>
              <Link className="h-3.5 w-3.5" />
              连接
            </>
          )}
        </button>

        {/* 错误提示 */}
        {accountsError && (
          <span className="text-xs text-red-500">{accountsError}</span>
        )}

        {/* 切换提示 */}
        {switchHint && (
          <span className="text-xs text-amber-600">{switchHint}</span>
        )}
      </div>
    )
  }

  /* ============================================================
   *  渲染
   * ============================================================ */
  return (
    <TradingContext.Provider value={contextValue}>
      <div className="flex h-full flex-col">
        {/* Tab 栏 + 右侧账户连接组件 */}
        <div className="flex-shrink-0 border-b border-zinc-200 bg-white">
          <div className="flex items-center justify-between">
            {/* 左侧 Tab */}
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

            {/* 右侧账户连接组件 */}
            <div className="pr-2">
              {renderAccountConnector()}
            </div>
          </div>
        </div>

        {/* 子页面 */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <Outlet />
        </div>
      </div>
    </TradingContext.Provider>
  )
}

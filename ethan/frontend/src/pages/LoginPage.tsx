import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'

type TradingState = { connected: boolean }

export default function LoginPage() {
  const [state, setState] = useState<TradingState>({ connected: false })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setErr(null)
    try {
      const s = await apiGet<TradingState>('/api/trading/state')
      setState(s)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function connect() {
    setBusy(true)
    setErr(null)
    try {
      await apiPost('/api/trading/connect')
      await refresh()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    setErr(null)
    try {
      await apiPost('/api/trading/disconnect')
      await refresh()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="text-sm font-semibold">连接状态</div>
        <div className="mt-3 flex items-center justify-between rounded-xl border border-[#1f2c4d] p-3">
          <div className="flex items-center gap-3">
            <div
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: state.connected ? '#20c997' : '#ff4d6d' }}
            />
            <div>
              <div className="font-semibold">MiniQMT 交易连接</div>
              <div className="text-xs text-[#9fb0d0]">
                {state.connected ? '已连接' : '未连接：请配置 QMT_PATH / ACCOUNT_ID 环境变量并连接'}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={refresh}
              className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
              disabled={busy}
            >
              刷新
            </button>
            {state.connected ? (
              <button
                type="button"
                onClick={disconnect}
                className="rounded-xl bg-[#ff4d6d] px-3 py-2 text-sm font-semibold text-white"
                disabled={busy}
              >
                断开
              </button>
            ) : (
              <button
                type="button"
                onClick={connect}
                className="rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
                disabled={busy}
              >
                连接与校验
              </button>
            )}
          </div>
        </div>

        {err ? <div className="mt-3 text-xs text-[#ff4d6d]">{err}</div> : null}
      </div>

      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="text-sm font-semibold">说明</div>
        <div className="mt-2 text-xs leading-6 text-[#9fb0d0]">
          <div>后端默认地址：{`${window.location.protocol}//${window.location.hostname || '127.0.0.1'}:8001`}</div>
          <div>前端可通过 VITE_ETHAN_API_BASE 覆盖后端地址</div>
          <div>实盘连接依赖 xtquant + 已启动登录的 MiniQMT 客户端</div>
        </div>
      </div>
    </div>
  )
}

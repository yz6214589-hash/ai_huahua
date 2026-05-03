import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'

type Asset = { total_asset?: number; cash?: number; market_value?: number; frozen_cash?: number }
type Position = {
  stock_code: string
  volume: number
  can_use_volume?: number
  open_price?: number
  market_value?: number
}
type EventRow = { ts: string; type: string; message: string; data: Record<string, unknown> }

export default function DashboardPage() {
  const [asset, setAsset] = useState<Asset | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [events, setEvents] = useState<EventRow[]>([])
  const [connected, setConnected] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function refreshAll() {
    setErr(null)
    try {
      const s = await apiGet<{ connected: boolean }>('/api/trading/state')
      setConnected(s.connected)
      if (!s.connected) {
        setAsset(null)
        setPositions([])
        setEvents([])
        return
      }
      const [a, p, e] = await Promise.all([
        apiGet<Asset>('/api/trading/asset'),
        apiGet<{ items: Position[] }>('/api/trading/positions'),
        apiGet<{ items: EventRow[] }>('/api/trading/events?limit=50'),
      ])
      setAsset(a)
      setPositions(p.items)
      setEvents(e.items)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    refreshAll()
  }, [])

  async function connect() {
    setErr(null)
    try {
      await apiPost('/api/trading/connect')
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">账户总览</div>
          <div className="mt-1 text-xs text-[#9fb0d0]">连接：MiniQMT {connected ? '已连接' : '未连接'}</div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
            onClick={refreshAll}
          >
            刷新
          </button>
          {!connected ? (
            <button
              type="button"
              className="rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
              onClick={connect}
            >
              连接
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {[
          { k: '可用资金', v: asset?.cash },
          { k: '总资产', v: asset?.total_asset },
          { k: '市值', v: asset?.market_value },
        ].map((it) => (
          <div key={it.k} className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
            <div className="text-xs text-[#9fb0d0]">{it.k}</div>
            <div className="mt-1 text-lg font-extrabold">{it.v ?? '--'}</div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="text-sm font-semibold">持仓</div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[780px] border-separate border-spacing-y-2 text-sm">
            <thead className="text-xs text-[#9fb0d0]">
              <tr>
                <th className="text-left font-semibold">标的</th>
                <th className="text-left font-semibold">持仓数量</th>
                <th className="text-left font-semibold">可用</th>
                <th className="text-left font-semibold">成本价</th>
                <th className="text-left font-semibold">市值</th>
              </tr>
            </thead>
            <tbody>
              {positions.length ? (
                positions.map((p) => (
                  <tr key={p.stock_code}>
                    <td className="rounded-l-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{p.stock_code}</td>
                    <td className="border-y border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{p.volume}</td>
                    <td className="border-y border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{p.can_use_volume ?? '--'}</td>
                    <td className="border-y border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{p.open_price ?? '--'}</td>
                    <td className="rounded-r-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{p.market_value ?? '--'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-[#9fb0d0]" colSpan={5}>
                    {connected ? '暂无持仓' : '未连接'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="text-sm font-semibold">事件流</div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[900px] border-separate border-spacing-y-2 text-sm">
            <thead className="text-xs text-[#9fb0d0]">
              <tr>
                <th className="text-left font-semibold">时间</th>
                <th className="text-left font-semibold">类型</th>
                <th className="text-left font-semibold">消息</th>
              </tr>
            </thead>
            <tbody>
              {events.length ? (
                events
                  .slice()
                  .reverse()
                  .map((e, idx) => (
                    <tr key={`${e.ts}-${idx}`}>
                      <td className="rounded-l-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{e.ts}</td>
                      <td className="border-y border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{e.type}</td>
                      <td className="rounded-r-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2">{e.message}</td>
                    </tr>
                  ))
              ) : (
                <tr>
                  <td className="rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-[#9fb0d0]" colSpan={3}>
                    {connected ? '暂无事件' : '未连接'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {err ? <div className="text-xs text-[#ff4d6d]">{err}</div> : null}
    </div>
  )
}

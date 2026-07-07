import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCw, Plus, DollarSign, TrendingUp, TrendingDown, Wallet, BarChart3, AlertTriangle } from 'lucide-react'

interface SimAccount {
  id: number
  account_name: string
  initial_capital: number
  current_capital: number
  total_asset: number
  status: string
  description?: string
  created_at?: string
}

interface SimPosition {
  id: number
  stock_code: string
  stock_name: string
  volume: number
  available_volume: number
  cost_price: number
  current_price?: number
  market_value?: number
  profit_loss?: number
  profit_loss_ratio?: number
}

interface SimTrade {
  id: number
  trade_no: string
  stock_code: string
  stock_name: string
  side: string
  price: number
  volume: number
  amount: number
  commission: number
  trade_time: string
  strategy?: string
}

export default function SimAccount() {
  const [accounts, setAccounts] = useState<SimAccount[]>([])
  const [positions, setPositions] = useState<SimPosition[]>([])
  const [trades, setTrades] = useState<SimTrade[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'positions' | 'trades'>('positions')
  const [showTradeForm, setShowTradeForm] = useState(false)
  const [tradeForm, setTradeForm] = useState({
    stock_code: '',
    stock_name: '',
    side: 'buy',
    price: 0,
    volume: 0,
  })
  const [activeAccountId, setActiveAccountId] = useState(1)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accData, posData, tradeData] = await Promise.all([
        fetchJson<{ accounts: SimAccount[] }>('/api/v1/sim-account/list'),
        fetchJson<{ positions: SimPosition[] }>(`/api/v1/sim-account/positions/${activeAccountId}`),
        fetchJson<{ trades: SimTrade[] }>(`/api/v1/sim-account/trades/${activeAccountId}`),
      ])
      if (accData.accounts?.length > 0) setAccounts(accData.accounts)
      if (posData.positions) setPositions(posData.positions)
      if (tradeData.trades) setTrades(tradeData.trades)
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setAccounts([])
      setPositions([])
      setTrades([])
    } finally {
      setLoading(false)
    }
  }, [activeAccountId])

  useEffect(() => { loadData() }, [loadData])

  const handleTrade = async () => {
    try {
      await postJson('/api/v1/sim-account/trade', {
        account_id: activeAccountId,
        ...tradeForm,
        price: Number(tradeForm.price),
        volume: Number(tradeForm.volume),
      })
      setShowTradeForm(false)
      setTradeForm({ stock_code: '', stock_name: '', side: 'buy', price: 0, volume: 0 })
      await loadData()
    } catch {
      //
    }
  }

  const activeAccount = accounts.find(a => a.id === activeAccountId) || accounts[0]
  const totalPL = positions.reduce((s, p) => s + (p.profit_loss || 0), 0)
  const totalMV = positions.reduce((s, p) => s + (p.market_value || 0), 0)

  if (loading && accounts.length === 0) {
    return <Loading className="py-20" />
  }

  if (error && accounts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">{error}</p>
        <button
          onClick={loadData}
          className="mt-3 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          重新加载
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">模拟盘</h1>
          <p className="text-sm text-zinc-500 mt-1">模拟交易账户管理与执行</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTradeForm(!showTradeForm)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            <Plus className="w-4 h-4" />
            模拟交易
          </button>
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      {activeAccount && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card>
            <CardBody>
              <div className="flex items-center gap-2 mb-1">
                <Wallet className="w-4 h-4 text-zinc-400" />
                <span className="text-xs text-zinc-500">{activeAccount.account_name}</span>
              </div>
              <div className="text-2xl font-semibold text-zinc-900">
                {(activeAccount.total_asset || 0).toLocaleString()}
              </div>
              <div className="text-xs text-zinc-500 mt-1">总资产</div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <div className="text-xs text-zinc-500">可用资金</div>
              <div className="mt-1 text-2xl font-semibold text-zinc-900">
                {(activeAccount.current_capital || 0).toLocaleString()}
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <div className="text-xs text-zinc-500">持仓市值</div>
              <div className="mt-1 text-2xl font-semibold text-zinc-900">
                {totalMV.toLocaleString()}
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <div className="text-xs text-zinc-500">浮动盈亏</div>
              <div className={`mt-1 text-2xl font-semibold ${totalPL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {totalPL >= 0 ? '+' : ''}{totalPL.toLocaleString()}
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {showTradeForm && (
        <Card>
          <CardHeader><h3 className="text-lg font-semibold">模拟交易下单</h3></CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">股票代码</label>
                <input
                  type="text"
                  value={tradeForm.stock_code}
                  onChange={e => setTradeForm(f => ({ ...f, stock_code: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  placeholder="如 600519.SH"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">股票名称</label>
                <input
                  type="text"
                  value={tradeForm.stock_name}
                  onChange={e => setTradeForm(f => ({ ...f, stock_name: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  placeholder="如 贵州茅台"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">方向</label>
                <select
                  value={tradeForm.side}
                  onChange={e => setTradeForm(f => ({ ...f, side: e.target.value }))}
                  className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                >
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">价格</label>
                <input
                  type="number"
                  value={tradeForm.price || ''}
                  onChange={e => setTradeForm(f => ({ ...f, price: Number(e.target.value) }))}
                  className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">数量</label>
                <input
                  type="number"
                  value={tradeForm.volume || ''}
                  onChange={e => setTradeForm(f => ({ ...f, volume: Number(e.target.value) }))}
                  className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleTrade}
                  className="w-full rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
                >
                  提交订单
                </button>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-semibold">持仓与交易</h3>
            <div className="flex gap-1">
              <button
                onClick={() => setActiveTab('positions')}
                className={`rounded px-3 py-1 text-xs font-medium transition ${
                  activeTab === 'positions' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
                }`}
              >
                持仓
              </button>
              <button
                onClick={() => setActiveTab('trades')}
                className={`rounded px-3 py-1 text-xs font-medium transition ${
                  activeTab === 'trades' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
                }`}
              >
                交易记录
              </button>
            </div>
          </div>
        </CardHeader>
        <CardBody>
          {activeTab === 'positions' && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200">
                <thead>
                  <tr className="text-left text-xs font-medium text-zinc-500 uppercase">
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">持仓量</th>
                    <th className="px-3 py-2">成本价</th>
                    <th className="px-3 py-2">现价</th>
                    <th className="px-3 py-2">市值</th>
                    <th className="px-3 py-2">盈亏</th>
                    <th className="px-3 py-2">盈亏率</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 text-sm">
                  {positions.map(pos => (
                    <tr key={pos.id} className="hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <div className="font-medium text-zinc-900">{pos.stock_name}</div>
                        <div className="text-xs text-zinc-500">{pos.stock_code}</div>
                      </td>
                      <td className="px-3 py-2 text-zinc-900">{pos.volume}</td>
                      <td className="px-3 py-2 text-zinc-900">{pos.cost_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-zinc-900">{pos.current_price?.toFixed(2) || '—'}</td>
                      <td className="px-3 py-2 text-zinc-900">{pos.market_value?.toLocaleString() || '—'}</td>
                      <td className={`px-3 py-2 font-medium ${(pos.profit_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(pos.profit_loss || 0) >= 0 ? '+' : ''}{pos.profit_loss?.toLocaleString() || '—'}
                      </td>
                      <td className={`px-3 py-2 font-medium ${(pos.profit_loss_ratio || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(pos.profit_loss_ratio || 0) >= 0 ? '+' : ''}{pos.profit_loss_ratio?.toFixed(2) || '—'}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {positions.length === 0 && (
                <div className="py-8 text-center text-sm text-zinc-500">暂无持仓</div>
              )}
            </div>
          )}
          {activeTab === 'trades' && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200">
                <thead>
                  <tr className="text-left text-xs font-medium text-zinc-500 uppercase">
                    <th className="px-3 py-2">时间</th>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">方向</th>
                    <th className="px-3 py-2">价格</th>
                    <th className="px-3 py-2">数量</th>
                    <th className="px-3 py-2">金额</th>
                    <th className="px-3 py-2">手续费</th>
                    <th className="px-3 py-2">策略</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 text-sm">
                  {trades.map(trade => (
                    <tr key={trade.id} className="hover:bg-zinc-50">
                      <td className="px-3 py-2 text-xs text-zinc-500">{trade.trade_time}</td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-zinc-900">{trade.stock_name}</div>
                        <div className="text-xs text-zinc-500">{trade.stock_code}</div>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                          trade.side === 'buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {trade.side === 'buy' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {trade.side === 'buy' ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-zinc-900">{trade.price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-zinc-900">{trade.volume}</td>
                      <td className="px-3 py-2 text-zinc-900">{trade.amount.toLocaleString()}</td>
                      <td className="px-3 py-2 text-zinc-500">{trade.commission.toFixed(2)}</td>
                      <td className="px-3 py-2 text-xs text-zinc-500">{trade.strategy || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {trades.length === 0 && (
                <div className="py-8 text-center text-sm text-zinc-500">暂无交易记录</div>
              )}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
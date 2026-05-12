import { useEffect, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Play, RefreshCcw } from 'lucide-react'

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: string; label: string; help: string
    min?: number; max?: number; step?: number; default?: number
  }>
  default_params: Record<string, unknown>
}

interface StrategyInstance {
  instance_id: string
  strategy_id: string
  name: string
  params: Record<string, unknown>
}

interface BacktestResult {
  metrics: { initial_nav: number; final_nav: number; total_return: number; num_trades: number; win_rate: number }
  trades: Array<{ date: string; action: string; price: number; qty: number; cost?: number; proceeds?: number; note?: string }>
  nav_log: Array<{ date: string; nav: number }>
  strategy_id: string
  stock_code: string
  start_date: string
  end_date: string
}

function MetricCard({ label, value, unit = '', tone }: { label: string; value: string | number; unit?: string; tone?: 'up' | 'down' | 'neutral' }) {
  const cls = tone === 'up' ? 'text-red-600' : tone === 'down' ? 'text-green-600' : 'text-zinc-900'
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
      <div className={`text-2xl font-bold ${cls}`}>{value}{unit}</div>
      <div className="mt-1 text-xs text-zinc-500">{label}</div>
    </div>
  )
}

export default function StrategyBacktest() {
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [instances, setInstances] = useState<StrategyInstance[]>([])
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [running, setRunning] = useState(false)

  const [mode, setMode] = useState<'instance' | 'strategy'>('instance')
  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [selectedStrategyId, setSelectedStrategyId] = useState('')
  const [overrideParams, setOverrideParams] = useState<Record<string, string>>({})
  const [stockCode, setStockCode] = useState('600519.SH')
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')

  useEffect(() => {
    Promise.all([
      fetchJson<{ strategies: StrategyDef[] }>('/api/analysis/strategies'),
      fetchJson<{ instances: StrategyInstance[] }>('/api/analysis/strategy-instances'),
    ]).then(([s, i]) => {
      setStrategies(s.strategies || [])
      setInstances(i.instances || [])
      if (s.strategies?.length) setSelectedStrategyId(s.strategies[0].strategy_id)
    }).catch((e) => toast('error', e instanceof Error ? e.message : String(e)))
  }, [])

  const currentInstance = instances.find((x) => x.instance_id === selectedInstanceId)
  const currentStrategy = strategies.find((s) => s.strategy_id === (currentInstance?.strategy_id || selectedStrategyId))

  useEffect(() => {
    if (currentInstance) {
      const params: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentInstance.params)) {
        params[k] = String(v)
      }
      setOverrideParams(params)
      setSelectedStrategyId(currentInstance.strategy_id)
    }
  }, [selectedInstanceId])

  useEffect(() => {
    if (!currentInstance && currentStrategy) {
      const params: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentStrategy.default_params)) {
        params[k] = String(v)
      }
      setOverrideParams(params)
    }
  }, [selectedStrategyId, currentInstance])

  const run = async () => {
    if (!stockCode.trim()) {
      toast('error', '请输入股票代码')
      return
    }
    setRunning(true)
    try {
      const strategyId = currentInstance?.strategy_id || selectedStrategyId
      if (!strategyId) {
        toast('error', '请选择策略')
        return
      }
      const params: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(overrideParams)) {
        const meta = currentStrategy?.params_schema?.[k]
        if (!meta) continue
        if (meta.type === 'int') params[k] = parseInt(String(v), 10)
        else if (meta.type === 'float') params[k] = parseFloat(String(v))
        else params[k] = v
      }
      const r = await postJson<BacktestResult>('/api/analysis/backtest/run', {
        stock_code: stockCode.trim(),
        start: startDate,
        end: endDate,
        strategy_id: strategyId,
        params,
      })
      setResult(r)
      toast('success', '回测完成')
    } catch (e) {
      toast('error', `回测失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRunning(false)
    }
  }

  const stratName = currentStrategy?.name || selectedStrategyId
  const totalReturn = result?.metrics?.total_return ?? 0
  const returnTone = totalReturn > 0 ? 'up' : totalReturn < 0 ? 'down' : 'neutral'

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="回测参数" />
        <CardBody>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-1.5 text-sm">
                <input type="radio" checked={mode === 'instance'} onChange={() => setMode('instance')} className="accent-zinc-900" />
                从实例选择
              </label>
              <label className="flex items-center gap-1.5 text-sm">
                <input type="radio" checked={mode === 'strategy'} onChange={() => setMode('strategy')} className="accent-zinc-900" />
                直接选策略
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {mode === 'instance' ? (
                <div>
                  <div className="mb-1 text-xs text-zinc-500">策略实例</div>
                  <select
                    value={selectedInstanceId}
                    onChange={(e) => setSelectedInstanceId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="">— 请选择实例 —</option>
                    {instances.map((inst) => (
                      <option key={inst.instance_id} value={inst.instance_id}>
                        {inst.name}（{strategies.find((s) => s.strategy_id === inst.strategy_id)?.name || inst.strategy_id}）
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <div className="mb-1 text-xs text-zinc-500">策略</div>
                  <select
                    value={selectedStrategyId}
                    onChange={(e) => setSelectedStrategyId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    {strategies.map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <div className="mb-1 text-xs text-zinc-500">股票代码</div>
                <input
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  placeholder="例如：600519.SH"
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div>
                <div className="mb-1 text-xs text-zinc-500">开始日期</div>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>

              <div>
                <div className="mb-1 text-xs text-zinc-500">结束日期</div>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>
            </div>

            {currentStrategy && Object.keys(currentStrategy.params_schema).length > 0 && (
              <div>
                <div className="mb-2 text-xs font-semibold text-zinc-900">参数覆盖</div>
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(currentStrategy.params_schema).map(([key, meta]) => (
                    <div key={key}>
                      <div className="mb-1 text-xs text-zinc-500">{meta.label}</div>
                      <input
                        type={meta.type === 'int' || meta.type === 'float' ? 'number' : 'text'}
                        value={overrideParams[key] ?? String(meta.default ?? '')}
                        onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                        min={meta.min}
                        max={meta.max}
                        step={meta.step}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={run}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running ? '回测中…' : '开始回测'}
            </button>
          </div>
        </CardBody>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <MetricCard label="初始资金" value={result.metrics.initial_nav.toLocaleString()} unit="元" />
            <MetricCard label="最终资金" value={result.metrics.final_nav.toLocaleString()} unit="元" />
            <MetricCard label="总收益率" value={`${totalReturn > 0 ? '+' : ''}${totalReturn.toFixed(2)}`} unit="%" tone={returnTone} />
            <MetricCard label="交易次数" value={result.metrics.num_trades} />
            <MetricCard label="胜率" value={`${result.metrics.win_rate.toFixed(1)}`} unit="%" />
          </div>

          <Card>
            <CardHeader title={`交易记录（{result.trades.length} 笔）`} />
            <CardBody className="p-0">
              {result.trades.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-zinc-500">无交易记录</div>
              ) : (
                <div className="max-h-80 overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-zinc-50 text-xs text-zinc-500">
                      <tr>
                        <th className="px-4 py-2">日期</th>
                        <th className="px-4 py-2">方向</th>
                        <th className="px-4 py-2">价格</th>
                        <th className="px-4 py-2">数量</th>
                        <th className="px-4 py-2">金额</th>
                        <th className="px-4 py-2">备注</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trades.map((t, i) => (
                        <tr key={i} className="border-t border-zinc-100">
                          <td className="px-4 py-2 text-xs text-zinc-700">{t.date}</td>
                          <td className="px-4 py-2">
                            <Badge tone={t.action === 'buy' ? 'green' : 'red'}>
                              {t.action === 'buy' ? '买入' : '卖出'}
                            </Badge>
                          </td>
                          <td className="px-4 py-2 text-zinc-900">{t.price}</td>
                          <td className="px-4 py-2 text-zinc-700">{t.qty}</td>
                          <td className="px-4 py-2 text-zinc-700">
                            {t.action === 'buy' ? `-${
                              t.cost != null ? t.cost.toLocaleString() : '—'
                            }` : `+${
                              t.proceeds != null ? t.proceeds.toLocaleString() : '—'
                            }`}
                          </td>
                          <td className="px-4 py-2 text-xs text-zinc-400">{t.note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}

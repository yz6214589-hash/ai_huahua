/**
 * 滚动验证（Walk-Forward）组件
 * 支持配置训练/测试窗口参数，运行滚动验证，展示结果
 */
import { useState, useEffect } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Play } from 'lucide-react'

/* ---------- 数据类型 ---------- */

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'object'
    label: string; help: string
    min?: number; max?: number; step?: number
    default?: number | string | boolean
    values?: string[]
  }>
  default_params: Record<string, unknown>
}

interface StrategyInstance {
  instance_id: string
  strategy_id: string
  name: string
  params: Record<string, unknown>
}

interface WFWindow {
  window_index: number
  train_start: string
  train_end: string
  test_start: string
  test_end: string
  train_metrics: Record<string, unknown>
  test_metrics: Record<string, unknown>
}

interface WFStability {
  win_rate: number
  avg_return: number
  std_return: number
}

interface WFResult {
  windows: WFWindow[]
  stability: WFStability
  aggregated_metrics: Record<string, unknown>
}

/* ---------- 主组件 ---------- */

export default function WalkForwardPanel() {
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [instances, setInstances] = useState<StrategyInstance[]>([])

  // 配置参数
  const [mode, setMode] = useState<'instance' | 'strategy'>('instance')
  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [selectedStrategyId, setSelectedStrategyId] = useState('')
  const [stockCode, setStockCode] = useState('600519.SH')
  const [startDate, setStartDate] = useState('2018-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [trainYears, setTrainYears] = useState(3)
  const [testYears, setTestYears] = useState(1)
  const [stepYears, setStepYears] = useState(1)
  const [wfMode, setWfMode] = useState<'rolling' | 'anchored'>('rolling')

  // 结果
  const [result, setResult] = useState<WFResult | null>(null)
  const [running, setRunning] = useState(false)
  const [overrideParams, setOverrideParams] = useState<Record<string, string>>({})

  useEffect(() => {
    Promise.all([
      fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies'),
      fetchJson<{ instances: StrategyInstance[] }>('/api/v1/analysis/strategy-instances'),
    ]).then(([s, i]) => {
      setStrategies(s.strategies || [])
      setInstances(i.instances || [])
      if (s.strategies?.length) setSelectedStrategyId(s.strategies[0].strategy_id)
    }).catch((e) => toast('error', e instanceof Error ? e.message : String(e)))
  }, [])

  const currentInstance = instances.find((x) => x.instance_id === selectedInstanceId)
  const currentStrategy = strategies.find((s) => s.strategy_id === (currentInstance?.strategy_id || selectedStrategyId))

  // 当策略切换且非实例模式时，自动填充默认参数
  useEffect(() => {
    if (!currentInstance && currentStrategy) {
      const params: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentStrategy.default_params)) {
        params[k] = String(v)
      }
      setOverrideParams(params)
    }
  }, [selectedStrategyId, currentInstance])

  /** 运行滚动验证 */
  const runWalkForward = async () => {
    if (!stockCode.trim()) {
      toast('error', '请输入股票代码')
      return
    }
    const strategyId = currentInstance?.strategy_id || selectedStrategyId
    if (!strategyId) {
      toast('error', '请选择策略')
      return
    }
    if (!startDate || !endDate) {
      toast('error', '请选择开始和结束日期')
      return
    }
    if (startDate >= endDate) {
      toast('error', '结束日期必须晚于开始日期')
      return
    }

    setRunning(true)
    try {
      // 构建参数
      const params: Record<string, unknown> = {}
      if (currentInstance) {
        for (const [k, v] of Object.entries(currentInstance.params)) {
          params[k] = v
        }
      } else if (currentStrategy) {
        for (const [k, v] of Object.entries(overrideParams)) {
          const schema = currentStrategy.params_schema[k]
          if (schema) {
            if (schema.type === 'int') params[k] = parseInt(v, 10)
            else if (schema.type === 'float') params[k] = parseFloat(v)
            else if (schema.type === 'bool') params[k] = v === 'true'
            else if (schema.type === 'enum') params[k] = String(v)
            else if (schema.type === 'object') {
              try { params[k] = JSON.parse(v) }
              catch { params[k] = {} }
            }
            else params[k] = v
          }
        }
      }

      const res = await postJson<WFResult>('/api/v1/analysis/backtest/walk-forward', {
        stock_code: stockCode.trim(),
        start: startDate,
        end: endDate,
        strategy_id: strategyId,
        params,
        train_years: trainYears,
        test_years: testYears,
        step_years: stepYears,
        mode: wfMode,
      })
      setResult(res)
      toast('success', '滚动验证完成')
    } catch (e) {
      toast('error', `滚动验证失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRunning(false)
    }
  }

  /** 格式化百分比 */
  const fmtPct = (val: unknown) => {
    if (val == null) return '—'
    const n = Number(val)
    if (isNaN(n)) return '—'
    return `${(n * 100).toFixed(2)}%`
  }

  /** 格式化数值 */
  const fmtNum = (val: unknown, decimals = 3) => {
    if (val == null) return '—'
    const n = Number(val)
    if (isNaN(n)) return '—'
    return n.toFixed(decimals)
  }

  return (
    <div className="space-y-4">
      {/* 配置区 */}
      <Card>
        <CardHeader title="滚动验证配置" />
        <CardBody>
          <div className="space-y-4">
            {/* 策略选择 */}
            <div className="flex items-center gap-4">
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

              {/* 策略参数输入 */}
              {mode === 'strategy' && currentStrategy && Object.keys(currentStrategy.params_schema).length > 0 && (
                <div className="col-span-1 md:col-span-2">
                  <div className="mb-2 text-xs font-semibold text-zinc-900">策略参数</div>
                  <div className="grid grid-cols-3 gap-3">
                    {Object.entries(currentStrategy.params_schema).map(([key, meta]) => (
                      <div key={key}>
                        <div className="mb-1 text-xs text-zinc-500">{meta.label} <span className="text-zinc-400">({key})</span></div>
                        {meta.type === 'bool' ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={overrideParams[key] === 'true'}
                              onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: String(e.target.checked) }))}
                              className="h-4 w-4 accent-zinc-900"
                            />
                            <span className="text-xs text-zinc-500">
                              {overrideParams[key] === 'true' ? '开启' : '关闭'}
                            </span>
                          </div>
                        ) : meta.type === 'enum' ? (
                          <select
                            value={overrideParams[key] ?? ''}
                            onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          >
                            {meta.values?.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        ) : meta.type === 'object' ? (
                          <textarea
                            value={overrideParams[key] ?? '{}'}
                            onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                            rows={2}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-mono outline-none focus:border-zinc-400"
                            placeholder='{"key": "value"}'
                          />
                        ) : (
                          <input
                            type="number"
                            value={overrideParams[key] ?? String(meta.default ?? '')}
                            onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                            min={meta.min}
                            max={meta.max}
                            step={meta.step}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        )}
                      </div>
                    ))}
                  </div>
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

            {/* 滚动参数 */}
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
              <div className="mb-2 text-xs font-semibold text-zinc-900">滚动参数</div>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                <div>
                  <div className="mb-1 text-xs text-zinc-500">训练窗口（年）</div>
                  <input
                    type="number"
                    value={trainYears}
                    onChange={(e) => setTrainYears(parseInt(e.target.value) || 1)}
                    min={1}
                    max={10}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">测试窗口（年）</div>
                  <input
                    type="number"
                    value={testYears}
                    onChange={(e) => setTestYears(parseInt(e.target.value) || 1)}
                    min={1}
                    max={5}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">步进（年）</div>
                  <input
                    type="number"
                    value={stepYears}
                    onChange={(e) => setStepYears(parseInt(e.target.value) || 1)}
                    min={1}
                    max={5}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">模式</div>
                  <select
                    value={wfMode}
                    onChange={(e) => setWfMode(e.target.value as 'rolling' | 'anchored')}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="rolling">滚动（Rolling）</option>
                    <option value="anchored">锚定（Anchored）</option>
                  </select>
                </div>
              </div>
            </div>

            <button
              onClick={runWalkForward}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running ? '验证中...' : '开始滚动验证'}
            </button>
          </div>
        </CardBody>
      </Card>

      {/* 结果展示 */}
      {result && (
        <>
          {/* 稳定性指标 */}
          <Card>
            <CardHeader title="稳定性指标" />
            <CardBody>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-zinc-900">{((result.stability?.win_rate ?? 0) * 100).toFixed(1)}%</div>
                  <div className="mt-1 text-xs text-zinc-500">胜率</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-zinc-900">{fmtPct(result.stability?.avg_return)}</div>
                  <div className="mt-1 text-xs text-zinc-500">平均收益</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-zinc-900">{fmtNum(result.stability?.std_return)}</div>
                  <div className="mt-1 text-xs text-zinc-500">收益标准差</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-green-600">{result.windows?.length ?? 0}</div>
                  <div className="mt-1 text-xs text-zinc-500">正收益窗口</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-zinc-900">{result.windows?.length ?? 0}</div>
                  <div className="mt-1 text-xs text-zinc-500">总窗口数</div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* 各窗口对比表格 */}
          <Card>
            <CardHeader title="各窗口训练/测试指标对比" />
            <CardBody className="p-0">
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                    <tr>
                      <th className="px-4 py-2" rowSpan={2}>窗口</th>
                      <th className="px-4 py-2" colSpan={2}>时间范围</th>
                      <th className="px-4 py-2 border-l border-zinc-200" colSpan={4}>训练集</th>
                      <th className="px-4 py-2 border-l border-zinc-200" colSpan={4}>测试集</th>
                    </tr>
                    <tr>
                      <th className="px-4 py-2 bg-zinc-50">训练期</th>
                      <th className="px-4 py-2 bg-zinc-50">测试期</th>
                      <th className="px-4 py-2 border-l border-zinc-200">收益率</th>
                      <th className="px-4 py-2">夏普</th>
                      <th className="px-4 py-2">回撤</th>
                      <th className="px-4 py-2">胜率</th>
                      <th className="px-4 py-2 border-l border-zinc-200">收益率</th>
                      <th className="px-4 py-2">夏普</th>
                      <th className="px-4 py-2">回撤</th>
                      <th className="px-4 py-2">胜率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result.windows ?? []).map((w) => {
                      const testReturn = Number(w.test_metrics?.total_return || 0)
                      const returnTone = testReturn > 0 ? 'text-red-600' : testReturn < 0 ? 'text-green-600' : 'text-zinc-900'
                      return (
                        <tr key={w.window_index} className="border-t border-zinc-100">
                          <td className="px-4 py-2 font-medium text-zinc-900">{w.window_index}</td>
                          <td className="px-4 py-2 text-xs text-zinc-500">{w.train_start} ~ {w.train_end}</td>
                          <td className="px-4 py-2 text-xs text-zinc-500">{w.test_start} ~ {w.test_end}</td>
                          <td className="px-4 py-2 border-l border-zinc-200">{fmtPct(w.train_metrics?.total_return)}</td>
                          <td className="px-4 py-2">{fmtNum(w.train_metrics?.sharpe)}</td>
                          <td className="px-4 py-2 text-green-600">{fmtPct(w.train_metrics?.max_drawdown)}</td>
                          <td className="px-4 py-2">{fmtPct(w.train_metrics?.win_rate)}</td>
                          <td className={`px-4 py-2 border-l border-zinc-200 font-medium ${returnTone}`}>{fmtPct(w.test_metrics?.total_return)}</td>
                          <td className="px-4 py-2">{fmtNum(w.test_metrics?.sharpe)}</td>
                          <td className="px-4 py-2 text-green-600">{fmtPct(w.test_metrics?.max_drawdown)}</td>
                          <td className="px-4 py-2">{fmtPct(w.test_metrics?.win_rate)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}

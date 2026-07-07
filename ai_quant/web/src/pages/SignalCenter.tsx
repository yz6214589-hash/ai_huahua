import { useState, useEffect, useCallback } from 'react'
import { Loading } from '@/components/Loading'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCw, TrendingUp, TrendingDown, Filter, Plus, Settings, X, Star, ChevronUp, ChevronDown, BarChart3, AlertTriangle } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

interface SignalItem {
  id: string
  stock_code: string
  stock_name: string
  signal_type: string
  strength: number
  score: number
  macd?: number
  rsi?: number
  ma20?: number
  close: number
  reason: string
  trade_date: string
  created_at: string
}

interface RuleCondition {
  indicator: string
  operator: string
  threshold_value: number
}

interface SignalRule {
  id: string
  name: string
  description?: string
  enabled: boolean
  conditions?: RuleCondition[]
  logic?: string
}

const INDICATOR_OPTIONS = [
  { value: 'rsi', label: 'RSI' },
  { value: 'macd', label: 'MACD' },
  { value: 'close', label: '收盘价' },
  { value: 'ma20', label: 'MA20' },
  { value: 'volume', label: '成交量' },
  { value: 'kdj_k', label: 'KDJ-K' },
  { value: 'kdj_d', label: 'KDJ-D' },
  { value: 'kdj_j', label: 'KDJ-J' },
]

const OPERATOR_OPTIONS = [
  { value: 'gt', label: '大于' },
  { value: 'lt', label: '小于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lte', label: '小于等于' },
  { value: 'eq', label: '等于' },
  { value: 'cross_above', label: '上穿' },
  { value: 'cross_below', label: '下穿' },
]

function StarRating({ strength }: { strength: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${i <= strength ? 'fill-yellow-400 text-yellow-400' : 'fill-none text-zinc-200'}`}
        />
      ))}
    </span>
  )
}

function RuleModal({
  open,
  rule,
  onSave,
  onClose,
}: {
  open: boolean
  rule?: SignalRule | null
  onSave: (rule: any) => void
  onClose: () => void
}) {
  const [name, setName] = useState(rule?.name || '')
  const [description, setDescription] = useState(rule?.description || '')
  const [logic, setLogic] = useState(rule?.logic || 'AND')
  const [conditions, setConditions] = useState<RuleCondition[]>(rule?.conditions || [{ indicator: 'rsi', operator: 'lt', threshold_value: 30 }])

  useEffect(() => {
    if (open) {
      setName(rule?.name || '')
      setDescription(rule?.description || '')
      setLogic(rule?.logic || 'AND')
      setConditions(rule?.conditions || [{ indicator: 'rsi', operator: 'lt', threshold_value: 30 }])
    }
  }, [open, rule])

  if (!open) return null

  const addCondition = () => {
    setConditions([...conditions, { indicator: 'rsi', operator: 'lt', threshold_value: 30 }])
  }

  const updateCondition = (index: number, field: keyof RuleCondition, value: string | number) => {
    const updated = conditions.map((c, i) => i === index ? { ...c, [field]: value } : c)
    setConditions(updated)
  }

  const removeCondition = (index: number) => {
    setConditions(conditions.filter((_, i) => i !== index))
  }

  const handleSave = () => {
    onSave({ name, description, logic, conditions, enabled: rule?.enabled ?? true })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-zinc-900">{rule ? '编辑规则' : '新建规则'}</h3>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-zinc-100"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">规则名称</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              placeholder="输入规则名称"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">规则描述</label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              placeholder="输入规则描述"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-2">条件逻辑组合</label>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setLogic('AND')}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${logic === 'AND' ? 'bg-zinc-900 text-white' : 'border border-zinc-200 text-zinc-600 hover:bg-zinc-50'}`}
              >所有条件满足(AND)</button>
              <button
                onClick={() => setLogic('OR')}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${logic === 'OR' ? 'bg-zinc-900 text-white' : 'border border-zinc-200 text-zinc-600 hover:bg-zinc-50'}`}
              >任一条件满足(OR)</button>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-zinc-700">条件列表</label>
              <button
                onClick={addCondition}
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                <Plus className="h-3 w-3" /> 添加条件
              </button>
            </div>
            <div className="space-y-2">
              {conditions.map((cond, i) => (
                <div key={i} className="flex items-center gap-2 rounded-lg border border-zinc-200 p-2">
                  <select
                    value={cond.indicator}
                    onChange={e => updateCondition(i, 'indicator', e.target.value)}
                    className="rounded border border-zinc-200 px-2 py-1 text-xs focus:outline-none"
                  >
                    {INDICATOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <select
                    value={cond.operator}
                    onChange={e => updateCondition(i, 'operator', e.target.value)}
                    className="rounded border border-zinc-200 px-2 py-1 text-xs focus:outline-none"
                  >
                    {OPERATOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <input
                    type="number"
                    value={cond.threshold_value}
                    onChange={e => updateCondition(i, 'threshold_value', Number(e.target.value))}
                    className="w-20 rounded border border-zinc-200 px-2 py-1 text-xs focus:outline-none"
                  />
                  <button onClick={() => removeCondition(i)} className="rounded p-1 text-zinc-400 hover:text-red-500">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50">取消</button>
          <button onClick={handleSave} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">保存</button>
        </div>
      </div>
    </div>
  )
}

function SignalDetailModal({ signal, onClose }: { signal: SignalItem | null; onClose: () => void }) {
  const [klineData, setKlineData] = useState<{
    dates: string[]
    kline: number[][]
    volumes: number[]
    ma5: number[]
    ma10: number[]
  } | null>(null)
  const [klineLoading, setKlineLoading] = useState(false)

  useEffect(() => {
    if (!signal) return
    setKlineLoading(true)
    postJson<{
      dates: string[]
      kline: number[][]
      volumes: number[]
      ma5: number[]
      ma10: number[]
    }>('/api/v1/trading/kline', { stock_code: signal.stock_code, days: 20 })
      .then(data => {
        setKlineData(data)
      })
      .catch(() => {
        setKlineData(null)
      })
      .finally(() => setKlineLoading(false))
  }, [signal])

  if (!signal) return null

  const option = klineData ? {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['K线', 'MA5', 'MA10'], bottom: 0 },
    grid: [{ left: '10%', right: '8%', top: '10%', height: '55%' }, { left: '10%', right: '8%', bottom: '15%', height: '15%' }],
    xAxis: [
      { type: 'category', data: klineData.dates, gridIndex: 0, axisLabel: { show: true }, axisLine: { lineStyle: { color: '#d1d5db' } } },
      { type: 'category', data: klineData.dates, gridIndex: 1, axisLabel: { show: true }, axisLine: { lineStyle: { color: '#d1d5db' } } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#f3f4f6' } } },
      { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false } },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: klineData.kline, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' },
      },
      { name: 'MA5', type: 'line', data: klineData.ma5, xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 1 } },
      { name: 'MA10', type: 'line', data: klineData.ma10, xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { color: '#a855f7', width: 1 } },
      {
        name: '成交量', type: 'bar', data: klineData.volumes, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: (params: any) => {
          const k = klineData.kline[params.dataIndex]
          return k ? (k[1] >= k[0] ? '#22c55e' : '#ef4444') : '#22c55e'
        }},
      },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
  } : null

  const isBuy = signal.signal_type === 'BUY'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-3xl rounded-xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-base font-semibold text-zinc-900">{signal.stock_name}</h3>
            <span className="text-xs text-zinc-500">{signal.stock_code}</span>
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${isBuy ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {isBuy ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {isBuy ? '买入' : '卖出'}
            </span>
          </div>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-zinc-100"><X className="h-4 w-4" /></button>
        </div>
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">信号强度</div>
            <StarRating strength={signal.strength} />
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">综合评分</div>
            <div className="text-sm font-semibold text-zinc-900">{signal.score}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">RSI(14)</div>
            <div className="text-sm font-semibold text-zinc-900">{signal.rsi?.toFixed(1)}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">MACD</div>
            <div className={`text-sm font-semibold ${(signal.macd ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>{signal.macd?.toFixed(2)}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">收盘价</div>
            <div className="text-sm font-semibold text-zinc-900">{signal.close.toFixed(2)}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">MA20</div>
            <div className="text-sm font-semibold text-zinc-900">{signal.ma20?.toFixed(2)}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">信号日期</div>
            <div className="text-sm font-semibold text-zinc-900">{signal.trade_date}</div>
          </div>
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="text-xs text-zinc-500">信号原因</div>
            <div className="text-sm text-zinc-900">{signal.reason}</div>
          </div>
        </div>
        <div className="h-[400px]">
          {klineLoading ? (
            <div className="flex items-center justify-center h-full text-zinc-400">加载K线数据...</div>
          ) : option ? (
            <ReactECharts option={option} style={{ height: '100%' }} />
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-400">K线数据暂不可用</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function SignalCenter() {
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [rules, setRules] = useState<SignalRule[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<'ALL' | 'BUY' | 'SELL'>('ALL')
  const [filterStock, setFilterStock] = useState('')
  const [sortField, setSortField] = useState<'trade_date' | 'strength' | 'score'>('trade_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [showRules, setShowRules] = useState(false)
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<SignalRule | null>(null)
  const [detailSignal, setDetailSignal] = useState<SignalItem | null>(null)
  const [generating, setGenerating] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [signalData, rulesData] = await Promise.all([
        fetchJson<{ items: SignalItem[]; total: number }>('/api/v1/signals'),
        fetchJson<SignalRule[]>('/api/v1/signals/rules'),
      ])
      // 后端 Decimal 字段以字符串形式返回（如 "close":"680.4100"），
      // 在边界处统一转换为 number，避免 .toFixed() 在 render 阶段抛错导致整棵组件树被卸载。
      const toNum = (v: unknown): number => {
        if (v === null || v === undefined || v === '') return 0
        const n = typeof v === 'number' ? v : Number(v)
        return Number.isFinite(n) ? n : 0
      }
      const normalized = (signalData.items || []).map(s => ({
        ...s,
        close: toNum(s.close),
        score: toNum(s.score),
        strength: toNum(s.strength),
        macd: s.macd === null || s.macd === undefined || s.macd === '' ? undefined : toNum(s.macd),
        rsi: s.rsi === null || s.rsi === undefined || s.rsi === '' ? undefined : toNum(s.rsi),
        ma20: s.ma20 === null || s.ma20 === undefined || s.ma20 === '' ? undefined : toNum(s.ma20),
      }))
      if (normalized.length > 0) setSignals(normalized)
      else setSignals([])
      if (rulesData.length > 0) setRules(rulesData)
      else setRules([])
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setSignals([])
      setRules([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const filteredSignals = signals
    .filter(s => {
      if (filterType !== 'ALL' && s.signal_type !== filterType) return false
      if (filterStock && !s.stock_name.includes(filterStock) && !s.stock_code.includes(filterStock)) return false
      return true
    })
    .sort((a, b) => {
      const mul = sortDir === 'asc' ? 1 : -1
      if (sortField === 'strength') return (a.strength - b.strength) * mul
      if (sortField === 'score') return (a.score - b.score) * mul
      return a.trade_date.localeCompare(b.trade_date) * mul
    })

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const SortIcon = ({ field }: { field: typeof sortField }) => {
    if (sortField !== field) return null
    return sortDir === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await postJson('/api/v1/signals/generate', { use_rules: true })
      await loadData()
    } catch {
      //
    } finally {
      setGenerating(false)
    }
  }

  const handleSaveRule = async (ruleData: any) => {
    try {
      if (editingRule) {
        await fetchJson(`/api/v1/signals/rules/${editingRule.id}`, {
          method: 'PUT',
          body: JSON.stringify(ruleData),
        })
      } else {
        await postJson('/api/v1/signals/rules', ruleData)
      }
      setRuleModalOpen(false)
      setEditingRule(null)
      const rulesData = await fetchJson<SignalRule[]>('/api/v1/signals/rules')
      if (rulesData.length > 0) setRules(rulesData)
    } catch {
      //
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    try {
      await fetchJson(`/api/v1/signals/rules/${ruleId}`, { method: 'DELETE' })
      setRules(rules.filter(r => r.id !== ruleId))
    } catch {
      //
    }
  }

  const handleToggleRule = async (rule: SignalRule) => {
    try {
      await fetchJson(`/api/v1/signals/rules/${rule.id}`, {
        method: 'PUT',
        body: JSON.stringify({ ...rule, enabled: !rule.enabled }),
      })
      setRules(rules.map(r => r.id === rule.id ? { ...r, enabled: !r.enabled } : r))
    } catch {
      //
    }
  }

  const stats = {
    buy: signals.filter(s => s.signal_type === 'BUY').length,
    sell: signals.filter(s => s.signal_type === 'SELL').length,
    highScore: signals.filter(s => s.score >= 80).length,
    strongSignal: signals.filter(s => s.strength >= 4).length,
  }

  if (loading && signals.length === 0) {
    return <Loading className="py-20" />
  }

  if (error && signals.length === 0) {
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
          <h1 className="text-lg font-semibold text-zinc-900">信号中心</h1>
          <p className="text-xs text-zinc-500 mt-0.5">基于技术指标的买卖信号管理</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            <BarChart3 className="w-4 h-4" />
            生成信号
          </button>
          <button
            onClick={() => setShowRules(!showRules)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            <Settings className="w-4 h-4" />
            规则配置
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card><CardBody>
          <div className="text-xs text-zinc-500">买入信号</div>
          <div className="mt-1 text-2xl font-semibold text-green-600">{stats.buy}</div>
        </CardBody></Card>
        <Card><CardBody>
          <div className="text-xs text-zinc-500">卖出信号</div>
          <div className="mt-1 text-2xl font-semibold text-red-600">{stats.sell}</div>
        </CardBody></Card>
        <Card><CardBody>
          <div className="text-xs text-zinc-500">{'高分信号(>=80)'}</div>
          <div className="mt-1 text-2xl font-semibold text-zinc-900">{stats.highScore}</div>
        </CardBody></Card>
        <Card><CardBody>
          <div className="text-xs text-zinc-500">{'强信号(>=4级)'}</div>
          <div className="mt-1 text-2xl font-semibold text-zinc-900">{stats.strongSignal}</div>
        </CardBody></Card>
      </div>

      {showRules && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">信号规则配置</h3>
              <button
                onClick={() => { setEditingRule(null); setRuleModalOpen(true) }}
                className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
              >
                <Plus className="w-3 h-3" /> 新建规则
              </button>
            </div>
          </CardHeader>
          <CardBody>
            <div className="space-y-2">
              {rules.map(rule => (
                <div key={rule.id} className="flex items-center justify-between rounded-lg border border-zinc-200 p-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-900">{rule.name}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${rule.enabled ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                        {rule.enabled ? '已启用' : '已停用'}
                      </span>
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600">{rule.logic || 'AND'}</span>
                    </div>
                    {rule.description && <div className="text-xs text-zinc-500 mt-0.5">{rule.description}</div>}
                    {rule.conditions && rule.conditions.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {rule.conditions.map((c, i) => (
                          <span key={i} className="inline-flex items-center rounded bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">
                            {INDICATOR_OPTIONS.find(o => o.value === c.indicator)?.label || c.indicator} {OPERATOR_OPTIONS.find(o => o.value === c.operator)?.label || c.operator} {c.threshold_value}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-3">
                    <label className="relative inline-flex cursor-pointer items-center">
                      <input type="checkbox" className="peer sr-only" checked={rule.enabled} onChange={() => handleToggleRule(rule)} />
                      <div className="h-5 w-9 rounded-full bg-zinc-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-zinc-900 peer-checked:after:translate-x-full" />
                    </label>
                    <button onClick={() => { setEditingRule(rule); setRuleModalOpen(true) }} className="rounded p-1 text-xs text-zinc-400 hover:text-zinc-700">编辑</button>
                    <button onClick={() => handleDeleteRule(rule.id)} className="rounded p-1 text-xs text-zinc-400 hover:text-red-500">删除</button>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold">信号列表</h3>
            <div className="flex items-center gap-2">
              <Filter className="w-3 h-3 text-zinc-400" />
              <select
                value={filterType}
                onChange={e => setFilterType(e.target.value as any)}
                className="rounded border border-zinc-200 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900"
              >
                <option value="ALL">全部</option>
                <option value="BUY">买入</option>
                <option value="SELL">卖出</option>
              </select>
              <input
                type="text"
                placeholder="搜索股票"
                value={filterStock}
                onChange={e => setFilterStock(e.target.value)}
                className="w-32 rounded border border-zinc-200 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium text-zinc-500 uppercase">
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3">信号类型</th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('strength')}>
                    <span className="inline-flex items-center gap-1">强度 <SortIcon field="strength" /></span>
                  </th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('score')}>
                    <span className="inline-flex items-center gap-1">评分 <SortIcon field="score" /></span>
                  </th>
                  <th className="px-4 py-3">收盘价</th>
                  <th className="px-4 py-3">RSI</th>
                  <th className="px-4 py-3">MACD</th>
                  <th className="px-4 py-3">原因</th>
                  <th className="px-4 py-3 cursor-pointer select-none" onClick={() => toggleSort('trade_date')}>
                    <span className="inline-flex items-center gap-1">生成时间 <SortIcon field="trade_date" /></span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredSignals.map(signal => (
                  <tr
                    key={signal.id}
                    className="cursor-pointer transition hover:bg-zinc-50"
                    onClick={() => setDetailSignal(signal)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-zinc-900">{signal.stock_name}</div>
                      <div className="text-xs text-zinc-500">{signal.stock_code}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                        signal.signal_type === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {signal.signal_type === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {signal.signal_type === 'BUY' ? '买入' : '卖出'}
                      </span>
                    </td>
                    <td className="px-4 py-3"><StarRating strength={signal.strength} /></td>
                    <td className="px-4 py-3">
                      <Badge variant={signal.score >= 80 ? 'success' : signal.score >= 60 ? 'warning' : 'default'}>
                        {signal.score}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-zinc-900">{signal.close.toFixed(2)}</td>
                    <td className="px-4 py-3 text-zinc-900">{signal.rsi?.toFixed(1)}</td>
                    <td className={`px-4 py-3 font-medium ${(signal.macd ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {signal.macd?.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500 max-w-[200px] truncate">{signal.reason}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500 whitespace-nowrap">{signal.trade_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredSignals.length === 0 && (
              <div className="py-8 text-center text-sm text-zinc-500">暂无匹配的信号数据</div>
            )}
          </div>
        </CardBody>
      </Card>

      <RuleModal
        open={ruleModalOpen}
        rule={editingRule}
        onSave={handleSaveRule}
        onClose={() => { setRuleModalOpen(false); setEditingRule(null) }}
      />
      <SignalDetailModal signal={detailSignal} onClose={() => setDetailSignal(null)} />
    </div>
  )
}
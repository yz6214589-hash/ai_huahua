import { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'select' | 'object'
    label: string; help: string
    min?: number; max?: number; step?: number
    default?: number | string | boolean
    values?: string[]
    options?: { value: string; label: string }[]
    section?: string
    show_if?: { field: string; value: string | boolean }
  }>
  default_params: Record<string, unknown>
}

interface StrategyInstance {
  instance_id: string
  strategy_id: string
  name: string
  params: Record<string, unknown>
}

// section 渐变色映射
const SECTION_GRADIENT: Record<string, string> = {
  '行情判别': 'from-blue-700 to-blue-600',
  '趋势买入': 'from-emerald-700 to-emerald-600',
  '趋势卖出': 'from-red-700 to-red-600',
  '震荡买入': 'from-amber-700 to-amber-600',
  '震荡卖出': 'from-orange-700 to-orange-600',
  '过渡买入': 'from-violet-700 to-violet-600',
  '过渡卖出': 'from-purple-700 to-purple-600',
  '通用止损': 'from-zinc-700 to-zinc-600',
}

function getSectionGradient(sectionName: string): string {
  return SECTION_GRADIENT[sectionName] || 'from-zinc-700 to-zinc-600'
}

export default function StrategyInstanceCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlStrategyId = searchParams.get('strategy_id')

  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [loading, setLoading] = useState(false)
  const [formStrategyId, setFormStrategyId] = useState('')
  const [formName, setFormName] = useState('')
  const [formParams, setFormParams] = useState<Record<string, string>>({})
  // 记录用户是否手动编辑过实例名称
  const nameEditedByUser = useRef(false)

  // 行情预览相关状态
  const [showPreview, setShowPreview] = useState(false)
  const [previewIndex, setPreviewIndex] = useState('000300.SH')
  const [previewStart, setPreviewStart] = useState('2026-01-01')
  const [previewEnd, setPreviewEnd] = useState('2026-05-31')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewData, setPreviewData] = useState<{
    dates: string[]
    closes: number[]
    indicator_values: (number | null)[]
    indicator_name: string
    market_types: string[]
    stock_name: string
  } | null>(null)
  const [indices, setIndices] = useState<Array<{ stock_code: string; stock_name: string }>>([])

  // 折叠区域
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({
    '趋势买入': true, '趋势卖出': true, '震荡买入': true, '震荡卖出': true, '过渡买入': true, '过渡卖出': true,
  })
  const toggleSection = (name: string) => {
    setCollapsedSections((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  const currentStrategy = strategies.find((s) => s.strategy_id === formStrategyId)

  /** 根据策略名称和参数值自动生成实例名 */
  const generateAutoName = (sid: string, params: Record<string, string>) => {
    const def = strategies.find((s) => s.strategy_id === sid)
    if (!def) return ''
    const paramValues = Object.values(params)
      .filter((v) => v !== '' && v !== undefined && v !== null)
      .join('_')
    return paramValues ? `${def.name}_${paramValues}` : def.name
  }

  // 当策略或参数变化时，自动生成实例名称（仅当用户未手动编辑时）
  useEffect(() => {
    if (!nameEditedByUser.current) {
      setFormName(generateAutoName(formStrategyId, formParams))
    }
  }, [formStrategyId, formParams])

  const handleStrategyChange = (sid: string, allStrategies?: StrategyDef[]) => {
    nameEditedByUser.current = false
    setFormStrategyId(sid)
    const src = allStrategies || strategies
    const def = src.find((s) => s.strategy_id === sid)
    if (def) {
      const p: Record<string, string> = {}
      for (const [k, v] of Object.entries(def.default_params)) {
        p[k] = String(v ?? '')
      }
      setFormParams(p)
    }
  }

  // 加载策略列表和指数列表
  const loadStrategies = async () => {
    setLoading(true)
    try {
      const [s, idx] = await Promise.all([
        fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies'),
        fetchJson<{ indices: Array<{ stock_code: string; stock_name: string }> }>('/api/v1/analysis/indices'),
      ])
      setStrategies(s.strategies || [])
      setIndices(idx.indices || [])
      // 如果 URL 中携带了 strategy_id，自动选中该策略
      if (urlStrategyId && s.strategies?.find((st) => st.strategy_id === urlStrategyId)) {
        setFormName('')
        handleStrategyChange(urlStrategyId, s.strategies)
      } else if (s.strategies?.length > 0) {
        handleStrategyChange(s.strategies[0].strategy_id, s.strategies)
      }
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStrategies() }, [])

  const submit = async () => {
    if (!formStrategyId || !formName.trim()) {
      toast('error', '请填写策略和实例名称')
      return
    }
    const def = strategies.find((s) => s.strategy_id === formStrategyId)
    if (!def) return
    const params: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(formParams)) {
      if (k in (def.params_schema || {})) {
        const meta = def.params_schema[k]
        if (meta.type === 'int') params[k] = parseInt(String(v), 10)
        else if (meta.type === 'float') params[k] = parseFloat(String(v))
        else if (meta.type === 'bool') params[k] = v === 'true'
        else if (meta.type === 'enum') params[k] = String(v)
        else if (meta.type === 'object') {
          try { params[k] = JSON.parse(String(v)) }
          catch { params[k] = {} }
        } else params[k] = v
      }
    }
    try {
      await postJson('/api/v1/analysis/strategy-instances', { strategy_id: formStrategyId, name: formName.trim(), params })
      toast('success', `实例「${formName}」创建成功`)
      nameEditedByUser.current = false
      navigate('/strategy/instances')
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    }
  }

  // 行情预览请求
  const loadPreview = async () => {
    if (!currentStrategy) return
    setPreviewLoading(true)
    try {
      const detectorParams: Record<string, unknown> = {
        stock_code: previewIndex,
        start_date: previewStart,
        end_date: previewEnd,
        detector_type: formParams.detector_type || 'adx',
      }
      // 传入当前行情判别参数
      if (formParams.detector_type === 'adx' || !formParams.detector_type) {
        detectorParams.adx_period = parseInt(formParams.adx_period || '14')
        detectorParams.adx_trend_threshold = parseFloat(formParams.adx_trend_threshold || '25')
        detectorParams.adx_range_threshold = parseFloat(formParams.adx_range_threshold || '20')
      } else if (formParams.detector_type === 'ma') {
        detectorParams.det_ma_fast = parseInt(formParams.det_ma_fast || '10')
        detectorParams.det_ma_slow = parseInt(formParams.det_ma_slow || '30')
      } else if (formParams.detector_type === 'boll') {
        detectorParams.det_boll_period = parseInt(formParams.det_boll_period || '20')
        detectorParams.det_boll_devfactor = parseFloat(formParams.det_boll_devfactor || '2')
      }
      const data = await postJson<typeof previewData>('/api/v1/analysis/market-preview', detectorParams)
      setPreviewData(data)
    } catch (e) {
      toast('error', e instanceof Error ? e.message : '行情预览加载失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* 面包屑导航 */}
      <div className="mb-4 flex items-center gap-2 text-sm">
        <button onClick={() => navigate('/strategy/instances')} className="text-zinc-500 hover:text-zinc-700">策略实例</button>
        <span className="text-zinc-400">/</span>
        <span className="text-zinc-900 font-medium">新建实例</span>
      </div>

      <Card>
        <CardHeader title="新建策略实例" />
        <CardBody>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1 text-xs text-zinc-500">所属策略</div>
                <select
                  value={formStrategyId}
                  onChange={(e) => handleStrategyChange(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                >
                  {strategies.map((s) => (
                    <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">实例名称</div>
                <input
                  value={formName}
                  onChange={(e) => {
                    nameEditedByUser.current = true
                    setFormName(e.target.value)
                  }}
                  placeholder="自动生成策略名称_参数值"
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>
            </div>
            {currentStrategy && Object.keys(currentStrategy.params_schema).length > 0 && (() => {
              const schema = currentStrategy.params_schema

              const isVisible = (key: string) => {
                const meta = schema[key]
                if (!meta?.show_if) return true
                const { field, value } = meta.show_if
                const currentVal = formParams[field]
                if (typeof value === 'boolean') {
                  return (currentVal === 'true') === value
                }
                return currentVal === value
              }

              const sections: Record<string, Array<[string, typeof schema[string]]>> = {}
              const noSection: Array<[string, typeof schema[string]]> = []

              for (const [key, meta] of Object.entries(schema)) {
                if (!isVisible(key)) continue
                if (meta.section) {
                  if (!sections[meta.section]) sections[meta.section] = []
                  sections[meta.section].push([key, meta])
                } else {
                  noSection.push([key, meta])
                }
              }

              const renderParam = (key: string, meta: typeof schema[string]) => (
                <div key={key}>
                  <div className="mb-1 text-xs text-zinc-500">{meta.label} <span className="text-zinc-400">({key})</span></div>
                  {meta.type === 'bool' ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={formParams[key] === 'true'}
                        onChange={(e) => setFormParams((p) => ({ ...p, [key]: String(e.target.checked) }))}
                        className="h-4 w-4 accent-zinc-900"
                      />
                      <span className="text-xs text-zinc-500">{formParams[key] === 'true' ? '开启' : '关闭'}</span>
                    </div>
                  ) : meta.type === 'select' ? (
                    <select
                      value={String(formParams[key] ?? meta.options?.[0]?.value ?? '')}
                      onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                      className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    >
                      {(meta.options || []).map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  ) : meta.type === 'enum' ? (
                    <select
                      value={formParams[key] ?? ''}
                      onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                      className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    >
                      {meta.values?.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  ) : meta.type === 'object' ? (
                    <textarea
                      value={formParams[key] ?? '{}'}
                      onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                      rows={2}
                      className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-mono outline-none focus:border-zinc-400"
                      placeholder='{"key": "value"}'
                    />
                  ) : (
                    <input
                      type="number"
                      value={formParams[key] ?? String(meta.default ?? '')}
                      onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                      min={meta.min}
                      max={meta.max}
                      step={meta.step}
                      className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    />
                  )}
                  <div className="mt-0.5 text-xs text-zinc-400">{meta.help}</div>
                </div>
              )

              const sectionOrder = ['行情判别', '趋势买入', '趋势卖出', '震荡买入', '震荡卖出', '过渡买入', '过渡卖出', '通用止损']

              const sortedSections = Object.entries(sections).sort((a, b) => {
                const idxA = sectionOrder.indexOf(a[0])
                const idxB = sectionOrder.indexOf(b[0])
                if (idxA === -1 && idxB === -1) return 0
                if (idxA === -1) return 1
                if (idxB === -1) return -1
                return idxA - idxB
              })

              const isSectionCollapsed = (name: string) => collapsedSections[name] === true

              return (
                <div className="space-y-3">
                  <div className="mb-2 text-xs font-semibold text-zinc-900">参数配置</div>
                  {noSection.length > 0 && (
                    <div className="grid grid-cols-2 gap-3">
                      {noSection.map(([key, meta]) => renderParam(key, meta))}
                    </div>
                  )}
                  {sortedSections.map(([sectionName, params]) => {
                    const collapsed = isSectionCollapsed(sectionName)
                    return (
                      <div key={sectionName} className="rounded-lg border border-zinc-100 bg-zinc-50/50">
                        <div className="flex items-center gap-2 px-3 py-2">
                          <button type="button" onClick={() => toggleSection(sectionName)} className="flex items-center gap-1.5">
                            {collapsed ? <ChevronRight className="h-3.5 w-3.5 text-zinc-400" /> : <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />}
                          </button>
                          <span className={`inline-flex items-center rounded-md bg-gradient-to-r ${getSectionGradient(sectionName)} px-2.5 py-1 text-xs font-semibold text-white shadow-sm`}>
                            {sectionName}
                          </span>
                          <span className="text-xs text-zinc-400">{params.length} 项</span>
                          {sectionName === '行情判别' && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setShowPreview(true); setPreviewData(null) }}
                              className="ml-auto rounded border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-50"
                            >
                              行情预览
                            </button>
                          )}
                        </div>
                        {!collapsed && (
                          <div className="grid grid-cols-2 gap-3 px-3 pb-3">
                            {params.map(([key, meta]) => renderParam(key, meta))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })()}
            <div className="flex gap-2">
              <button onClick={submit} className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">
                <Plus className="h-4 w-4" />
                保存实例
              </button>
              <button onClick={() => navigate('/strategy/instances')} className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                取消
              </button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* 行情预览模态框 */}
      {showPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowPreview(false)}>
          <div className="relative mx-4 max-h-[85vh] w-full max-w-4xl overflow-auto rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-zinc-900">行情预览</h3>
              <button onClick={() => setShowPreview(false)} className="text-zinc-400 hover:text-zinc-600">✕</button>
            </div>

            {/* 输入区域 */}
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <div>
                <div className="mb-1 text-xs text-zinc-500">股票指数</div>
                <select
                  value={previewIndex}
                  onChange={(e) => setPreviewIndex(e.target.value)}
                  className="rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
                >
                  {indices.map((idx) => (
                    <option key={idx.stock_code} value={idx.stock_code}>{idx.stock_name} ({idx.stock_code})</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">开始日期</div>
                <input type="date" value={previewStart} onChange={(e) => setPreviewStart(e.target.value)} className="rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">结束日期</div>
                <input type="date" value={previewEnd} onChange={(e) => setPreviewEnd(e.target.value)} className="rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>
              <button onClick={loadPreview} disabled={previewLoading} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50">
                {previewLoading ? '加载中...' : '查看'}
              </button>
            </div>

            {/* 图例 */}
            <div className="mb-3 flex gap-4 text-xs">
              <span className="flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{background:'rgba(59,130,246,0.25)'}}></span> 趋势市</span>
              <span className="flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{background:'rgba(234,179,8,0.25)'}}></span> 震荡市</span>
              <span className="flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{background:'rgba(156,163,175,0.25)'}}></span> 过渡区间</span>
            </div>

            {/* 图表 */}
            {previewData && previewData.dates.length > 0 && (
              <ReactECharts
                option={{
                  tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                  grid: { left: 60, right: 60, top: 30, bottom: 30 },
                  xAxis: { type: 'category', data: previewData.dates, axisLabel: { fontSize: 10, rotate: 45 } },
                  yAxis: [
                    { type: 'value', name: '价格', scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
                    { type: 'value', name: previewData.indicator_name, scale: true, splitLine: { show: false } },
                  ],
                  series: [
                    {
                      name: '收盘价',
                      type: 'line',
                      data: previewData.closes,
                      lineStyle: { width: 1.5, color: '#3b82f6' },
                      itemStyle: { color: '#3b82f6' },
                      symbol: 'none',
                      markArea: {
                        silent: true,
                        data: (function() {
                          const areas: any[] = []
                          const types = previewData.market_types
                          const dates = previewData.dates
                          let i = 0
                          while (i < types.length) {
                            const t = types[i]
                            let j = i
                            while (j < types.length && types[j] === t) j++
                            let color: string
                            if (t === 'trend') color = 'rgba(59,130,246,0.15)'
                            else if (t === 'range') color = 'rgba(234,179,8,0.15)'
                            else color = 'rgba(156,163,175,0.12)'
                            areas.push([{ xAxis: dates[i], itemStyle: { color } }, { xAxis: dates[j - 1] }])
                            i = j
                          }
                          return areas
                        })(),
                      },
                    },
                    {
                      name: previewData.indicator_name,
                      type: 'line',
                      yAxisIndex: 1,
                      data: previewData.indicator_values,
                      lineStyle: { width: 1, color: '#f97316', type: 'dashed' },
                      itemStyle: { color: '#f97316' },
                      symbol: 'none',
                    },
                  ],
                }}
                style={{ height: 400 }}
              />
            )}

            {previewData && previewData.dates.length === 0 && (
              <div className="py-8 text-center text-sm text-zinc-400">未查询到数据，请检查指数和日期范围</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

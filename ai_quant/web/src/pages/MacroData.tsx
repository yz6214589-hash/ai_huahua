import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { MacroLatest } from '@/api/types'
import { cn } from '@/lib/utils'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ExternalLink, RefreshCcw } from 'lucide-react'

// 指标中文名称映射（后端返回 name 时优先使用后端的）
const INDICATOR_LABELS: Record<string, string> = {
  CPI: 'CPI（居民消费价格指数）',
  PPI: 'PPI（生产价格指数）',
  PMI: 'PMI（采购经理指数）',
  LPR: 'LPR（贷款市场报价利率）',
  FearGreed: '恐惧贪婪指数',
  VIX: 'VIX（CBOE波动率指数）',
  OVX: 'OVX（原油波动率指数）',
  GVZ: 'GVZ（黄金波动率指数）',
  iVIX: 'iVIX（中国波动率指数）',
  US10Y: '美国10年期国债收益率',
}

// 指标分组定义
const CHINA_MARKET_INDICATORS = ['CPI', 'PMI', 'LPR', 'iVIX']
const GLOBAL_MARKET_INDICATORS = ['FearGreed', 'VIX', 'OVX', 'GVZ', 'US10Y']

/**
 * 格式化指标数值
 * - CPI: 百分比格式，保留1位小数
 * - PMI: 保留1位小数
 * - LPR: 百分比格式，保留2位小数
 * - FearGreed: 整数
 * - VIX/OVX/GVZ: 保留1位小数
 * - US10Y: 百分比格式，保留2位小数（后端已返回百分比形式，无需乘以100）
 */
function formatIndicatorValue(indicator: string, raw: number | null): string {
  if (raw == null) return '--'

  switch (indicator) {
    case 'CPI':
      return `${raw.toFixed(2)}%`
    case 'PMI':
      return raw.toFixed(2)
    case 'LPR':
      return `${raw.toFixed(2)}%`
    case 'FearGreed':
      return raw.toFixed(2)
    case 'VIX':
    case 'OVX':
    case 'GVZ':
    case 'iVIX':
      return raw.toFixed(2)
    case 'US10Y':
      return `${raw.toFixed(2)}%`
    default:
      return String(raw)
  }
}

/**
 * 获取指标卡片的颜色样式
 * - 经济指标（CPI/PMI/LPR）：蓝色系
 * - 情绪指标（FearGreed/VIX/OVX/GVZ）：根据值显示红/绿/灰色
 * - US10Y：紫色系
 */
function getIndicatorColor(indicator: string, value: number | null): {
  border: string
  valueText: string
  badge: string
  badgeText: string
} {
  // 经济指标（CPI/PMI/LPR）：蓝色系
  if (['CPI', 'PMI', 'LPR'].includes(indicator)) {
    return {
      border: 'border-l-blue-500',
      valueText: 'text-blue-700',
      badge: 'bg-blue-50',
      badgeText: 'text-blue-600',
    }
  }

  // US10Y：紫色系
  if (indicator === 'US10Y') {
    return {
      border: 'border-l-purple-500',
      valueText: 'text-purple-700',
      badge: 'bg-purple-50',
      badgeText: 'text-purple-600',
    }
  }

  // 情绪指标：根据值动态变色
  if (value == null) {
    return {
      border: 'border-l-zinc-300',
      valueText: 'text-zinc-700',
      badge: 'bg-zinc-50',
      badgeText: 'text-zinc-500',
    }
  }

  // FearGreed: >60 绿色(贪婪), 40-60 灰色(中性), <40 红色(恐慌)
  if (indicator === 'FearGreed') {
    if (value > 60) {
      return {
        border: 'border-l-emerald-500',
        valueText: 'text-emerald-700',
        badge: 'bg-emerald-50',
        badgeText: 'text-emerald-600',
      }
    }
    if (value < 40) {
      return {
        border: 'border-l-red-500',
        valueText: 'text-red-700',
        badge: 'bg-red-50',
        badgeText: 'text-red-600',
      }
    }
    return {
      border: 'border-l-zinc-400',
      valueText: 'text-zinc-700',
      badge: 'bg-zinc-50',
      badgeText: 'text-zinc-500',
    }
  }

  // VIX/OVX/GVZ/iVIX: >25 红色(高波动), 15-25 灰色(正常), <15 绿色(低波动)
  if (['VIX', 'OVX', 'GVZ', 'iVIX'].includes(indicator)) {
    if (value > 25) {
      return {
        border: 'border-l-red-500',
        valueText: 'text-red-700',
        badge: 'bg-red-50',
        badgeText: 'text-red-600',
      }
    }
    if (value < 15) {
      return {
        border: 'border-l-emerald-500',
        valueText: 'text-emerald-700',
        badge: 'bg-emerald-50',
        badgeText: 'text-emerald-600',
      }
    }
    return {
      border: 'border-l-zinc-400',
      valueText: 'text-zinc-700',
      badge: 'bg-zinc-50',
      badgeText: 'text-zinc-500',
    }
  }

  // 默认
  return {
    border: 'border-l-zinc-300',
    valueText: 'text-zinc-700',
    badge: 'bg-zinc-50',
    badgeText: 'text-zinc-500',
  }
}

/**
 * 获取情绪指标的标签文字
 */
function getSentimentLabel(indicator: string, value: number | null): string | null {
  if (value == null) return null

  if (indicator === 'FearGreed') {
    if (value > 60) return '贪婪'
    if (value < 40) return '恐慌'
    return '中性'
  }

  if (['VIX', 'OVX', 'GVZ', 'iVIX'].includes(indicator)) {
    if (value > 25) return '高波动'
    if (value < 15) return '低波动'
    return '正常'
  }

  return null
}

/**
 * 纯 SVG 实现的历史趋势折线图
 * 不引入额外依赖，使用 SVG 绘制坐标轴、刻度线、折线和数据点
 */
function TrendChart({ data, indicator }: { data: { date: string; value: number }[]; indicator: string }) {
  if (data.length === 0) {
    return <div className="py-4 text-center text-xs text-zinc-500">暂无历史数据</div>
  }

  const values = data.map((d) => d.value)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const range = maxVal - minVal || 1

  const width = 600
  const height = 200
  const padding = { top: 20, right: 20, bottom: 30, left: 50 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  // 生成 SVG 折线路径
  const points = data.map((d, i) => {
    const x = padding.left + (i / (data.length - 1 || 1)) * chartWidth
    const y = padding.top + chartHeight - ((d.value - minVal) / range) * chartHeight
    return `${x},${y}`
  })
  const pathD = `M ${points.join(' L ')}`

  // 生成填充区域路径（折线到底部的区域）
  const areaD = `${pathD} L ${padding.left + chartWidth},${padding.top + chartHeight} L ${padding.left},${padding.top + chartHeight} Z`

  // Y轴刻度值
  const yTicks = [minVal, minVal + range * 0.25, minVal + range * 0.5, minVal + range * 0.75, maxVal]

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {/* Y轴刻度线 */}
      {yTicks.map((tick, i) => {
        const y = padding.top + chartHeight - ((tick - minVal) / range) * chartHeight
        return (
          <g key={i}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e4e4e7" strokeWidth={0.5} />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" className="text-[10px]" fill="#71717a">
              {formatIndicatorValue(indicator, tick)}
            </text>
          </g>
        )
      })}
      {/* 填充区域 */}
      <path d={areaD} fill="rgba(59,130,246,0.08)" />
      {/* 趋势折线 */}
      <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth={2} />
      {/* 数据点 */}
      {data.map((d, i) => {
        const x = padding.left + (i / (data.length - 1 || 1)) * chartWidth
        const y = padding.top + chartHeight - ((d.value - minVal) / range) * chartHeight
        return <circle key={i} cx={x} cy={y} r={3} fill="#3b82f6" />
      })}
      {/* X轴日期标签（只显示首尾和中间） */}
      {[0, Math.floor(data.length / 2), data.length - 1].map((idx) => {
        if (idx >= data.length) return null
        const x = padding.left + (idx / (data.length - 1 || 1)) * chartWidth
        return (
          <text key={idx} x={x} y={height - 5} textAnchor="middle" className="text-[10px]" fill="#71717a">
            {data[idx].date.slice(5)}
          </text>
        )
      })}
    </svg>
  )
}

function IndicatorCard({ it, onClick }: { it: MacroLatest['indicators'][number]; onClick: () => void }) {
  // 优先使用后端返回的 name 字段，否则回退到本地映射
  const label = it.name || INDICATOR_LABELS[it.indicator] || it.indicator
  const raw = it.value
  const display = formatIndicatorValue(it.indicator, raw)
  const colors = getIndicatorColor(it.indicator, raw)
  const sentimentLabel = getSentimentLabel(it.indicator, raw)

  return (
    <Card className={cn('border-l-4 cursor-pointer hover:shadow-md transition-shadow', colors.border)} onClick={onClick}>
      <CardBody>
        {/* 第一行：大号数值 */}
        <div className={cn('text-2xl font-bold', colors.valueText)}>
          {display}
          {sentimentLabel && (
            <span className={cn('ml-2 inline-block rounded px-1.5 py-0.5 text-xs font-medium', colors.badge, colors.badgeText)}>
              {sentimentLabel}
            </span>
          )}
        </div>
        {/* 第二行：指标名称（中文含义） */}
        <div className="mt-1 text-sm text-zinc-600">{label}</div>
        {/* 第三行：数据日期 + 数据来源 */}
        <div className="mt-1 text-xs text-zinc-400">
          {it.date || '--'}
          {it.source ? ` · ${it.source}` : ''}
        </div>
        {it.error ? <div className="mt-1 text-xs text-red-500">{it.error}</div> : null}
      </CardBody>
    </Card>
  )
}

export default function MacroData() {
  const [macro, setMacro] = useState<MacroLatest | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // 历史趋势相关状态
  const [selectedIndicator, setSelectedIndicator] = useState<string | null>(null)
  const [historyData, setHistoryData] = useState<{ date: string; value: number }[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<MacroLatest>('/api/v1/macro/latest')
      setMacro(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  // 点击卡片时获取历史数据
  const handleCardClick = async (indicator: string) => {
    setSelectedIndicator(indicator)
    setHistoryLoading(true)
    try {
      const r = await fetchJson<{ indicator: string; name: string; data: { date: string; value: number }[] }>(
        `/api/v1/macro/history/${indicator}?days=90`
      )
      setHistoryData(r.data || [])
    } catch {
      setHistoryData([])
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // ESC 键关闭弹窗
  useEffect(() => {
    if (!selectedIndicator) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedIndicator(null)
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [selectedIndicator])

  // 弹窗打开时禁止背景滚动
  useEffect(() => {
    if (selectedIndicator) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [selectedIndicator])

  // 按分组过滤指标
  const chinaMarketIndicators = macro?.indicators?.filter((it) =>
    CHINA_MARKET_INDICATORS.includes(it.indicator)
  ) || []
  const globalIndicators = macro?.indicators?.filter((it) =>
    GLOBAL_MARKET_INDICATORS.includes(it.indicator)
  ) || []

  return (
    <div className="space-y-6">
      {/* 隐藏：刷新按钮
      <div className="flex items-center justify-end">
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className={cn(loading ? 'animate-spin' : '', 'h-4 w-4')} />
          刷新
        </button>
      </div>
      */}

      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}

      {/* 初始加载骨架屏 */}
      {loading && !macro ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardBody>
                <div className="animate-pulse">
                  <div className="h-8 w-24 rounded bg-zinc-200" />
                  <div className="mt-2 h-4 w-40 rounded bg-zinc-100" />
                  <div className="mt-2 h-3 w-28 rounded bg-zinc-100" />
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : macro?.indicators && macro.indicators.length > 0 ? (
        <>
          {/* 中国市场指标分组 */}
          {chinaMarketIndicators.length > 0 && (
            <div>
              <div className="mb-3 text-sm font-medium text-zinc-700">中国市场指标</div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {chinaMarketIndicators.map((it) => (
                  <IndicatorCard key={it.indicator} it={it} onClick={() => handleCardClick(it.indicator)} />
                ))}
              </div>
            </div>
          )}

          {/* 全球市场指标分组 */}
          {globalIndicators.length > 0 && (
            <div>
              <div className="mb-3 text-sm font-medium text-zinc-700">全球市场指标</div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {globalIndicators.map((it) => {
                  // FearGreed 卡片合并 composite 数据
                  if (it.indicator === 'FearGreed' && macro?.composite) {
                    const raw = it.value
                    const display = formatIndicatorValue(it.indicator, raw)
                    const colors = getIndicatorColor(it.indicator, raw)
                    const sentimentLabel = getSentimentLabel(it.indicator, raw)
                    const label = it.name || INDICATOR_LABELS[it.indicator] || it.indicator
                    return (
                      <Card
                        key={it.indicator}
                        className={cn('border-l-4 cursor-pointer hover:shadow-md transition-shadow', colors.border)}
                        onClick={() => handleCardClick(it.indicator)}
                      >
                        <CardBody>
                          <div className={cn('text-2xl font-bold', colors.valueText)}>
                            {display}
                            {sentimentLabel && (
                              <span className={cn('ml-2 inline-block rounded px-1.5 py-0.5 text-xs font-medium', colors.badge, colors.badgeText)}>
                                {sentimentLabel}
                              </span>
                            )}
                          </div>
                          <div className="mt-1 text-sm text-zinc-600">{label}</div>
                          <div className="mt-1 text-xs text-zinc-400">
                            {it.date || '--'}
                            {it.source ? ` · ${it.source}` : ''}
                          </div>
                          <div className="mt-3 border-t border-zinc-100 pt-2">
                            <div className="text-xs text-zinc-600">
                              整体情绪：<span className="font-medium text-zinc-800">{macro.composite.overall_sentiment || '--'}</span>
                              <span className="mx-1.5 text-zinc-300">|</span>
                              建议：<span className="font-medium text-zinc-800">{macro.composite.action_suggestion || '--'}</span>
                            </div>
                            <div className="mt-1 text-[11px] text-zinc-400">
                              更新于 {macro.composite.timestamp ? macro.composite.timestamp.slice(0, 16).replace('T', ' ') : '--'}
                            </div>
                          </div>
                        </CardBody>
                      </Card>
                    )
                  }
                  return (
                    <IndicatorCard key={it.indicator} it={it} onClick={() => handleCardClick(it.indicator)} />
                  )
                })}
              </div>
            </div>
          )}

          {/* 历史趋势弹窗 */}
          {selectedIndicator && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
              onClick={() => setSelectedIndicator(null)}
            >
              <div
                className="w-[90vw] max-w-[720px] rounded-xl bg-white p-6 shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              >
                {/* 弹窗头部 */}
                <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
                  <h3 className="text-base font-semibold text-zinc-900">
                    {INDICATOR_LABELS[selectedIndicator] || selectedIndicator} - 历史趋势
                  </h3>
                  <button
                    onClick={() => setSelectedIndicator(null)}
                    className="rounded-lg p-1.5 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-600"
                  >
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                {/* 弹窗内容 */}
                <div className="mt-4">
                  {historyLoading ? (
                    <div className="py-12 text-center text-sm text-zinc-500">加载中...</div>
                  ) : (
                    <TrendChart data={historyData} indicator={selectedIndicator} />
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      ) : !loading ? (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">暂无宏观数据</div>
      ) : null}

      <Card>
        <CardHeader title="Polymarket 快捷入口">Polymarket 快捷入口</CardHeader>
        <CardBody>
          <div className="mt-1 flex flex-wrap gap-2">
            {['war', 'ceasefire', 'tariff', 'China', 'Fed'].map((k) => (
              <a
                key={k}
                href={`https://polymarket.com/markets?search=${k}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
              >
                {k} <ExternalLink className="h-3 w-3" />
              </a>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

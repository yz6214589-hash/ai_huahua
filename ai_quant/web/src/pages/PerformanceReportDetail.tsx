/**
 * 绩效报告详情页
 * 支持普通版和 Plus 版切换展示
 * 普通版：QuantStats 基础指标和图表
 * Plus 版：额外展示 SVD 诊断、成本分析、个股盈亏
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loading } from '@/components/Loading'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { toast } from '@/components/Toast'
import { postJson } from '@/api/client'
import {
  getReportDetailFull,
  getReportDetailPlus,
  getQuantStatsHtml,
  type ReportDetail,
  type ReportDetailPlus,
  type SVDResult,
  type CostAnalysis,
  type StockPnL,
} from '@/api/performance'
import {
  formatDate,
  formatPct,
  formatNum,
  buildEquityOption,
  buildMonthlyHeatmapOption,
  buildDrawdownOption,
} from '@/utils/performanceReport'
import {
  ArrowLeft,
  Download,
  Printer,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'

/** 市场状态颜色映射 */
const STATE_COLOR_MAP: Record<string, string> = {
  '齐涨齐跌': 'bg-green-100 text-green-800',
  '板块分化': 'bg-yellow-100 text-yellow-800',
  '个股行情': 'bg-red-100 text-red-800',
}

/** 全量 QuantStats 指标定义（34项） */
const ALL_QS_METRICS: Array<{ key: string; label: string; type: 'pct' | 'num' | 'int'; decimals?: number }> = [
  { key: 'total_return', label: '总收益率', type: 'pct' },
  { key: 'annualized_return', label: '年化收益率', type: 'pct' },
  { key: 'cagr', label: 'CAGR', type: 'pct' },
  { key: 'max_drawdown', label: '最大回撤', type: 'pct' },
  { key: 'sharpe_ratio', label: '夏普比率', type: 'num' },
  { key: 'sortino', label: '索提诺比率', type: 'num' },
  { key: 'omega', label: 'Omega 比率', type: 'num' },
  { key: 'calmar_ratio', label: '卡玛比率', type: 'num' },
  { key: 'var_95', label: 'VaR(95%)', type: 'pct' },
  { key: 'cvar_95', label: 'CVaR(95%)', type: 'pct' },
  { key: 'gain_to_pain', label: '盈亏比(G/P)', type: 'num' },
  { key: 'profit_factor', label: '盈亏比', type: 'num' },
  { key: 'skew', label: '偏度', type: 'num' },
  { key: 'kurtosis', label: '峰度', type: 'num' },
  { key: 'volatility', label: '波动率', type: 'pct' },
  { key: 'best_day', label: '最佳单日', type: 'pct' },
  { key: 'worst_day', label: '最差单日', type: 'pct' },
  { key: 'consecutive_wins', label: '最大连胜', type: 'int' },
  { key: 'consecutive_losses', label: '最大连亏', type: 'int' },
  { key: 'win_rate', label: '胜率', type: 'pct' },
  { key: 'alpha', label: 'Alpha', type: 'num' },
  { key: 'beta', label: 'Beta', type: 'num' },
  { key: 'information_ratio', label: '信息比率', type: 'num' },
  { key: 'tracking_error', label: '跟踪误差', type: 'pct' },
  { key: 'total_trades', label: '总交易次数', type: 'int' },
  { key: 'winning_trades', label: '盈利次数', type: 'int' },
  { key: 'losing_trades', label: '亏损次数', type: 'int' },
  { key: 'avg_profit', label: '平均盈利', type: 'num' },
  { key: 'avg_loss', label: '平均亏损', type: 'num' },
  { key: 'trading_days', label: '交易天数', type: 'int' },
  { key: 'initial_cash', label: '初始资金', type: 'num', decimals: 0 },
  { key: 'final_nav', label: '期末净值', type: 'num' },
  { key: 'max_drawdown_duration', label: '最大回撤持续期', type: 'int' },
  { key: 'recovery_factor', label: '恢复因子', type: 'num' },
]

/** 从 ReportDetail 中获取指标值 */
function getMetricValue(detail: ReportDetail, key: string): number | string | undefined | null {
  // 先从顶层属性取
  const topLevel = (detail as any)[key]
  if (topLevel != null) return topLevel
  // 再从 metrics 子对象取
  const metricsLevel = detail.metrics?.[key as keyof typeof detail.metrics]
  if (metricsLevel != null) return metricsLevel
  return null
}

/** 构建成本构成饼图 ECharts 配置 */
function buildCostPieOption(cost: CostAnalysis) {
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, fontSize: 11, formatter: '{b}\n{d}%' },
        data: [
          { value: cost.commission, name: '佣金', itemStyle: { color: '#5470c6' } },
          { value: cost.stamp_tax, name: '印花税', itemStyle: { color: '#91cc75' } },
          { value: cost.transfer_fee, name: '过户费', itemStyle: { color: '#fac858' } },
        ],
      },
    ],
  }
}

/** 构建 SVD 趋势图 ECharts 配置 */
function buildSVDTrendOption(rollingData: SVDResult['rolling_data']) {
  if (!rollingData || rollingData.length === 0) return null

  const dates = rollingData.map(d => d.date.length > 10 ? d.date.slice(0, 10) : d.date)
  const top1Values = rollingData.map(d => parseFloat((d.top1_var * 100).toFixed(2)))
  const top3Values = rollingData.map(d => parseFloat((d.top3_var * 100).toFixed(2)))

  // 标记不同市场状态的区间
  const stateColors: Record<string, string> = {
    '齐涨齐跌': '#91cc75',
    '板块分化': '#fac858',
    '个股行情': '#ee6666',
  }

  // 为每个点根据状态设置颜色
  const top1ItemColors = rollingData.map(d => stateColors[d.state] || '#5470c6')

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = params[0]?.axisValue + '<br/>'
        for (const p of params) {
          html += `${p.marker} ${p.seriesName}: ${parseFloat(p.value).toFixed(2)}%<br/>`
        }
        const idx = params[0]?.dataIndex
        if (idx != null && rollingData[idx]) {
          html += `市场状态: ${rollingData[idx].state}`
        }
        return html
      },
    },
    legend: { data: ['Factor1 方差占比', 'Factor1-3 累计占比'], bottom: 0 },
    grid: { left: '8%', right: '5%', top: '10%', bottom: '18%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => v.toFixed(0) + '%', fontSize: 10 },
    },
    series: [
      {
        name: 'Factor1 方差占比',
        type: 'line',
        data: top1Values.map((v, i) => ({
          value: v,
          itemStyle: { color: top1ItemColors[i] },
        })),
        smooth: true,
        lineStyle: { color: '#5470c6', width: 2 },
        itemStyle: { color: '#5470c6' },
        symbol: 'circle',
        symbolSize: 4,
      },
      {
        name: 'Factor1-3 累计占比',
        type: 'line',
        data: top3Values,
        smooth: true,
        lineStyle: { color: '#91cc75', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#91cc75' },
        symbol: 'none',
      },
    ],
  }
}

export default function PerformanceReportDetail() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const contentRef = useRef<HTMLDivElement>(null)

  // 基础数据
  const [detail, setDetail] = useState<ReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 版本切换
  const [mode, setMode] = useState<'common' | 'plus'>('common')

  // Plus 版额外数据
  const [plusData, setPlusData] = useState<ReportDetailPlus | null>(null)
  const [plusLoading, setPlusLoading] = useState(false)
  const [plusDataLoaded, setPlusDataLoaded] = useState(false)
  const [plusError, setPlusError] = useState<string | null>(null)

  // 重新生成和 AI 分析
  const [regenerating, setRegenerating] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // 全量指标表格展开/收起
  const [metricsExpanded, setMetricsExpanded] = useState(false)

  // 加载基础报告数据
  useEffect(() => {
    if (!reportId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    getReportDetailFull(reportId)
      .then(data => {
        if (!cancelled) setDetail(data)
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : '加载报告详情失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [reportId])

  // 切换到 Plus 版时加载额外数据
  useEffect(() => {
    if (mode !== 'plus' || !reportId || plusDataLoaded) return
    let cancelled = false
    setPlusLoading(true)
    setPlusError(null)
    getReportDetailPlus(reportId)
      .then(data => {
        if (!cancelled) {
          setPlusData(data)
          setPlusDataLoaded(true)
        }
      })
      .catch(e => {
        if (!cancelled) {
          setPlusError(e instanceof Error ? e.message : '加载 Plus 版数据失败')
        }
      })
      .finally(() => {
        if (!cancelled) setPlusLoading(false)
      })
    return () => { cancelled = true }
  }, [mode, reportId, plusDataLoaded])

  /** 重新生成报告 */
  const handleRegenerate = useCallback(async () => {
    if (!reportId || !detail) return
    setRegenerating(true)
    try {
      await postJson(`/api/v1/performance/regenerate/${reportId}`, { report_type: mode })
      // 重新加载详情
      setDetail(null)
      setPlusData(null)
      setPlusDataLoaded(false)
      setPlusError(null)
      const data = await getReportDetailFull(reportId!)
      setDetail(data)
      if (mode === 'plus') {
        const plusRes = await getReportDetailPlus(reportId!)
        setPlusData(plusRes)
        setPlusDataLoaded(true)
      }
      toast('success', '报告重新生成成功')
    } catch (e) {
      toast('error', e instanceof Error ? e.message : '重新生成失败')
    } finally {
      setRegenerating(false)
    }
  }, [reportId, detail, mode])

  /** 生成 AI 分析 */
  const handleGenerateAI = useCallback(async () => {
    if (!reportId) return
    setAiLoading(true)
    try {
      const res = await postJson<{ analysis: string }>(`/api/v1/performance/ai-analysis/${reportId}`, {})
      setAiAnalysis(res.analysis || '暂无分析结果')
    } catch (e) {
      setAiAnalysis('AI 分析生成失败：' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setAiLoading(false)
    }
  }, [reportId])

  /** 打开 QuantStats HTML 报告 */
  const handleOpenQuantStats = useCallback(async () => {
    if (!reportId) return
    try {
      const result = await getQuantStatsHtml(reportId)
      if (result?.url) {
        window.open(result.url, '_blank')
      } else if (result?.html_path) {
        window.open(result.html_path, '_blank')
      }
    } catch {
      window.open(`/api/v1/performance/quantstats-html/${reportId}`, '_blank')
    }
  }, [reportId])

  /** 导出 PDF */
  const handleExportPDF = useCallback(async () => {
    try {
      const { default: html2canvas } = await import('html2canvas')
      const { default: jsPDF } = await import('jspdf')
      if (!contentRef.current) return
      const canvas = await html2canvas(contentRef.current, { useCORS: true, scale: 2, backgroundColor: '#ffffff' })
      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pdfW = 190
      const pdfH = (canvas.height / canvas.width) * pdfW
      const pageH = 277
      if (pdfH <= pageH) {
        pdf.addImage(imgData, 'PNG', 10, 10, pdfW, pdfH)
      } else {
        let position = 10
        pdf.addImage(imgData, 'PNG', 10, position, pdfW, pdfH)
      }
      pdf.save(`绩效报告_${detail?.strategy_name || 'unknown'}_${new Date().toISOString().slice(0, 10)}.pdf`)
    } catch {
      // 导出失败时静默处理
    }
  }, [detail?.strategy_name])

  /** 打印 */
  const handlePrint = useCallback(() => {
    window.print()
  }, [])

  // 加载中
  if (loading) {
    return <Loading className="py-20" text="加载报告详情" />
  }

  // 加载失败
  if (error || !detail) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <p className="text-sm text-zinc-500">{error || '报告不存在'}</p>
        <button
          onClick={() => navigate('/strategy/performance')}
          className="mt-3 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          返回报告列表
        </button>
      </div>
    )
  }

  // 数据准备
  const equityCurve = detail.equity_curve || []
  const drawdownCurve = detail.drawdown_curve || []
  const monthlyReturns = detail.monthly_returns || []
  const trades = detail.trades || []

  const equityOption = equityCurve.length > 0
    ? buildEquityOption(equityCurve, undefined, detail.initial_cash)
    : null
  const heatmapOption = monthlyReturns.length > 0 ? buildMonthlyHeatmapOption(monthlyReturns) : null
  const drawdownOption = drawdownCurve.length > 0 ? buildDrawdownOption(drawdownCurve) : null

  // Plus 版数据
  const svdResult = plusData?.svd_result
  const costAnalysis = plusData?.cost_analysis
  const stockPnl = plusData?.stock_pnl || []

  // 指标快捷访问
  const qs: Partial<ReportDetail> = detail || {}

  return (
    <div className="space-y-6">
      {/* 顶部区域 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/strategy/performance')}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            返回列表
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-zinc-900">
                {detail.strategy_name || '未命名策略'}
              </h1>
              <Badge variant={detail.report_type === 'plus' ? 'success' : 'default'}>
                {detail.report_type === 'plus' ? 'PLUS 版' : '普通版'}
              </Badge>
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">
              {formatDate(detail.start_date)} ~ {formatDate(detail.end_date)} | 初始资金：{detail.initial_cash?.toLocaleString()}
              {detail.backtest_id && (
                <span className="ml-3">
                  <button onClick={() => navigate(`/strategy/backtest-history?backtest_id=${detail.backtest_id}`)}
                    className="text-blue-600 hover:text-blue-800 hover:underline">回测任务：{detail.backtest_id.slice(0, 8)}...</button>
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* 普通版/Plus版切换 */}
          <div className="flex gap-1">
            {(['common', 'plus'] as const).map(t => (
              <button
                key={t}
                onClick={() => setMode(t)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  mode === t
                    ? 'bg-zinc-900 text-white'
                    : 'border border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                }`}
              >
                {t === 'common' ? '普通版' : 'Plus版'}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              if (!window.confirm('确定要重新生成报告吗？\n\n此操作将覆盖当前报告数据。')) return
              handleRegenerate()
            }}
            disabled={regenerating}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? 'animate-spin' : ''}`} /> 重新生成
          </button>
          <button
            onClick={handleExportPDF}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
          >
            <Download className="w-3.5 h-3.5" /> 导出PDF
          </button>
          <button
            onClick={handlePrint}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
          >
            <Printer className="w-3.5 h-3.5" /> 打印
          </button>
          <button
            onClick={handleOpenQuantStats}
            className="inline-flex items-center gap-1 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition"
          >
            <ExternalLink className="w-3.5 h-3.5" /> 查看 QuantStats 报告
          </button>
        </div>
      </div>

      <div ref={contentRef} className="space-y-6">
        {/* ============ 普通版内容 ============ */}

        {/* 指标卡片区域 - 第一行 */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className={`text-xl font-bold ${(detail.metrics?.total_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPct(detail.metrics?.total_return)}
            </div>
            <div className="mt-1 text-xs text-zinc-500">总收益率</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className={`text-xl font-bold ${(detail.metrics?.annualized_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPct(detail.metrics?.annualized_return)}
            </div>
            <div className="mt-1 text-xs text-zinc-500">年化收益率</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-red-600">{formatPct(detail.metrics?.max_drawdown)}</div>
            <div className="mt-1 text-xs text-zinc-500">最大回撤</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(detail.metrics?.sharpe_ratio)}</div>
            <div className="mt-1 text-xs text-zinc-500">夏普比率</div>
          </div>
        </div>

        {/* 指标卡片区域 - 第二行 */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.sortino)}</div>
            <div className="mt-1 text-xs text-zinc-500">索提诺比率</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.omega)}</div>
            <div className="mt-1 text-xs text-zinc-500">Omega 比率</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-red-600">{formatPct(qs.var_95)}</div>
            <div className="mt-1 text-xs text-zinc-500">VaR(95%)</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-red-600">{formatPct(qs.cvar_95)}</div>
            <div className="mt-1 text-xs text-zinc-500">CVaR(95%)</div>
          </div>
        </div>

        {/* 指标卡片区域 - 第三行 */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.gain_to_pain)}</div>
            <div className="mt-1 text-xs text-zinc-500">盈亏比(G/P)</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.skew)}</div>
            <div className="mt-1 text-xs text-zinc-500">偏度</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.kurtosis)}</div>
            <div className="mt-1 text-xs text-zinc-500">峰度</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatPct(qs.cagr)}</div>
            <div className="mt-1 text-xs text-zinc-500">CAGR</div>
          </div>
        </div>

        {/* 指标卡片区域 - 第四行 */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-green-600">{formatPct(qs.best_day)}</div>
            <div className="mt-1 text-xs text-zinc-500">最佳单日</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-red-600">{formatPct(qs.worst_day)}</div>
            <div className="mt-1 text-xs text-zinc-500">最差单日</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-green-600">{qs.consecutive_wins ?? '--'}</div>
            <div className="mt-1 text-xs text-zinc-500">最大连胜</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-red-600">{qs.consecutive_losses ?? '--'}</div>
            <div className="mt-1 text-xs text-zinc-500">最大连亏</div>
          </div>
        </div>

        {/* 指标卡片区域 - 第五行 */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.alpha)}</div>
            <div className="mt-1 text-xs text-zinc-500">Alpha</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.beta)}</div>
            <div className="mt-1 text-xs text-zinc-500">Beta</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatNum(qs.information_ratio)}</div>
            <div className="mt-1 text-xs text-zinc-500">信息比率</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <div className="text-xl font-bold text-zinc-900">{formatPct(qs.tracking_error)}</div>
            <div className="mt-1 text-xs text-zinc-500">跟踪误差</div>
          </div>
        </div>

        {/* 图表区域：累计收益曲线 + 月度收益热力图 */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-zinc-200 p-4">
            <div className="mb-2 text-xs font-medium text-zinc-600">累计收益曲线</div>
            {equityOption ? (
              <ReactECharts option={equityOption} style={{ height: 280 }} />
            ) : (
              <div className="flex items-center justify-center h-[280px] text-zinc-400 text-sm">
                暂无收益曲线数据
              </div>
            )}
          </div>
          <div className="rounded-lg border border-zinc-200 p-4">
            <div className="mb-2 text-xs font-medium text-zinc-600">月度收益热力图</div>
            {heatmapOption ? (
              <ReactECharts option={heatmapOption} style={{ height: 280 }} />
            ) : (
              <div className="flex items-center justify-center h-[280px] text-zinc-400 text-sm">
                暂无月度收益数据
              </div>
            )}
          </div>
        </div>

        {/* 回撤水下图（全宽） */}
        <div className="rounded-lg border border-zinc-200 p-4">
          <div className="mb-2 text-xs font-medium text-zinc-600">回撤水下图</div>
          {drawdownOption ? (
            <ReactECharts option={drawdownOption} style={{ height: 220 }} />
          ) : (
            <div className="flex items-center justify-center h-[220px] text-zinc-400 text-sm">
              暂无回撤数据
            </div>
          )}
        </div>

        {/* 全量指标表格（可展开/收起） */}
        <Card>
          <CardHeader>
            <div
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setMetricsExpanded(!metricsExpanded)}
            >
              <h3 className="text-sm font-semibold text-zinc-700">全量指标明细（{ALL_QS_METRICS.length}项）</h3>
              {metricsExpanded ? (
                <ChevronUp className="w-4 h-4 text-zinc-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-zinc-400" />
              )}
            </div>
          </CardHeader>
          {metricsExpanded && (
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-100">
                      <th className="py-2 px-3 text-left text-xs font-medium text-zinc-500">指标名称</th>
                      <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">指标值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ALL_QS_METRICS.map(m => {
                      const raw = getMetricValue(detail, m.key)
                      let display = '--'
                      if (raw != null) {
                        if (m.type === 'pct') display = formatPct(raw as number)
                        else if (m.type === 'int') display = String(Math.round(Number(raw)))
                        else display = formatNum(raw as number, m.decimals)
                      }
                      return (
                        <tr key={m.key} className="border-b border-zinc-50 hover:bg-zinc-50">
                          <td className="py-2 px-3 text-zinc-700">{m.label}</td>
                          <td className="py-2 px-3 text-right font-mono text-zinc-900">{display}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          )}
        </Card>

        {/* 交易记录表格 */}
        {trades.length > 0 && (
          <Card>
            <CardHeader><h3 className="text-sm font-semibold text-zinc-700">交易记录</h3></CardHeader>
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-100">
                      <th className="py-2 px-3 text-left text-xs font-medium text-zinc-500">日期</th>
                      <th className="py-2 px-3 text-left text-xs font-medium text-zinc-500">方向</th>
                      <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">数量</th>
                      <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">价格</th>
                      <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">金额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t, i) => {
                      const trade = t as Record<string, any>
                      // 方向字段：优先使用后端 action 字段，并做中文映射
                      const directionMap: Record<string, string> = { buy: '买入', sell: '卖出', pending_sell: '待卖' }
                      const direction = directionMap[trade.action] || trade.action || trade.direction || trade.side || '--'
                      const isBuy = direction.toLowerCase().includes('buy') || direction === '买入'
                      return (
                        <tr key={i} className="border-b border-zinc-50 hover:bg-zinc-50">
                          <td className="py-2 px-3 text-zinc-700">{formatDate(trade.trade_date || trade.date)}</td>
                          <td className="py-2 px-3">
                            <span className={`text-xs font-medium ${isBuy ? 'text-red-600' : 'text-green-600'}`}>
                              {direction}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right text-zinc-700">{trade.size || trade.quantity || trade.amount || '--'}</td>
                          <td className="py-2 px-3 text-right text-zinc-700">{trade.price ? Number(trade.price).toFixed(2) : '--'}</td>
                          <td className="py-2 px-3 text-right text-zinc-700">{(trade.cost || trade.proceeds || trade.total || trade.value) ? Number(trade.cost || trade.proceeds || trade.total || trade.value).toLocaleString() : '--'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        )}

        {/* AI 策略分析模块 - 普通版和 Plus 版都显示 */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-700">AI 策略分析</h3>
              {!aiAnalysis && !aiLoading && (
                <button
                  onClick={handleGenerateAI}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                >
                  生成 AI 分析
                </button>
              )}
            </div>
          </CardHeader>
          <CardBody>
            {aiLoading && <Loading className="py-6" text="AI 分析中，请稍候..." size="sm" />}
            {aiAnalysis && !aiLoading && (
              <div className="prose prose-sm max-w-none text-zinc-700 whitespace-pre-wrap leading-relaxed">
                {aiAnalysis}
              </div>
            )}
            {!aiAnalysis && !aiLoading && (
              <div className="py-6 text-center text-sm text-zinc-400">
                点击"生成 AI 分析"获取策略智能分析报告
              </div>
            )}
          </CardBody>
        </Card>

        {/* ============ Plus 版额外内容 ============ */}
        {mode === 'plus' && (
          <>
            {plusLoading && <Loading className="py-6" text="加载Plus版数据" size="sm" />}

            {/* SVD 市场状态诊断 */}
            {svdResult && (
              <Card>
                <CardHeader><h3 className="text-sm font-semibold text-zinc-700">SVD 市场状态诊断</h3></CardHeader>
                <CardBody>
                  <div className="space-y-4">
                    {/* 诊断卡片 */}
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                      {/* 当前市场状态 */}
                      <div className="rounded-lg border border-zinc-200 p-4 text-center">
                        <div className="text-xs text-zinc-500 mb-2">当前市场状态</div>
                        <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-semibold ${STATE_COLOR_MAP[svdResult.current_state] || 'bg-zinc-100 text-zinc-800'}`}>
                          {svdResult.current_state}
                        </span>
                      </div>
                      {/* Factor1 方差占比 */}
                      <div className="rounded-lg border border-zinc-200 p-4 text-center">
                        <div className="text-xs text-zinc-500 mb-2">Factor1 方差占比</div>
                        <div className="text-2xl font-bold text-zinc-900">
                          {(svdResult.current_f1_ratio * 100).toFixed(1)}%
                        </div>
                      </div>
                      {/* 投资建议 */}
                      <div className="rounded-lg border border-zinc-200 p-4">
                        <div className="text-xs text-zinc-500 mb-2">投资建议</div>
                        <div className="text-sm text-zinc-700 leading-relaxed">{svdResult.advice}</div>
                      </div>
                    </div>

                    {/* SVD 趋势图 */}
                    {svdResult.rolling_data && svdResult.rolling_data.length > 0 && (
                      <div className="rounded-lg border border-zinc-200 p-4">
                        <div className="mb-2 text-xs font-medium text-zinc-600">SVD 趋势图</div>
                        {(() => {
                          const svdOption = buildSVDTrendOption(svdResult.rolling_data)
                          return svdOption ? (
                            <ReactECharts option={svdOption} style={{ height: 280 }} />
                          ) : (
                            <div className="flex items-center justify-center h-[280px] text-zinc-400 text-sm">
                              暂无趋势数据
                            </div>
                          )
                        })()}
                      </div>
                    )}

                    {/* 数据概要 */}
                    <div className="text-xs text-zinc-400">
                      分析股票数: {svdResult.stock_count} | 数据天数: {svdResult.data_days}
                    </div>
                  </div>
                </CardBody>
              </Card>
            )}

            {/* 个股盈亏分析 */}
            {stockPnl.length > 0 && (
              <Card>
                <CardHeader><h3 className="text-sm font-semibold text-zinc-700">个股盈亏分析</h3></CardHeader>
                <CardBody>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-100">
                          <th className="py-2 px-3 text-left text-xs font-medium text-zinc-500">证券名称</th>
                          <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">买入金额</th>
                          <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">卖出金额</th>
                          <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">未平仓数量</th>
                          <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">已实现盈亏</th>
                          <th className="py-2 px-3 text-right text-xs font-medium text-zinc-500">总成本</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stockPnl.map((s, i) => (
                          <tr key={i} className="border-b border-zinc-50 hover:bg-zinc-50">
                            <td className="py-2 px-3 text-zinc-700">
                              {s.stock_name}
                              <span className="ml-1 text-zinc-400 text-xs">{s.stock_code}</span>
                            </td>
                            <td className="py-2 px-3 text-right text-zinc-700">{s.buy_amount?.toLocaleString() ?? '--'}</td>
                            <td className="py-2 px-3 text-right text-zinc-700">{s.sell_amount?.toLocaleString() ?? '--'}</td>
                            <td className="py-2 px-3 text-right text-zinc-700">{s.unclosed ?? '--'}</td>
                            <td className={`py-2 px-3 text-right font-medium ${(s.realized_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {s.realized_pnl != null ? (s.realized_pnl >= 0 ? '+' : '') + s.realized_pnl.toLocaleString() : '--'}
                            </td>
                            <td className="py-2 px-3 text-right text-zinc-700">{s.total_cost?.toLocaleString() ?? '--'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardBody>
              </Card>
            )}

            {/* 交易成本分析 */}
            {costAnalysis && (
              <Card>
                <CardHeader><h3 className="text-sm font-semibold text-zinc-700">交易成本分析</h3></CardHeader>
                <CardBody>
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    {/* 左侧：成本明细 */}
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg bg-zinc-50 p-3 text-center">
                          <div className="text-xs text-zinc-500">总成交额</div>
                          <div className="mt-1 text-lg font-semibold text-zinc-900">{costAnalysis.total_turnover?.toLocaleString() ?? '--'}</div>
                        </div>
                        <div className="rounded-lg bg-zinc-50 p-3 text-center">
                          <div className="text-xs text-zinc-500">综合费率</div>
                          <div className="mt-1 text-lg font-semibold text-zinc-900">{costAnalysis.cost_ratio != null ? (costAnalysis.cost_ratio * 100).toFixed(4) + '%' : '--'}</div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border border-zinc-200 p-3">
                          <div className="text-xs text-zinc-500">佣金</div>
                          <div className="mt-1 text-base font-semibold text-zinc-900">{costAnalysis.commission?.toLocaleString() ?? '--'}</div>
                          <div className="text-xs text-zinc-400">
                            {costAnalysis.total_cost ? ((costAnalysis.commission / costAnalysis.total_cost) * 100).toFixed(1) + '%' : '--'}
                          </div>
                        </div>
                        <div className="rounded-lg border border-zinc-200 p-3">
                          <div className="text-xs text-zinc-500">印花税</div>
                          <div className="mt-1 text-base font-semibold text-zinc-900">{costAnalysis.stamp_tax?.toLocaleString() ?? '--'}</div>
                          <div className="text-xs text-zinc-400">
                            {costAnalysis.total_cost ? ((costAnalysis.stamp_tax / costAnalysis.total_cost) * 100).toFixed(1) + '%' : '--'}
                          </div>
                        </div>
                        <div className="rounded-lg border border-zinc-200 p-3">
                          <div className="text-xs text-zinc-500">过户费</div>
                          <div className="mt-1 text-base font-semibold text-zinc-900">{costAnalysis.transfer_fee?.toLocaleString() ?? '--'}</div>
                          <div className="text-xs text-zinc-400">
                            {costAnalysis.total_cost ? ((costAnalysis.transfer_fee / costAnalysis.total_cost) * 100).toFixed(1) + '%' : '--'}
                          </div>
                        </div>
                        <div className="rounded-lg border border-zinc-200 p-3">
                          <div className="text-xs text-zinc-500">总成本</div>
                          <div className="mt-1 text-base font-semibold text-red-600">{costAnalysis.total_cost?.toLocaleString() ?? '--'}</div>
                        </div>
                      </div>
                    </div>
                    {/* 右侧：成本构成饼图 */}
                    <div className="rounded-lg border border-zinc-200 p-4">
                      <div className="mb-2 text-xs font-medium text-zinc-600">成本构成</div>
                      <ReactECharts option={buildCostPieOption(costAnalysis)} style={{ height: 260 }} />
                    </div>
                  </div>
                </CardBody>
              </Card>
            )}

            {/* Plus 版数据为空提示 */}
            {!plusLoading && plusDataLoaded && !svdResult && !costAnalysis && stockPnl.length === 0 && (
              <Card>
                <CardBody>
                  <div className="flex flex-col items-center py-8">
                    <AlertTriangle className="h-10 w-10 text-amber-400 mb-3" />
                    <p className="text-sm text-zinc-600 mb-1">Plus 版报告数据为空</p>
                    <p className="text-xs text-zinc-400 mb-4">可能由于回测数据不足或未关联回测任务</p>
                    <button
                      onClick={handleRegenerate}
                      disabled={regenerating}
                      className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {regenerating ? '生成中...' : '重新生成 Plus 版报告'}
                    </button>
                  </div>
                </CardBody>
              </Card>
            )}

            {/* Plus 版加载失败提示 */}
            {!plusLoading && plusError && !plusDataLoaded && (
              <Card>
                <CardBody>
                  <div className="flex flex-col items-center py-8">
                    <AlertTriangle className="h-10 w-10 text-red-400 mb-3" />
                    <p className="text-sm text-zinc-600 mb-1">Plus 版报告加载失败</p>
                    <p className="text-xs text-zinc-400 mb-4">{plusError}</p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          setPlusError(null)
                          setPlusDataLoaded(false)
                          setPlusData(null)
                        }}
                        className="rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50"
                      >
                        重试
                      </button>
                      <button
                        onClick={handleRegenerate}
                        disabled={regenerating}
                        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                      >
                        {regenerating ? '生成中...' : '重新生成'}
                      </button>
                    </div>
                  </div>
                </CardBody>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}

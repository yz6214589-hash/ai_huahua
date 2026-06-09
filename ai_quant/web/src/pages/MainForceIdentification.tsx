import { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import {
  Shield,
  TrendingUp,
  TrendingDown,
  BarChart3,
  DollarSign,
  Zap,
  Target,
  Eye,
  Loader2,
  Search,
  AlertTriangle,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import {
  analyzeMainForce,
  MainForceAnalysis,
  TimeRange,
  checkDataCompleteness,
} from '@/api/mainforce'

// 主力类型中文标签
const MAINFORCE_TYPE_LABELS: Record<string, string> = {
  institution: '机构主力',
  hot_money: '游资',
  retail: '散户',
}

// 特征名中文映射（与参考代码 7-主力行为识别.py L358-369 对齐）
const FEATURE_NAME_MAP: Record<string, string> = {
  ofi_abs: 'OFI绝对值',
  large_ratio: '大单比例',
  cancel_rate: '撤单率',
  interval_cv: '间隔规律性',
  recovery_speed: '冲击恢复',
  run_length: '方向持续',
  vol_cv: '量变异系数',
  direction_symmetry: '方向对称性',
  limit_ratio: '限价单比例',
  price_volatility: '价格波动',
}

// 主力类型颜色映射
const TYPE_COLOR_MAP: Record<string, { bg: string; text: string; border: string; bar: string }> = {
  institution: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', bar: '#3b82f6' },
  hot_money: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', bar: '#ef4444' },
  retail: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', bar: '#22c55e' },
}

// 买卖方向中文标签和颜色
const DIRECTION_LABELS: Record<string, { label: string; bg: string; text: string; icon: string }> = {
  strong_buy: { label: '强买入', bg: 'bg-red-100', text: 'text-red-700', icon: '▲▲' },
  weak_buy: { label: '弱买入', bg: 'bg-red-50', text: 'text-red-600', icon: '▲' },
  neutral: { label: '中性', bg: 'bg-gray-100', text: 'text-gray-600', icon: '—' },
  weak_sell: { label: '弱卖出', bg: 'bg-green-50', text: 'text-green-600', icon: '▼' },
  strong_sell: { label: '强卖出', bg: 'bg-green-100', text: 'text-green-700', icon: '▼▼' },
}

// 趋势指标中文映射
const VOLUME_TREND_MAP: Record<string, string> = { increasing: '增加', decreasing: '减少', stable: '平稳' }
const PRICE_TREND_MAP: Record<string, string> = { up: '上涨', down: '下跌', sideways: '横盘' }
const CAPITAL_FLOW_MAP: Record<string, string> = { inflow: '流入', outflow: '流出', neutral: '中性' }
const ACTIVITY_LEVEL_MAP: Record<string, string> = { high: '高', medium: '中', low: '低' }

// 时间范围选项
const TIME_RANGE_OPTIONS: Array<{ value: TimeRange; label: string; period: string }> = [
  { value: 'today', label: '今日', period: '1分钟K线' },
  { value: 'yesterday', label: '昨日', period: '1分钟K线' },
  { value: 'last_5_days', label: '近五日', period: '1分钟K线' },
]

// 将特征值归一化到 0-1 范围
function normalizeFeatures(features: Record<string, number>): { names: string[]; values: number[] } {
  const entries = Object.entries(features)
  const values = entries.map(([, v]) => v)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const range = maxVal - minVal || 1
  return {
    names: entries.map(([k]) => FEATURE_NAME_MAP[k] || k),
    values: entries.map(([, v]) => parseFloat((((v - minVal) / range)).toFixed(3))),
  }
}

// 主力类型判定卡片
function TypeClassificationCard({ classification }: { classification: MainForceAnalysis['classification'] }) {
  const typeLabel = MAINFORCE_TYPE_LABELS[classification.primary_type] || classification.primary_type
  const colors = TYPE_COLOR_MAP[classification.primary_type] || TYPE_COLOR_MAP.institution
  const confidencePercent = (classification.confidence * 100).toFixed(1)

  const direction = classification.direction || 'neutral'
  const directionInfo = DIRECTION_LABELS[direction] || DIRECTION_LABELS.neutral
  const ofiSignedRecent = classification.ofi_signed_recent ?? 0
  const ofiSignedFull = classification.ofi_signed ?? 0

  const sortedScores = Object.entries(classification.type_scores).sort(([, a], [, b]) => b - a)

  return (
    <div className={`${colors.bg} border ${colors.border} rounded-xl p-6`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Target className={`w-8 h-8 ${colors.text}`} />
          <div>
            <div className="text-sm text-gray-500">主力类型</div>
            <div className={`text-2xl font-bold ${colors.text}`}>{typeLabel}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">置信度</div>
          <div className={`text-3xl font-bold ${colors.text}`}>{confidencePercent}%</div>
        </div>
      </div>

      {/* 买卖方向徽章 */}
      <div className={`flex items-center justify-between gap-3 mb-4 px-4 py-3 rounded-lg ${directionInfo.bg}`}>
        <div className="flex items-center gap-2">
          <span className={`text-2xl font-bold ${directionInfo.text}`}>{directionInfo.icon}</span>
          <span className={`text-base font-semibold ${directionInfo.text}`}>主力动向：{directionInfo.label}</span>
        </div>
        <div className="text-right text-xs text-gray-500">
          <div>近期 OFI: <span className={`font-mono font-semibold ${directionInfo.text}`}>{ofiSignedRecent > 0 ? '+' : ''}{ofiSignedRecent.toFixed(3)}</span></div>
          <div>全期 OFI: <span className="font-mono">{ofiSignedFull > 0 ? '+' : ''}{ofiSignedFull.toFixed(3)}</span></div>
        </div>
      </div>

      {/* 各类型概率条形图 */}
      <div className="space-y-3">
        {sortedScores.map(([type, score]) => {
          const label = MAINFORCE_TYPE_LABELS[type] || type
          const typeColors = TYPE_COLOR_MAP[type] || TYPE_COLOR_MAP.institution
          const widthPercent = (score * 100).toFixed(1)
          return (
            <div key={type} className="flex items-center gap-3">
              <span className="text-sm text-gray-600 w-16 shrink-0">{label}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${widthPercent}%`, backgroundColor: typeColors.bar }}
                />
              </div>
              <span className="text-sm text-gray-700 w-14 text-right">{(score * 100).toFixed(1)}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// 特征雷达图
function FeatureRadarChart({ features }: { features: Record<string, number> }) {
  const { names, values } = normalizeFeatures(features)

  const option = {
    tooltip: {
      trigger: 'item',
    },
    radar: {
      indicator: names.map((name) => ({ name, max: 1 })),
      shape: 'polygon' as const,
      splitNumber: 4,
      axisName: {
        color: '#4b5563',
        fontSize: 11,
      },
      splitArea: {
        areaStyle: {
          color: ['#f9fafb', '#f3f4f6', '#e5e7eb', '#d1d5db'],
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '特征值',
            areaStyle: {
              color: 'rgba(59, 130, 246, 0.2)',
            },
            lineStyle: {
              color: '#3b82f6',
              width: 2,
            },
            itemStyle: {
              color: '#3b82f6',
            },
          },
        ],
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: '350px' }} />
}

// 趋势指标卡片
function TrendIndicatorCards({ indicators }: { indicators: MainForceAnalysis['indicators'] }) {
  const cards = [
    {
      label: '成交量趋势',
      value: VOLUME_TREND_MAP[indicators.volume_trend] || indicators.volume_trend,
      icon: <BarChart3 className="w-5 h-5" />,
      colorClass: indicators.volume_trend === 'increasing' ? 'text-green-600 bg-green-50' : indicators.volume_trend === 'decreasing' ? 'text-red-600 bg-red-50' : 'text-gray-600 bg-gray-50',
    },
    {
      label: '价格趋势',
      value: PRICE_TREND_MAP[indicators.price_trend] || indicators.price_trend,
      icon: <TrendingUp className="w-5 h-5" />,
      colorClass: indicators.price_trend === 'up' ? 'text-green-600 bg-green-50' : indicators.price_trend === 'down' ? 'text-red-600 bg-red-50' : 'text-gray-600 bg-gray-50',
    },
    {
      label: '资金流向',
      value: CAPITAL_FLOW_MAP[indicators.capital_flow] || indicators.capital_flow,
      icon: <DollarSign className="w-5 h-5" />,
      colorClass: indicators.capital_flow === 'inflow' ? 'text-green-600 bg-green-50' : indicators.capital_flow === 'outflow' ? 'text-red-600 bg-red-50' : 'text-gray-600 bg-gray-50',
    },
    {
      label: '活跃度',
      value: ACTIVITY_LEVEL_MAP[indicators.activity_level] || indicators.activity_level,
      icon: <Zap className="w-5 h-5" />,
      colorClass: indicators.activity_level === 'high' ? 'text-orange-600 bg-orange-50' : indicators.activity_level === 'medium' ? 'text-blue-600 bg-blue-50' : 'text-gray-600 bg-gray-50',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div key={card.label} className={`${card.colorClass} rounded-lg p-4 flex flex-col items-center gap-2`}>
          {card.icon}
          <div className="text-xs opacity-70">{card.label}</div>
          <div className="text-lg font-bold">{card.value}</div>
        </div>
      ))}
    </div>
  )
}

// 信号列表
function SignalList({ signals }: { signals: MainForceAnalysis['signals'] }) {
  if (signals.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-gray-500">
        暂无信号数据
      </div>
    )
  }

  const sortedSignals = [...signals].sort((a, b) => b.date.localeCompare(a.date))

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">类型</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">强度</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">描述</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {sortedSignals.map((signal, idx) => (
            <tr key={`${signal.date}-${idx}`} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm text-gray-900">{signal.date}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  signal.type === 'BUY'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}>
                  {signal.type === 'BUY' ? '买入' : '卖出'}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-900">
                <span className="text-yellow-500">
                  {'*'.repeat(signal.strength)}
                </span>
                <span className="text-gray-300 ml-0.5">
                  {'*'.repeat(Math.max(0, 5 - signal.strength))}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">{signal.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function MainForceIdentification() {
  // 单股分析相关状态
  const [selectedStock, setSelectedStock] = useState<StockSearchItem | null>(null)
  const [timeRange, setTimeRange] = useState<TimeRange>('today')
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<MainForceAnalysis | null>(null)
  const [analysisError, setAnalysisError] = useState('')

  // 触发单股主力行为分析
  const handleAnalyze = async () => {
    if (!selectedStock) {
      setAnalysisError('请选择一只股票')
      return
    }
    setAnalysisLoading(true)
    setAnalysisError('')
    setAnalysisResult(null)
    try {
      const result = await analyzeMainForce(selectedStock.code, timeRange)
      setAnalysisResult(result)
      // 如果后端返回了错误信息（如 QMT 无数据），在结果卡片中显示，无需额外弹窗
      if (result.error) {
        setAnalysisError(result.error)
      }
    } catch (error: any) {
      setAnalysisError(error?.message || '分析失败，请重试')
    }
    setAnalysisLoading(false)
  }

  // 获取当前时间范围的周期描述
  const currentRangeOption = TIME_RANGE_OPTIONS.find((opt) => opt.value === timeRange)

  // 数据完整性检查
  const dataCompleteness = analysisResult ? checkDataCompleteness(analysisResult) : null

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 头部 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            主力识别
          </h1>
          <p className="text-gray-600 mt-1">基于分钟级行情数据识别主力资金动向，辅助风控决策</p>
        </div>

        {/* 单股主力行为分析面板 */}
        <div className="mb-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Eye className="w-5 h-5 text-indigo-600" />
            单股主力行为分析
          </h2>

          {/* 搜索区域 */}
          <div className="flex flex-wrap items-end gap-4 mb-6">
            <div className="flex-1 min-w-[240px]">
              <label className="block text-sm text-gray-600 mb-1">选择股票</label>
              <StockPicker
                value={selectedStock}
                onChange={(val) => setSelectedStock(val as StockSearchItem | null)}
                placeholder="搜索股票代码或名称"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">时间范围</label>
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                {TIME_RANGE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setTimeRange(opt.value)}
                    className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
                      timeRange === opt.value
                        ? 'bg-white text-indigo-700 shadow-sm font-medium'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {currentRangeOption && (
                <div className="text-xs text-gray-400 mt-1">数据周期: {currentRangeOption.period}</div>
              )}
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analysisLoading || !selectedStock}
              className="flex items-center gap-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analysisLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  分析中...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  开始分析
                </>
              )}
            </button>
          </div>

          {/* 错误提示 */}
          {analysisError && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              {analysisError}
            </div>
          )}

          {/* 加载状态 */}
          {analysisLoading && (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
              <span className="text-sm text-gray-500">
                正在通过 QMT 网关分析 {selectedStock?.code}，请稍候...
              </span>
            </div>
          )}

          {/* 分析结果 */}
          {analysisResult && !analysisLoading && (
            <div className="space-y-6">
              {/* 分析股票基本信息 */}
              <div className="flex flex-wrap items-center gap-4 pb-4 border-b border-gray-100">
                <div>
                  <span className="text-lg font-bold text-gray-900">{analysisResult.stock_name}</span>
                  <span className="ml-2 text-sm text-gray-500">{analysisResult.stock_code}</span>
                </div>
                <div className="text-sm text-gray-500 flex flex-wrap gap-3">
                  <span>时间范围: {analysisResult.time_range_label}</span>
                  <span className="flex items-center gap-1">
                    数据条数: <span className={`font-mono font-semibold ${(analysisResult.data_bars ?? 0) === 0 ? 'text-red-500' : 'text-gray-700'}`}>{analysisResult.data_bars ?? 0}</span>
                    {analysisResult.expected_bars !== undefined && analysisResult.expected_bars > 0 && (
                      <span className="text-gray-400">/ {analysisResult.expected_bars}</span>
                    )}
                  </span>
                  <span>分析时间: {analysisResult.analysis_date}</span>
                </div>
              </div>

              {/* QMT 无数据或分析失败的提示 */}
              {analysisResult.error && (
                <div className="flex items-start gap-3 p-4 bg-orange-50 border border-orange-200 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-orange-800">无法完成主力行为分析</div>
                    <div className="text-sm text-orange-700 mt-1 whitespace-pre-line">{analysisResult.error}</div>
                  </div>
                </div>
              )}

              {/* 数据完整性警告（仅在非错误状态下显示） */}
              {!analysisResult.error && dataCompleteness && !dataCompleteness.complete && dataCompleteness.warning && (
                <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <div>
                    <div className="text-sm font-medium text-amber-800">数据完整性警告</div>
                    <div className="text-sm text-amber-700">{dataCompleteness.warning}</div>
                  </div>
                </div>
              )}

              {/* 数据完整性确认（仅在非错误状态下显示） */}
              {!analysisResult.error && dataCompleteness && dataCompleteness.complete && (
                <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
                  <div className="text-sm text-green-700">数据完整，分析结果可靠</div>
                </div>
              )}

              {/* 主力类型判定卡片 + 特征雷达图（仅在有数据时显示） */}
              {!analysisResult.error && (analysisResult.data_bars ?? 0) > 0 && (
                <>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <TypeClassificationCard classification={analysisResult.classification} />
                    <div className="bg-white border border-gray-200 rounded-xl p-4">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">特征雷达图</h3>
                      <FeatureRadarChart features={analysisResult.features} />
                    </div>
                  </div>

                  {/* 趋势指标卡片 */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-3">趋势指标</h3>
                    <TrendIndicatorCards indicators={analysisResult.indicators} />
                  </div>

                  {/* 信号列表 */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-3">交易信号</h3>
                    <div className="border border-gray-200 rounded-lg overflow-hidden">
                      <SignalList signals={analysisResult.signals} />
                    </div>
                  </div>

                  {/* 分析摘要 */}
                  {analysisResult.summary && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">分析摘要</h3>
                      <p className="text-sm text-gray-600 leading-relaxed">{analysisResult.summary}</p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* 无结果占位 */}
          {!analysisResult && !analysisLoading && !analysisError && (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-gray-400">
              <Search className="w-10 h-10 mb-3 opacity-50" />
              选择一只股票，点击"开始分析"查看主力行为分析结果
              <div className="text-xs text-gray-400 mt-2">
                通过 QMT 网关获取分钟级行情数据进行主力行为识别
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

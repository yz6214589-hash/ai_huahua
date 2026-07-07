import { useState } from 'react'
import { postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { Brain, Play, RefreshCcw, TrendingUp, TrendingDown, BarChart3, Hash, Layers, Target, Cpu } from 'lucide-react'

interface MlMetrics {
  accuracy: number
  precision: number
  recall: number
  f1: number
  engine: string
  train_size: number
  test_size: number
  train_positive_rate: number
  test_positive_rate: number
  target_breakouts?: number
  target_high_prob?: number
}

interface FeatureImportance {
  feature: string
  importance: number
}

interface MlTrainResult {
  ok: boolean
  target_code: string
  train_codes: string[]
  engine: string
  metrics: MlMetrics
  feature_importance: FeatureImportance[]
  predictions_count: number
  predictions_high_prob: number
  predictions_sample: Array<[string, number]>
  target_breakout_count: number
  total_samples: number
  entry_period: number
  atr_period: number
  split_date: string
  start: string
  end: string
  stock_breakout_details: Record<string, number>
  error?: string
}

function MetricCard({ label, value, unit = '', icon, tone }: {
  label: string
  value: string | number
  unit?: string
  icon?: React.ReactNode
  tone?: 'up' | 'down' | 'neutral'
}) {
  const cls = tone === 'up' ? 'text-green-600' : tone === 'down' ? 'text-red-600' : 'text-zinc-900'
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
      <div className="flex items-center justify-center gap-1.5 mb-1">
        {icon && <span className="text-zinc-400">{icon}</span>}
      </div>
      <div className={`text-2xl font-bold ${cls}`}>{value}{unit}</div>
      <div className="mt-1 text-xs text-zinc-500">{label}</div>
    </div>
  )
}

function FeatureImportanceChart({ data }: { data: FeatureImportance[] }) {
  if (!data.length) return null
  const maxImp = Math.max(...data.map(d => d.importance), 0.01)
  const featureLabels: Record<string, string> = {
    atr_ratio: 'ATR比率',
    adx: 'ADX',
    vol_ratio: '量比',
    rsi: 'RSI',
    breakout_strength: '突破强度',
    momentum_5d: '5日动量',
    consolidation_days: '盘整天数',
    atr_change: 'ATR变化',
  }
  return (
    <div className="space-y-2">
      {data.map((item) => (
        <div key={item.feature} className="flex items-center gap-3">
          <span className="w-24 text-xs text-zinc-600 text-right shrink-0">
            {featureLabels[item.feature] || item.feature}
          </span>
          <div className="flex-1 h-5 bg-zinc-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${(item.importance / maxImp) * 100}%` }}
            />
          </div>
          <span className="w-12 text-xs text-zinc-500 text-right shrink-0">
            {(item.importance * 100).toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function MlTraining() {
  const [targetStock, setTargetStock] = useState<StockSearchItem | null>(null)
  const [trainingStocks, setTrainingStocks] = useState<StockSearchItem[]>([])
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2025-12-31')
  const [splitDate, setSplitDate] = useState('2025-01-01')
  const [entryPeriod, setEntryPeriod] = useState(20)
  const [atrPeriod, setAtrPeriod] = useState(20)
  const [engine, setEngine] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<MlTrainResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleTargetStockChange = (val: StockSearchItem | StockSearchItem[] | null) => {
    if (val && !Array.isArray(val)) {
      setTargetStock(val)
    } else {
      setTargetStock(null)
    }
  }

  const handleTrainingStocksChange = (val: StockSearchItem | StockSearchItem[] | null) => {
    if (Array.isArray(val)) {
      const filtered = val.filter(s => s.code !== targetStock?.code)
      setTrainingStocks(filtered)
    } else {
      setTrainingStocks([])
    }
  }

  const handleTrain = async () => {
    if (!targetStock) {
      toast('error', '请选择目标股票')
      return
    }
    if (trainingStocks.length === 0) {
      toast('error', '请至少选择1只训练股票')
      return
    }
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const stockCodes = [targetStock.code, ...trainingStocks.map(s => s.code)]
      const res = await postJson<MlTrainResult>('/api/v1/analysis/ml-train', {
        stock_codes: stockCodes,
        start: startDate,
        end: endDate,
        split_date: splitDate,
        entry_period: entryPeriod,
        atr_period: atrPeriod,
        engine: engine,
      })
      if (!res.ok) {
        setError(res.error || '训练失败')
        toast('error', res.error || '训练失败')
      } else {
        setResult(res)
        toast('success', 'ML模型训练完成')
      }
    } catch (e: any) {
      const msg = e?.message || '请求失败'
      setError(msg)
      toast('error', msg)
    } finally {
      setLoading(false)
    }
  }

  const metricTone = (v: number) => {
    if (v >= 0.7) return 'up' as const
    if (v >= 0.4) return 'neutral' as const
    return 'down' as const
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Brain className="h-6 w-6 text-zinc-700" />
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">海龟交易 ML 模型训练</h1>
          <p className="text-sm text-zinc-500">基于多只股票突破事件特征训练分类模型，为海龟策略提供信号过滤</p>
        </div>
      </div>

      {/* 配置面板 */}
      <Card>
        <CardHeader title="训练配置" subtitle="选择股票和参数进行ML模型训练" />
        <CardBody className="space-y-5">
          {/* 目标股票选择 */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1.5 flex items-center gap-2">
              <Target className="h-4 w-4 text-blue-500" />
              目标股票（单选）
            </label>
            <StockPicker
              value={targetStock}
              onChange={handleTargetStockChange}
              mode="single"
              placeholder="搜索并选择目标股票..."
            />
            {targetStock && (
              <div className="mt-2">
                <Badge variant="info" className="text-xs">
                  {targetStock.code} {targetStock.name || ''}
                </Badge>
              </div>
            )}
          </div>

          {/* 训练股票选择 */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1.5 flex items-center gap-2">
              <Layers className="h-4 w-4 text-green-500" />
              训练股票（多选）
            </label>
            <StockPicker
              value={trainingStocks}
              onChange={handleTrainingStocksChange}
              mode="multiple"
              placeholder="搜索并添加训练股票..."
              disabled={!targetStock}
            />
            {trainingStocks.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {trainingStocks.map((s) => (
                  <Badge key={s.code} variant="default" className="text-xs">
                    {s.code} {s.name || ''}
                  </Badge>
                ))}
              </div>
            )}
            {targetStock && trainingStocks.length === 0 && (
              <p className="mt-2 text-xs text-zinc-400">请选择至少1只训练股票用于特征学习</p>
            )}
          </div>

          {/* 日期参数 */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">开始日期</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">结束日期</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">分割日期（训练/测试）</label>
              <input
                type="date"
                value={splitDate}
                onChange={(e) => setSplitDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              />
            </div>
          </div>

          {/* 策略参数 */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                唐奇安通道周期（entry_period）
              </label>
              <input
                type="number"
                min={5}
                max={120}
                value={entryPeriod}
                onChange={(e) => setEntryPeriod(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                ATR计算周期（atr_period）
              </label>
              <input
                type="number"
                min={5}
                max={60}
                value={atrPeriod}
                onChange={(e) => setAtrPeriod(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                ML引擎
              </label>
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              >
                <option value="auto">自动选择（推荐）</option>
                <option value="lightgbm">LightGBM</option>
                <option value="xgboost">XGBoost</option>
                <option value="sklearn">scikit-learn</option>
              </select>
            </div>
          </div>

          {/* 训练按钮 */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleTrain}
              disabled={loading || !targetStock || trainingStocks.length === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <>
                  <RefreshCcw className="h-4 w-4 animate-spin" />
                  训练中...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  开始训练
                </>
              )}
            </button>
            {result && (
              <span className="text-xs text-zinc-500">
                上次训练: {new Date().toLocaleString()}
              </span>
            )}
          </div>
        </CardBody>
      </Card>

      {/* 错误提示 */}
      {error && (
        <Card>
          <CardBody className="bg-red-50">
            <div className="flex items-center gap-2 text-red-600">
              <span className="text-sm font-medium">训练失败:</span>
              <span className="text-sm">{error}</span>
            </div>
          </CardBody>
        </Card>
      )}

      {/* 结果展示 */}
      {result && (
        <div className="space-y-6">
          {/* 评估指标 */}
          <Card>
            <CardHeader title="模型评估指标" subtitle={`引擎: ${result.engine}`} />
            <CardBody>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
                <MetricCard
                  label="准确率"
                  value={result.metrics.accuracy.toFixed(3)}
                  icon={<TrendingUp className="h-4 w-4" />}
                  tone={metricTone(result.metrics.accuracy)}
                />
                <MetricCard
                  label="精确率"
                  value={result.metrics.precision.toFixed(3)}
                  icon={<Target className="h-4 w-4" />}
                  tone={metricTone(result.metrics.precision)}
                />
                <MetricCard
                  label="召回率"
                  value={result.metrics.recall.toFixed(3)}
                  icon={<BarChart3 className="h-4 w-4" />}
                  tone={metricTone(result.metrics.recall)}
                />
                <MetricCard
                  label="F1分数"
                  value={result.metrics.f1.toFixed(3)}
                  icon={<Cpu className="h-4 w-4" />}
                  tone={metricTone(result.metrics.f1)}
                />
                <MetricCard
                  label="训练样本"
                  value={result.metrics.train_size}
                  icon={<Hash className="h-4 w-4" />}
                />
                <MetricCard
                  label="测试样本"
                  value={result.metrics.test_size}
                  icon={<Hash className="h-4 w-4" />}
                />
              </div>
            </CardBody>
          </Card>

          {/* 特征重要性 */}
          <Card>
            <CardHeader title="特征重要性" subtitle="各特征对模型决策的贡献程度" />
            <CardBody>
              <FeatureImportanceChart data={result.feature_importance} />
            </CardBody>
          </Card>

          {/* 预测结果样本 */}
          <Card>
            <CardHeader
              title="预测结果样本"
              subtitle={`共 ${result.predictions_count} 个预测，高置信度 ${result.predictions_high_prob} 个`}
            />
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200">
                      <th className="px-3 py-2 text-left font-medium text-zinc-700">日期</th>
                      <th className="px-3 py-2 text-right font-medium text-zinc-700">突破概率</th>
                      <th className="px-3 py-2 text-center font-medium text-zinc-700">预测类别</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.predictions_sample.map(([date, prob]) => (
                      <tr key={date} className="border-b border-zinc-100">
                        <td className="px-3 py-2 text-zinc-800">{date}</td>
                        <td className="px-3 py-2 text-right">
                          <span className={prob >= 0.5 ? 'text-green-600' : 'text-red-600'}>
                            {(prob * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <Badge variant={prob >= 0.5 ? 'success' : 'default'}>
                            {prob >= 0.5 ? '突破' : '非突破'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>

          {/* 突破事件统计 */}
          <Card>
            <CardHeader title="各股票突破事件统计" subtitle="目标股票与训练股票的突破事件分布" />
            <CardBody>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-800">目标股票</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-600">
                    {result.target_code}
                  </div>
                  <div className="mt-2 text-sm text-blue-700">
                    突破事件: {result.target_breakout_count} 次
                  </div>
                </div>
                <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Layers className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium text-green-800">训练股票</span>
                  </div>
                  <div className="text-sm text-green-700 space-y-1">
                    {Object.entries(result.stock_breakout_details).map(([code, count]) => (
                      <div key={code} className="flex justify-between">
                        <span>{code}</span>
                        <span className="font-medium">{count} 次</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}

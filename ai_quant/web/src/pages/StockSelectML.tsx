import { Loading } from '@/components/Loading'
import { useState, useRef, useEffect, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCcw, Play, Settings, Trash2, ChevronDown } from 'lucide-react'

// 训练进度阶段定义
interface TrainingStatus {
  stage: string
  progress: number
  message: string
}

const STAGE_LABELS: Record<string, string> = {
  queued: '排队等待',
  pool: '获取股票池',
  features: '特征提取',
  samples: '训练样本构建',
  training: '模型训练',
  done: '训练完成',
  error: '训练失败',
}

interface Prediction {
  code: string
  name: string
  signal: string
  confidence: number
  reasons: string[]
  indicators: {
    rsi?: number
    macd?: number
    ma20?: number
    close: number
  }
}

interface SignalApiItem {
  code: string
  name: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasons: string[]
  indicators: {
    rsi?: number
    macd?: number
    ma20?: number
    close: number
  }
}

interface SavedModel {
  model_id: string
  model_type: string
  engine: string
  trained_at: string
  train_samples: number
  stock_count: number
}

const MODEL_FRAMEWORKS = [
  { key: 'lightgbm', label: 'LightGBM', desc: '梯度提升树，训练快、对特征交叉敏感' },
  { key: 'xgboost', label: 'XGBoost', desc: '极端梯度提升，正则化强，拟合稳定' },
]

const SIGNAL_MAP: Record<string, string> = {
  BUY: '强烈买入',
  SELL: '卖出',
  HOLD: '持有',
}

const SIGNAL_TONE: Record<string, 'green' | 'blue' | 'zinc' | 'amber'> = {
  BUY: 'green',
  SELL: 'amber',
  HOLD: 'zinc',
}

const STOCK_SCOPES = [
  { key: 'all', label: '全部股票' },
  { key: 'sh', label: '沪市主板' },
  { key: 'sz_main', label: '深市主板' },
  { key: 'cyb', label: '创业板' },
  { key: 'kcb', label: '科创板' },
]

function SignalBadge({ signal }: { signal: string }) {
  const display = SIGNAL_MAP[signal] || signal
  const tone = SIGNAL_TONE[signal] || 'zinc'
  return <Badge tone={tone}>{display}</Badge>
}

// 格式化日期时间显示
function formatDateTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return iso
  }
}

// 训练进度组件
function TrainingProgress({ status }: { status: TrainingStatus | null }) {
  if (!status) return null
  const isError = status.stage === 'error'
  const isDone = status.stage === 'done'
  const stageOrder = ['queued', 'pool', 'features', 'samples', 'training', 'done']
  const currentIdx = stageOrder.indexOf(status.stage)
  const barColor = isError ? 'bg-red-500' : isDone ? 'bg-green-500' : 'bg-blue-500'

  return (
    <div className="space-y-3">
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-zinc-100">
        <div
          className={`absolute left-0 top-0 h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.min(status.progress, 100)}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          {['pool', 'features', 'samples', 'training'].map((s, i) => {
            const thisIdx = stageOrder.indexOf(s)
            const isActive = currentIdx === thisIdx
            const isPast = currentIdx > thisIdx
            return (
              <div key={s} className="flex items-center gap-1">
                {i > 0 && <span className="text-zinc-300">-</span>}
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                    isActive ? 'bg-blue-100 font-medium text-blue-700' :
                    isPast ? 'bg-green-50 text-green-600' :
                    'bg-zinc-50 text-zinc-400'
                  }`}
                >
                  {isPast ? '\u2713 ' : ''}
                  {STAGE_LABELS[s]}
                </span>
              </div>
            )
          })}
        </div>
        <span className={`font-medium ${isError ? 'text-red-600' : 'text-zinc-500'}`}>
          {status.progress}%
        </span>
      </div>
      <p className={`text-sm ${isError ? 'text-red-600' : 'text-zinc-600'}`}>
        {status.message}
      </p>
    </div>
  )
}

export default function StockSelectML() {
  // === 训练区状态 ===
  const [trainFramework, setTrainFramework] = useState('lightgbm')
  const [training, setTraining] = useState(false)
  const [trainStatus, setTrainStatus] = useState<TrainingStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // === 预测区状态 ===
  const [predictFramework, setPredictFramework] = useState('lightgbm')
  const [savedModels, setSavedModels] = useState<SavedModel[]>([])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [stockScope, setStockScope] = useState('all')
  const [predicting, setPredicting] = useState(false)
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [predictError, setPredictError] = useState<string | null>(null)
  const [modelInfo, setModelInfo] = useState<{ model_id: string; engine: string; trained_at: string } | null>(null)

  // === 分页 ===
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 50

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // 加载已训练的模型列表
  const loadModels = useCallback(async () => {
    try {
      const r = await fetchJson<{ models: SavedModel[] }>('/api/v1/signals/models')
      setSavedModels(r.models || [])
    } catch {
      // 忽略
    }
  }, [])

  useEffect(() => {
    loadModels()
  }, [loadModels])

  // 按预测区选的框架过滤模型列表
  const frameworkModels = savedModels.filter(m => m.model_type === predictFramework)

  // 切换框架时自动选中最新模型
  useEffect(() => {
    if (frameworkModels.length > 0 && !frameworkModels.find(m => m.model_id === selectedModelId)) {
      setSelectedModelId(frameworkModels[0].model_id)
    } else if (frameworkModels.length === 0) {
      setSelectedModelId('')
    }
  }, [predictFramework, frameworkModels])

  // === 训练逻辑 ===
  const startPolling = (taskId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchJson<TrainingStatus>(`/api/v1/signals/train-status/${taskId}`)
        setTrainStatus(status)
        if (status.stage === 'done' || status.stage === 'error') {
          setTraining(false)
          if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
          if (status.stage === 'done') {
            loadModels()
          }
        }
      } catch {
        // 忽略
      }
    }, 1500)
  }

  const handleStartTraining = async () => {
    setTraining(true)
    setTrainStatus({ stage: 'queued', progress: 0, message: '启动训练任务...' })
    try {
      const result = await postJson<{ task_id: string }>('/api/v1/signals/train', {
        model: trainFramework,
      })
      startPolling(result.task_id)
    } catch (e) {
      setTraining(false)
      setTrainStatus({ stage: 'error', progress: 0, message: e instanceof Error ? e.message : '训练启动失败' })
    }
  }

  // === 删除模型 ===
  const handleDeleteModel = async (modelId: string) => {
    try {
      await fetchJson(`/api/v1/signals/models/${modelId}`, { method: 'DELETE' })
      await loadModels()
      if (selectedModelId === modelId) {
        setSelectedModelId('')
      }
    } catch {
      // 忽略
    }
  }

  // === 预测逻辑 ===
  const handlePredict = async () => {
    if (!selectedModelId) return
    setPredicting(true)
    setPredictError(null)
    setCurrentPage(1)
    try {
      const r = await postJson<{ items: SignalApiItem[]; total: number; model_info: any }>(
        '/api/v1/signals/ml-predict',
        {
          model_id: selectedModelId,
          stock_scope: stockScope,
        },
      )
      setPredictions((r.items || []).map((item) => ({
        code: item.code,
        name: item.name,
        signal: SIGNAL_MAP[item.signal] || item.signal,
        confidence: item.confidence,
        reasons: item.reasons || [],
        indicators: item.indicators,
      })))
      setModelInfo(r.model_info || null)
    } catch (e) {
      setPredictError(e instanceof Error ? e.message : '预测失败')
      setPredictions([])
    } finally {
      setPredicting(false)
    }
  }

  // 分页计算
  const totalPages = Math.ceil(predictions.length / pageSize)
  const pageStart = (currentPage - 1) * pageSize
  const pageEnd = pageStart + pageSize
  const pageItems = predictions.slice(pageStart, pageEnd)

  return (
    <div className="space-y-4">
      {/* ========== 训练区 ========== */}
      <Card>
        <CardHeader title="一、模型训练" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {MODEL_FRAMEWORKS.map((m) => (
              <div
                key={m.key}
                onClick={() => !training && setTrainFramework(m.key)}
                className={`cursor-pointer rounded-lg border p-4 transition ${
                  trainFramework === m.key
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-zinc-100 hover:border-zinc-300'
                } ${training ? 'pointer-events-none opacity-60' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="text-sm font-medium text-zinc-900">{m.label}</div>
                  {trainFramework === m.key && <Badge tone="blue">已选</Badge>}
                </div>
                <p className="mt-1 text-xs text-zinc-500">{m.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 space-y-3">
            <button
              onClick={handleStartTraining}
              disabled={training}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
            >
              <Settings className={`h-4 w-4 ${training ? 'animate-spin' : ''}`} />
              {training ? '训练中...' : '开始训练'}
            </button>
            {(training || trainStatus) && <TrainingProgress status={trainStatus} />}
          </div>
        </CardBody>
      </Card>

      {/* ========== 预测区 ========== */}
      <Card>
        <CardHeader title="二、模型预测" />
        <CardBody>
          {/* 第1步：选模型框架 */}
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-medium text-zinc-500">第1步：选择模型框架</label>
              <div className="flex gap-2">
                {MODEL_FRAMEWORKS.map((m) => (
                  <button
                    key={m.key}
                    onClick={() => setPredictFramework(m.key)}
                    className={`rounded-lg border px-4 py-2 text-sm transition ${
                      predictFramework === m.key
                        ? 'border-blue-300 bg-blue-50 font-medium text-blue-700'
                        : 'border-zinc-200 text-zinc-600 hover:border-zinc-300'
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 第2步：选具体模型 */}
            <div>
              <label className="mb-2 block text-xs font-medium text-zinc-500">
                第2步：选择已训练的模型
                {frameworkModels.length > 0 && (
                  <span className="ml-2 text-zinc-400">（共 {frameworkModels.length} 个）</span>
                )}
              </label>
              {frameworkModels.length === 0 ? (
                <div className="rounded-lg border border-dashed border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-400">
                  暂无已训练的 {MODEL_FRAMEWORKS.find(m => m.key === predictFramework)?.label} 模型，请先在上方完成训练
                </div>
              ) : (
                <div className="space-y-2">
                  {frameworkModels.map((m) => (
                    <div
                      key={m.model_id}
                      onClick={() => setSelectedModelId(m.model_id)}
                      className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 transition ${
                        selectedModelId === m.model_id
                          ? 'border-blue-300 bg-blue-50'
                          : 'border-zinc-100 hover:border-zinc-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="radio"
                          checked={selectedModelId === m.model_id}
                          onChange={() => setSelectedModelId(m.model_id)}
                          className="h-4 w-4 text-blue-600"
                        />
                        <div>
                          <div className="text-sm font-medium text-zinc-900">
                            {m.engine} - {formatDateTime(m.trained_at)}
                          </div>
                          <div className="text-xs text-zinc-500">
                            训练样本: {m.train_samples} | 股票数: {m.stock_count}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteModel(m.model_id) }}
                        className="rounded p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-500"
                        title="删除此模型"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 第3步：选股票范围 */}
            <div>
              <label className="mb-2 block text-xs font-medium text-zinc-500">第3步：选择预测范围</label>
              <div className="flex flex-wrap gap-2">
                {STOCK_SCOPES.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setStockScope(s.key)}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                      stockScope === s.key
                        ? 'border-blue-300 bg-blue-50 font-medium text-blue-700'
                        : 'border-zinc-200 text-zinc-600 hover:border-zinc-300'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 预测按钮 */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handlePredict}
                disabled={predicting || !selectedModelId}
                className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40"
              >
                <Play className={`h-4 w-4 ${predicting ? 'animate-pulse' : ''}`} />
                {predicting ? '预测中...' : '运行预测'}
              </button>
              {modelInfo && (
                <span className="text-xs text-zinc-400">
                  当前模型: {modelInfo.engine} | 训练时间: {formatDateTime(modelInfo.trained_at)}
                </span>
              )}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ========== 结果区 ========== */}
      <Card>
        <CardHeader title="预测信号结果" />
        <CardBody className="p-0">
          {predicting && predictions.length === 0 ? (
            <Loading className="py-8" />
          ) : predictError ? (
            <div className="flex flex-col items-center px-4 py-8">
              <p className="text-sm text-red-600">{predictError}</p>
              <button
                onClick={handlePredict}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                重新预测
              </button>
            </div>
          ) : predictions.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <p className="text-sm text-zinc-500">
                {selectedModelId
                  ? '请点击"运行预测"按钮生成信号'
                  : '请先选择模型框架和已训练的模型'}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500">
                    <tr>
                      <th className="px-3 py-2">#</th>
                      <th className="px-3 py-2">股票</th>
                      <th className="px-3 py-2">信号</th>
                      <th className="px-3 py-2 text-right">置信度</th>
                      <th className="px-3 py-2">指标</th>
                      <th className="px-3 py-2">理由</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((p, idx) => (
                      <tr key={p.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                        <td className="px-3 py-2 text-xs text-zinc-400">{pageStart + idx + 1}</td>
                        <td className="px-3 py-2">
                          <div className="text-sm font-medium text-zinc-900">{p.code}</div>
                          <div className="text-xs text-zinc-500">{p.name}</div>
                        </td>
                        <td className="px-3 py-2"><SignalBadge signal={p.signal} /></td>
                        <td className="px-3 py-2 text-right">
                          <div className="text-sm font-bold text-zinc-900">{(p.confidence * 100).toFixed(1)}%</div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1 text-xs text-zinc-600">
                            {p.indicators?.rsi !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">RSI:{p.indicators.rsi.toFixed(1)}</span>}
                            {p.indicators?.macd !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">MACD:{p.indicators.macd.toFixed(2)}</span>}
                            {p.indicators?.ma20 !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">MA20:{p.indicators.ma20.toFixed(1)}</span>}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <ul className="list-inside list-disc text-xs text-zinc-500">
                            {(p.reasons || []).slice(0, 2).map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
                  <span className="text-xs text-zinc-500">
                    共 {predictions.length} 条，第 {currentPage}/{totalPages} 页
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                      disabled={currentPage <= 1}
                      className="rounded border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
                    >
                      上一页
                    </button>
                    {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                      let page: number
                      if (totalPages <= 7) {
                        page = i + 1
                      } else if (currentPage <= 4) {
                        page = i + 1
                      } else if (currentPage >= totalPages - 3) {
                        page = totalPages - 6 + i
                      } else {
                        page = currentPage - 3 + i
                      }
                      return (
                        <button
                          key={page}
                          onClick={() => setCurrentPage(page)}
                          className={`rounded border px-3 py-1 text-xs ${
                            page === currentPage
                              ? 'border-blue-300 bg-blue-50 font-medium text-blue-700'
                              : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                          }`}
                        >
                          {page}
                        </button>
                      )
                    })}
                    <button
                      onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                      disabled={currentPage >= totalPages}
                      className="rounded border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="模型说明" />
        <CardBody>
          <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-600">
            <p>本模块使用 LightGBM / XGBoost 机器学习模型对股票进行走势预测。</p>
            <p className="mt-2"><strong>训练流程</strong>：特征提取（19个技术指标） {'->'} 训练样本构建（未来5日涨幅{'>'}2%为正例） {'->'} 模型训练。</p>
            <p className="mt-2"><strong>预测流程</strong>：选择已训练模型 {'->'} 选择股票范围 {'->'} 运行预测。训练好的模型会持久化保存，可反复使用。</p>
            <p className="mt-2">预测结果仅供参考，不构成投资建议。</p>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

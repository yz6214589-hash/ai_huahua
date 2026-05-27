import { useState, useEffect } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCcw, Play } from 'lucide-react'

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

const MODEL_OPTIONS = [
  { key: 'lstm', label: 'LSTM 神经网络', desc: '适合捕捉时序依赖，能学习股价波动的长期模式' },
  { key: 'xgboost', label: 'XGBoost', desc: '擅长特征交叉，对基本面因子效果较好' },
  { key: 'ensemble', label: 'LSTM+XGBoost集成', desc: '结合两者优势，综合预测最稳定' },
  { key: 'transformer', label: 'Transformer', desc: '注意力机制，擅长多因子长序列预测（开发中）' },
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

function SignalBadge({ signal }: { signal: string }) {
  const display = SIGNAL_MAP[signal] || signal
  const tone = SIGNAL_TONE[signal] || 'zinc'
  return <Badge tone={tone}>{display}</Badge>
}

export default function StockSelectML() {
  const [selectedModel, setSelectedModel] = useState('ensemble')
  const [running, setRunning] = useState(false)
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPredictions = async (model: string) => {
    setLoading(true)
    setError(null)
    try {
      const r = await postJson<{ items: SignalApiItem[]; total: number }>('/api/v1/signals/rule-based', { model })
      setPredictions((r.items || []).map((item) => ({
        code: item.code,
        name: item.name,
        signal: SIGNAL_MAP[item.signal] || item.signal,
        confidence: item.confidence,
        reasons: item.reasons || [],
        indicators: item.indicators,
      })))
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setPredictions([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPredictions(selectedModel)
  }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      await loadPredictions(selectedModel)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="模型选择" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {MODEL_OPTIONS.map((m) => {
              const disabled = m.key === 'transformer'
              return (
                <div
                  key={m.key}
                  onClick={() => !disabled && setSelectedModel(m.key)}
                  className={`cursor-pointer rounded-lg border p-4 transition ${
                    selectedModel === m.key
                      ? 'border-blue-300 bg-blue-50'
                      : disabled
                      ? 'cursor-not-allowed border-zinc-100 bg-zinc-50 opacity-50'
                      : 'border-zinc-100 hover:border-zinc-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="text-sm font-medium text-zinc-900">{m.label}</div>
                    {selectedModel === m.key && <Badge tone="blue">已选</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">{m.desc}</p>
                </div>
              )
            })}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleRun}
              disabled={running || loading}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running || loading ? '信号生成中...' : '重新运行预测'}
            </button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="规则引擎信号结果" />
        <CardBody className="p-0">
          {loading && predictions.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">加载中...</div>
          ) : error && predictions.length === 0 ? (
            <div className="flex flex-col items-center px-4 py-8">
              <p className="text-sm text-red-600">{error}</p>
              <button
                onClick={handleRun}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                重新加载
              </button>
            </div>
          ) : predictions.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无信号数据</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">信号</th>
                    <th className="px-3 py-2 text-right">置信度</th>
                    <th className="px-3 py-2">指标</th>
                    <th className="px-3 py-2">理由</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((p) => {
                    const ind = p.indicators
                    return (
                      <tr key={p.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                        <td className="px-3 py-2">
                          <div className="text-sm font-medium text-zinc-900">{p.code}</div>
                          <div className="text-xs text-zinc-500">{p.name}</div>
                        </td>
                        <td className="px-3 py-2"><SignalBadge signal={p.signal} /></td>
                        <td className="px-3 py-2 text-right">
                          <div className="text-sm font-bold text-zinc-900">{p.confidence.toFixed(1)}%</div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1 text-xs text-zinc-600">
                            {ind?.rsi !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">RSI:{ind.rsi.toFixed(1)}</span>}
                            {ind?.macd !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">MACD:{ind.macd.toFixed(2)}</span>}
                            {ind?.ma20 !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">MA20:{ind.ma20.toFixed(1)}</span>}
                            {ind?.close !== undefined && <span className="rounded bg-zinc-100 px-1.5 py-0.5">收盘:{ind.close.toFixed(1)}</span>}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <ul className="list-inside list-disc text-xs text-zinc-500">
                            {(p.reasons || []).slice(0, 2).map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                            {(p.reasons || []).length > 2 && (
                              <li className="text-zinc-400">+{(p.reasons || []).length - 2}条...</li>
                            )}
                          </ul>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="模型说明" />
        <CardBody>
          <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-600">
            <p>本模块使用规则引擎对股票进行走势预测。模型基于过去120个交易日的 OHLCV 数据、动量指标、技术指标（RSI、MACD、布林带等）以及基本面数据（PE、PB、ROE 等）进行训练。</p>
            <p className="mt-2">预测结果仅供参考，不构成投资建议。实际交易需结合市场环境、政策变化、资金管理等因素综合判断。</p>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
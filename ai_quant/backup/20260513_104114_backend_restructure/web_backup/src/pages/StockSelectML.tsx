import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCcw, Play } from 'lucide-react'

const MOCK_PREDICTIONS = [
  { code: '600519.SH', name: '贵州茅台', signal: '强烈买入', confidence: 88.5, probUp: 0.85, probDown: 0.08, probHold: 0.07, target: 1850, stop: 1620, model: 'LSTM + XGBoost集成', date: '2024-12-15' },
  { code: '300750.SZ', name: '宁德时代', signal: '买入', confidence: 72.3, probUp: 0.72, probDown: 0.15, probHold: 0.13, target: 295, stop: 245, model: 'LSTM + XGBoost集成', date: '2024-12-15' },
  { code: '002475.SZ', name: '立讯精密', signal: '买入', confidence: 68.9, probUp: 0.69, probDown: 0.18, probHold: 0.13, target: 48, stop: 38, model: 'XGBoost', date: '2024-12-15' },
  { code: '600036.SH', name: '招商银行', signal: '持有', confidence: 55.2, probUp: 0.45, probDown: 0.30, probHold: 0.25, target: 38, stop: 32, model: 'LSTM', date: '2024-12-15' },
  { code: '688041.SH', name: '寒武纪', signal: '谨慎买入', confidence: 58.7, probUp: 0.59, probDown: 0.25, probHold: 0.16, target: 165, stop: 110, model: 'LSTM + XGBoost集成', date: '2024-12-15' },
  { code: '000858.SZ', name: '五粮液', signal: '买入', confidence: 65.4, probUp: 0.65, probDown: 0.20, probHold: 0.15, target: 168, stop: 142, model: 'LSTM + XGBoost集成', date: '2024-12-15' },
]

const MODELS = [
  { key: 'lstm', label: 'LSTM 神经网络', desc: '适合捕捉时序依赖，能学习股价波动的长期模式', accuracy: '68.2%', recall: '71.5%' },
  { key: 'xgboost', label: 'XGBoost', desc: '擅长特征交叉，对基本面因子效果较好', accuracy: '72.8%', recall: '74.1%' },
  { key: 'ensemble', label: 'LSTM+XGBoost集成', desc: '结合两者优势，综合预测最稳定', accuracy: '75.3%', recall: '78.6%' },
  { key: 'transformer', label: 'Transformer', desc: '注意力机制，擅长多因子长序列预测（开发中）', accuracy: '—', recall: '—' },
]

function SignalBadge({ signal }: { signal: string }) {
  const tone = signal.includes('强烈') ? 'green' : signal.includes('买入') ? 'blue' : signal.includes('谨慎') ? 'amber' : 'zinc'
  return <Badge tone={tone}>{signal}</Badge>
}

function ProbBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-6 text-zinc-500">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100">
        <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, backgroundColor: color }} />
      </div>
      <span className="w-10 text-right text-zinc-600">{(pct * 100).toFixed(0)}%</span>
    </div>
  )
}

export default function StockSelectML() {
  const [selectedModel, setSelectedModel] = useState('ensemble')
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    setRunning(true)
    await new Promise((r) => setTimeout(r, 2000))
    setRunning(false)
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="模型选择" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {MODELS.map((m) => (
              <div
                key={m.key}
                onClick={() => m.accuracy !== '—' && setSelectedModel(m.key)}
                className={`cursor-pointer rounded-lg border p-4 transition ${
                  selectedModel === m.key
                    ? 'border-blue-300 bg-blue-50'
                    : m.accuracy === '—'
                    ? 'cursor-not-allowed border-zinc-100 bg-zinc-50 opacity-50'
                    : 'border-zinc-100 hover:border-zinc-300'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="text-sm font-medium text-zinc-900">{m.label}</div>
                  {selectedModel === m.key && <Badge tone="blue">已选</Badge>}
                </div>
                <p className="mt-1 text-xs text-zinc-500">{m.desc}</p>
                <div className="mt-2 flex gap-3">
                  <div className="text-xs">
                    <div className="text-zinc-400">准确率</div>
                    <div className="font-medium text-zinc-700">{m.accuracy}</div>
                  </div>
                  <div className="text-xs">
                    <div className="text-zinc-400">召回率</div>
                    <div className="font-medium text-zinc-700">{m.recall}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleRun}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running ? '模型预测中…' : '重新运行预测'}
            </button>
            <span className="text-xs text-zinc-400">数据更新：2024-12-15 · 基于过去120日数据训练</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="模型预测结果" />
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2">股票</th>
                  <th className="px-3 py-2">信号</th>
                  <th className="px-3 py-2 text-right">置信度</th>
                  <th className="px-3 py-2">上涨/下跌/持有概率</th>
                  <th className="px-3 py-2 text-right">目标价</th>
                  <th className="px-3 py-2 text-right">止损价</th>
                  <th className="px-3 py-2">使用模型</th>
                  <th className="px-3 py-2">预测日期</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_PREDICTIONS.map((p) => (
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
                      <div className="space-y-1">
                        <ProbBar label="↑" pct={p.probUp} color="#4ade80" />
                        <ProbBar label="↓" pct={p.probDown} color="#f87171" />
                        <ProbBar label="—" pct={p.probHold} color="#d1d5db" />
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-zinc-900">{p.target}</td>
                    <td className="px-3 py-2 text-right text-red-500">{p.stop}</td>
                    <td className="px-3 py-2 text-xs text-zinc-500">{p.model}</td>
                    <td className="px-3 py-2 text-xs text-zinc-400">{p.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="模型说明" />
        <CardBody>
          <div className="rounded-lg border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-600">
            <p>本模块使用机器学习模型对股票进行走势预测。模型基于过去120个交易日的 OHLCV 数据、动量指标、技术指标（RSI、MACD、布林带等）以及基本面数据（PE、PB、ROE 等）进行训练。</p>
            <p className="mt-2">预测结果仅供参考，不构成投资建议。实际交易需结合市场环境、政策变化、资金管理等因素综合判断。</p>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowRight, CheckCircle } from 'lucide-react'

interface StrategyDef {
  strategy_id: string
  name: string
  description: string
  pros: string[]
  cons: string[]
  params_schema: Record<string, {
    type: string
    label: string
    help: string
    min?: number
    max?: number
    step?: number
    default?: number
    values?: string[]
  }>
  default_params: Record<string, unknown>
}

export default function StrategyLibrary() {
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchJson<{ strategies: StrategyDef[] }>('/api/analysis/strategies')
      .then((r) => setStrategies(r.strategies || []))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">共 {strategies.length} 种策略</div>
      </div>
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}
      {loading ? <div className="text-sm text-zinc-500">加载中…</div> : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {strategies.map((s) => (
          <Card key={s.strategy_id}>
            <CardHeader
              title={s.name}
              right={
                <button
                  onClick={() => setExpandedId(expandedId === s.strategy_id ? null : s.strategy_id)}
                  className="text-xs text-zinc-500 hover:text-zinc-900"
                >
                  {expandedId === s.strategy_id ? '收起详情' : '查看详情'}
                </button>
              }
            />
            <CardBody>
              <p className="text-xs text-zinc-600 line-clamp-2">{s.description}</p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="inline-flex items-center gap-1 rounded-md border border-green-200 bg-green-50 px-2 py-0.5 text-xs text-green-700">
                  <CheckCircle className="h-3 w-3" />
                  优点
                </span>
                {s.pros.slice(0, 2).map((p) => (
                  <span key={p} className="rounded-md border border-zinc-100 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">{p}</span>
                ))}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="rounded-md border border-red-200 bg-red-50 px-2 py-0.5 text-xs text-red-700">缺点</span>
                {s.cons.slice(0, 2).map((c) => (
                  <span key={c} className="rounded-md border border-zinc-100 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">{c}</span>
                ))}
              </div>

              {expandedId === s.strategy_id && (
                <div className="mt-4 space-y-4 border-t border-zinc-100 pt-4">
                  <div>
                    <div className="mb-2 text-xs font-semibold text-zinc-900">参数说明</div>
                    <div className="space-y-2">
                      {Object.entries(s.params_schema).map(([key, param]) => (
                        <div key={key} className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-zinc-900">{param.label}</span>
                            <Badge tone="blue">{param.type}</Badge>
                          </div>
                          <div className="mt-1 text-xs text-zinc-500">{param.help}</div>
                          <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
                            {param.min !== undefined && <span>最小：{param.min}</span>}
                            {param.max !== undefined && <span>最大：{param.max}</span>}
                            {param.step !== undefined && <span>步长：{param.step}</span>}
                            <span>默认：{param.default ?? String(s.default_params[key] ?? '—')}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <a
                      href="/strategy/instances"
                      className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                    >
                      创建实例 <ArrowRight className="h-3 w-3" />
                    </a>
                    <a
                      href="/strategy/backtest"
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                    >
                      立即回测 <ArrowRight className="h-3 w-3" />
                    </a>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}

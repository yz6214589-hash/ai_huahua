import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { useEffect, useMemo, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import type { RiskApproveRequest, RiskApproveResponse } from '@/api/types'
import { Play } from 'lucide-react'

type RiskStatus = {
  source: string
  status: string
  features: string[]
}

export default function RiskApprove() {
  const [data, setData] = useState<RiskStatus | null>(null)
  const [orderCode, setOrderCode] = useState('')
  const [direction, setDirection] = useState<'buy' | 'sell'>('buy')
  const [amount, setAmount] = useState('100000')
  const [price, setPrice] = useState('0')
  const [quantity, setQuantity] = useState('0')
  const [totalAsset, setTotalAsset] = useState('1000000')
  const [currentPrice, setCurrentPrice] = useState('0')
  const [atr14, setAtr14] = useState('0')
  const [newsText, setNewsText] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [resp, setResp] = useState<RiskApproveResponse | null>(null)

  useEffect(() => {
    fetchJson<RiskStatus>('/api/v1/risk/status').then(setData).catch(() => null)
  }, [])

  const payload = useMemo<RiskApproveRequest | null>(() => {
    const code = orderCode.trim()
    if (!code) return null
    const amt = Number(amount || 0)
    const px = Number(price || 0)
    const qty = Number(quantity || 0)
    const ta = Number(totalAsset || 0)
    const cp = Number(currentPrice || 0)
    const a = Number(atr14 || 0)
    return {
      order: { stock_code: code, direction, amount: isFinite(amt) ? amt : 0, price: isFinite(px) ? px : 0, quantity: isFinite(qty) ? qty : 0 },
      portfolio: { total_asset: isFinite(ta) ? ta : 0, prices: cp > 0 ? { [code]: cp } : {}, atr: a > 0 ? { [code]: a } : {} },
      context: { news_text: String(newsText || '') },
    }
  }, [orderCode, direction, amount, price, quantity, totalAsset, currentPrice, atr14, newsText])

  const run = async () => {
    if (!payload) { setErr('请填写股票代码'); return }
    setLoading(true)
    setErr(null)
    setResp(null)
    try {
      const r = await postJson<RiskApproveResponse>('/api/v1/risk/approve', payload)
      setResp(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const tone = (d: string) => d === 'APPROVE' ? 'green' : d === 'WARN' ? 'amber' : d === 'REJECT' ? 'red' : 'zinc'

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="风控审批" />
          <CardBody className="space-y-3 text-sm">
            <div className="flex items-center gap-4 text-xs text-zinc-500">
              <span>模块：{data?.source || '—'}</span>
              <span>状态：{data?.status || 'loading'}</span>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
              能力：{(data?.features || []).join(' / ') || '—'}
            </div>

            {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="mb-1 text-xs text-zinc-500">股票代码 *</div>
                  <input
                    value={orderCode}
                    onChange={(e) => setOrderCode(e.target.value)}
                    placeholder="600519.SH"
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">方向</div>
                  <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value as 'buy' | 'sell')}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">下单金额（元）</div>
                  <input
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">价格（元）</div>
                  <input
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">数量（股）</div>
                  <input
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">总资产（元）</div>
                  <input
                    value={totalAsset}
                    onChange={(e) => setTotalAsset(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">当前价（可选）</div>
                  <input
                    value={currentPrice}
                    onChange={(e) => setCurrentPrice(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">ATR14（可选）</div>
                  <input
                    value={atr14}
                    onChange={(e) => setAtr14(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
              </div>
              <div>
                <div className="mb-1 text-xs text-zinc-500">新闻/上下文（可选）</div>
                <textarea
                  value={newsText}
                  onChange={(e) => setNewsText(e.target.value)}
                  rows={3}
                  placeholder="填写相关市场新闻或上下文信息，有助于风控模型做出更准确判断"
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={run}
                className={cn(
                  'inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60'
                )}
              >
                <Play className="h-4 w-4" />
                {loading ? '审批中…' : '提交审批'}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader title="审批结果" />
          <CardBody>
            {resp ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-zinc-900">决策结论</span>
                  <Badge tone={tone(resp.decision)}>{resp.decision}</Badge>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-700">
                  {resp.reason}
                </div>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[
                    { label: '规则', value: resp.rule_name || '—' },
                    { label: '最大仓位', value: `${Math.round((resp.max_position_pct || 0) * 100)}%` },
                    { label: '建议金额', value: resp.suggested_amount != null ? `${resp.suggested_amount.toLocaleString()} 元` : '—' },
                    { label: '建议数量', value: resp.suggested_quantity != null ? `${resp.suggested_quantity} 股` : '—' },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-lg border border-zinc-100 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-400">{label}</div>
                      <div className="mt-0.5 text-sm font-medium text-zinc-900">{value}</div>
                    </div>
                  ))}
                </div>
                {resp.checks?.length ? (
                  <div>
                    <div className="mb-2 text-xs font-semibold text-zinc-900">规则明细</div>
                    <div className="space-y-2">
                      {resp.checks.map((c, i) => (
                        <div key={i} className="flex items-start justify-between gap-3 rounded-lg border border-zinc-100 bg-white px-3 py-2 text-sm">
                          <div>
                            <Badge tone={tone(c.decision)}>{c.decision}</Badge>
                            <div className="mt-1 text-xs text-zinc-500">{c.rule_name}</div>
                          </div>
                          <div className="text-right text-xs text-zinc-600">{c.reason}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-zinc-500">填写左侧表单并提交审批，结果将在此处展示</div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

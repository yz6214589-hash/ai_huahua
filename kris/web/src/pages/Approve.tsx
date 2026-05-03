import { useState } from 'react'
import { fetchJson } from '@/api/client'
import type { ApproveRequest, Direction, RiskDecisionOut } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DecisionBadge } from '@/components/DecisionBadge'

export default function ApprovePage() {
  const [stockCode, setStockCode] = useState('510050.SH')
  const [direction, setDirection] = useState<Direction>('buy')
  const [amount, setAmount] = useState<string>('100000')
  const [price, setPrice] = useState<string>('3')
  const [quantity, setQuantity] = useState<string>('0')
  const [currentPrice, setCurrentPrice] = useState<string>('3')
  const [totalAsset, setTotalAsset] = useState<string>('1000000')
  const [atr, setAtr] = useState<string>('0.05')
  const [vix, setVix] = useState<string>('18.5')
  const [newsText, setNewsText] = useState<string>('')

  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<RiskDecisionOut | null>(null)

  const submit = async (override?: Partial<{ amount: number; quantity: number }>) => {
    setLoading(true)
    setErr(null)
    try {
      const parseNum = (s: string) => {
        const t = s.trim()
        if (t === '') return 0
        const n = Number(t)
        return Number.isFinite(n) ? n : NaN
      }

      const vixN = parseNum(vix)
      const priceN = parseNum(price)
      const amountN = override?.amount ?? parseNum(amount)
      const quantityN = override?.quantity ?? parseNum(quantity)
      const currentPriceN = parseNum(currentPrice)
      const totalAssetN = parseNum(totalAsset)
      const atrN = parseNum(atr)

      if (!Number.isFinite(vixN)) throw new Error('请输入有效的 VIX')
      if (!(amountN > 0)) throw new Error('请输入有效的下单金额')
      if (!(priceN > 0)) throw new Error('请输入有效的委托价格')
      if (!(totalAssetN > 0)) throw new Error('请输入有效的总资产')

      await fetchJson('/api/kris/update-macro', {
        method: 'POST',
        body: JSON.stringify({ vix: vixN }),
      })

      const req: ApproveRequest = {
        order: {
          stock_code: stockCode.trim(),
          direction,
          amount: amountN,
          price: priceN,
          quantity: Number.isFinite(quantityN) ? quantityN : 0,
        },
        portfolio: {
          total_asset: totalAssetN,
          prices: { [stockCode.trim()]: Number.isFinite(currentPriceN) ? currentPriceN : 0 },
          atr: { [stockCode.trim()]: Number.isFinite(atrN) ? atrN : 0 },
        },
        context: { news_text: newsText },
      }

      const resp = await fetchJson<RiskDecisionOut>('/api/kris/approve', {
        method: 'POST',
        body: JSON.stringify(req),
      })
      setResult(resp)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const applySuggestionAndSubmit = async () => {
    if (!result) return
    if (result.suggested_amount <= 0 || result.suggested_quantity <= 0) return
    setAmount(String(result.suggested_amount))
    setQuantity(String(result.suggested_quantity))
    await submit({ amount: result.suggested_amount, quantity: result.suggested_quantity })
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="订单审批" right={<div className="text-xs text-zinc-500">卖出单也走同样表单；事件关键词仅对买入生效</div>} />
          <CardBody className="space-y-4">
            {err ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-zinc-600">股票代码</div>
                <input
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  placeholder="例如 510050.SH"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">方向</div>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value as Direction)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                >
                  <option value="buy">buy（买入）</option>
                  <option value="sell">sell（卖出）</option>
                </select>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">下单金额（元）</div>
                <input
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">委托价格</div>
                <input
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">数量（股，可选）</div>
                <input
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">现价（价格偏离）</div>
                <input
                  value={currentPrice}
                  onChange={(e) => setCurrentPrice(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">总资产（元）</div>
                <input
                  value={totalAsset}
                  onChange={(e) => setTotalAsset(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">ATR</div>
                <input
                  value={atr}
                  onChange={(e) => setAtr(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">VIX</div>
                <input
                  value={vix}
                  onChange={(e) => setVix(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-zinc-600">新闻文本（买入检查关键词，可为空）</div>
              <textarea
                value={newsText}
                onChange={(e) => setNewsText(e.target.value)}
                className="h-28 w-full resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => submit()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
              >
                提交审批
              </button>
              <button
                onClick={() => {
                  setResult(null)
                  setErr(null)
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50"
              >
                清空结果
              </button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="审批结果" right={result ? <DecisionBadge decision={result.decision} /> : <span className="text-xs text-zinc-500">未提交</span>} />
          <CardBody className="space-y-4">
            {!result ? (
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-10 text-center text-sm text-zinc-600">等待审批结果</div>
            ) : (
              <>
                <div
                  className={[
                    'rounded-xl border px-4 py-3',
                    result.decision === 'warn'
                      ? 'border-amber-200 bg-amber-50'
                      : result.decision === 'approve'
                        ? 'border-emerald-200 bg-emerald-50'
                        : result.decision === 'reject'
                          ? 'border-red-200 bg-red-50'
                          : 'border-zinc-200 bg-zinc-900 text-white',
                  ].join(' ')}
                >
                  <div className="text-sm font-semibold">
                    {result.decision === 'approve'
                      ? 'APPROVE：允许执行原订单'
                      : result.decision === 'warn'
                        ? 'WARN：建议缩单后执行'
                        : result.decision === 'reject'
                          ? 'REJECT：拒绝本笔订单'
                          : 'HALT：当日停止所有交易'}
                  </div>
                  <div className={['mt-1 text-sm', result.decision === 'halt' ? 'text-white/80' : ''].join(' ')}>{result.reason}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3">
                  <div className="text-xs text-zinc-500">建议执行</div>
                  <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="rounded-lg bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">建议下单金额（元）</div>
                      <div className="mt-1 text-lg font-semibold text-zinc-900">{result.suggested_amount.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">建议下单数量（股）</div>
                      <div className="mt-1 text-lg font-semibold text-zinc-900">{result.suggested_quantity.toLocaleString()}</div>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={applySuggestionAndSubmit}
                      disabled={loading || result.decision !== 'warn' || result.suggested_amount <= 0}
                      className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
                    >
                      一键按建议下单
                    </button>
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-200 bg-white">
                  <div className="border-b border-zinc-100 px-4 py-3">
                    <div className="text-sm font-semibold text-zinc-900">命中规则明细</div>
                  </div>
                  <div className="overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-white">
                        <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                          <th className="px-4 py-2">规则</th>
                          <th className="px-4 py-2">决策</th>
                          <th className="px-4 py-2">原因</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.checks.map((c, idx) => (
                          <tr key={idx} className="border-b border-zinc-50">
                            <td className="px-4 py-2 font-medium text-zinc-900">{c.rule_name}</td>
                            <td className="px-4 py-2 text-zinc-700">
                              <DecisionBadge decision={c.decision} />
                            </td>
                            <td className="px-4 py-2 text-zinc-600">{c.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

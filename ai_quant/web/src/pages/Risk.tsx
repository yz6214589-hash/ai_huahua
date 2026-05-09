import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { useEffect, useMemo, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import type { RiskApproveRequest, RiskApproveResponse, RiskAuditResponse } from '@/api/types'
import { RefreshCcw } from 'lucide-react'

type RiskStatus = {
  source: string
  status: string
  features: string[]
}

export default function Risk() {
  const [data, setData] = useState<RiskStatus | null>(null)
  const [audit, setAudit] = useState<RiskAuditResponse | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditErr, setAuditErr] = useState<string | null>(null)

  const [orderCode, setOrderCode] = useState('')
  const [direction, setDirection] = useState<'buy' | 'sell'>('buy')
  const [amount, setAmount] = useState('100000')
  const [price, setPrice] = useState('0')
  const [quantity, setQuantity] = useState('0')
  const [totalAsset, setTotalAsset] = useState('1000000')
  const [currentPrice, setCurrentPrice] = useState('0')
  const [atr14, setAtr14] = useState('0')
  const [newsText, setNewsText] = useState('')
  const [approveLoading, setApproveLoading] = useState(false)
  const [approveErr, setApproveErr] = useState<string | null>(null)
  const [approveResp, setApproveResp] = useState<RiskApproveResponse | null>(null)

  useEffect(() => {
    fetchJson<RiskStatus>('/api/risk/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  const loadAudit = async () => {
    setAuditLoading(true)
    setAuditErr(null)
    try {
      const r = await fetchJson<RiskAuditResponse>('/api/risk/audit?last_n=200')
      setAudit(r)
    } catch (e) {
      setAudit(null)
      setAuditErr(e instanceof Error ? e.message : String(e))
    } finally {
      setAuditLoading(false)
    }
  }

  useEffect(() => {
    loadAudit()
  }, [])

  const approvePayload = useMemo<RiskApproveRequest | null>(() => {
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

  const runApprove = async () => {
    if (!approvePayload) {
      setApproveErr('请填写股票代码')
      return
    }
    setApproveLoading(true)
    setApproveErr(null)
    setApproveResp(null)
    try {
      const r = await postJson<RiskApproveResponse>('/api/risk/approve', approvePayload)
      setApproveResp(r)
    } catch (e) {
      setApproveErr(e instanceof Error ? e.message : String(e))
    } finally {
      setApproveLoading(false)
    }
  }

  const decisionTone = (d: string) => {
    if (d === 'APPROVE') return 'green'
    if (d === 'WARN') return 'amber'
    if (d === 'REJECT') return 'red'
    return 'zinc'
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="风控中心" />
          <CardBody className="space-y-3 text-sm text-zinc-700">
            <div>模块来源：{data?.source || 'kris'}</div>
            <div>状态：{data?.status || 'loading'}</div>
            <div>能力：{(data?.features || []).join(' / ') || '—'}</div>

            {approveErr ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{approveErr}</div> : null}

            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">风控审批</div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block">
                  <div className="text-xs text-zinc-500">股票代码</div>
                  <input
                    value={orderCode}
                    onChange={(e) => setOrderCode(e.target.value)}
                    placeholder="例如 600519.SH"
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">方向</div>
                  <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value as 'buy' | 'sell')}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  >
                    <option value="buy">buy</option>
                    <option value="sell">sell</option>
                  </select>
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">下单金额（amount）</div>
                  <input
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">价格（price）</div>
                  <input
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">数量（quantity）</div>
                  <input
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">总资产（total_asset）</div>
                  <input
                    value={totalAsset}
                    onChange={(e) => setTotalAsset(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">当前价（可选，用于仓位估算）</div>
                  <input
                    value={currentPrice}
                    onChange={(e) => setCurrentPrice(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">ATR14（可选）</div>
                  <input
                    value={atr14}
                    onChange={(e) => setAtr14(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block col-span-2">
                  <div className="text-xs text-zinc-500">新闻/上下文（可选）</div>
                  <textarea
                    value={newsText}
                    onChange={(e) => setNewsText(e.target.value)}
                    rows={4}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
              </div>

              <button
                type="button"
                disabled={approveLoading}
                onClick={runApprove}
                className={cn('mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60')}
              >
                <RefreshCcw className="h-4 w-4" />
                {approveLoading ? '审批中...' : '提交审批'}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="审批结果 / 审计"
            right={
              <button
                onClick={loadAudit}
                disabled={auditLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                刷新审计
              </button>
            }
          />
          <CardBody className="space-y-4">
            {approveResp ? (
              <div className="rounded-lg border border-zinc-200 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-zinc-900">结论</div>
                  <Badge tone={decisionTone(approveResp.decision)}>{approveResp.decision}</Badge>
                </div>
                <div className="mt-2 text-sm text-zinc-700">{approveResp.reason}</div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-600">
                  <div>规则：{approveResp.rule_name}</div>
                  <div>最大仓位：{Math.round((approveResp.max_position_pct || 0) * 100)}%</div>
                  <div>建议金额：{approveResp.suggested_amount}</div>
                  <div>建议数量：{approveResp.suggested_quantity}</div>
                </div>
                {approveResp.checks?.length ? (
                  <div className="mt-3 overflow-auto rounded-lg border border-zinc-200">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-50 text-zinc-500">
                        <tr>
                          <th className="px-3 py-2">decision</th>
                          <th className="px-3 py-2">rule</th>
                          <th className="px-3 py-2">reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {approveResp.checks.map((c, idx) => (
                          <tr key={idx} className="border-t border-zinc-100 align-top">
                            <td className="px-3 py-2">
                              <Badge tone={decisionTone(c.decision)}>{c.decision}</Badge>
                            </td>
                            <td className="px-3 py-2 text-zinc-700">{c.rule_name}</td>
                            <td className="px-3 py-2 text-zinc-700">{c.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-zinc-500">提交审批后在此展示决策与规则明细</div>
            )}

            {auditErr ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{auditErr}</div> : null}
            <div className="overflow-auto rounded-lg border border-zinc-200 bg-white">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50 text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">时间</th>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">方向</th>
                    <th className="px-3 py-2">金额</th>
                    <th className="px-3 py-2">决策</th>
                    <th className="px-3 py-2">原因</th>
                  </tr>
                </thead>
                <tbody>
                  {(audit?.items || []).length === 0 ? (
                    <tr>
                      <td className="px-3 py-6 text-sm text-zinc-500" colSpan={6}>
                        {auditLoading ? '加载中…' : '暂无待审批订单'}
                      </td>
                    </tr>
                  ) : (
                    audit!.items.map((it, idx) => (
                      <tr key={it.timestamp + String(idx)} className="border-t border-zinc-100 align-top">
                        <td className="px-3 py-2 text-zinc-700">{String(it.timestamp || '').slice(0, 19).replace('T', ' ')}</td>
                        <td className="px-3 py-2 text-zinc-700">{it.stock_code}</td>
                        <td className="px-3 py-2 text-zinc-700">{it.direction}</td>
                        <td className="px-3 py-2 text-zinc-700">{it.amount}</td>
                        <td className="px-3 py-2">
                          <Badge tone={decisionTone(String(it.decision))}>{String(it.decision)}</Badge>
                        </td>
                        <td className="px-3 py-2 text-zinc-700">{it.reason}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

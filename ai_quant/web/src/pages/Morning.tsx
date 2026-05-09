import { useEffect, useState } from 'react'
import { postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import type { MorningTriggerRequest, MorningTriggerResponse } from '@/api/types'
import { RefreshCcw } from 'lucide-react'

export default function Morning() {
  const [result, setResult] = useState<MorningTriggerResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [stage, setStage] = useState('')
  const [industryLevel, setIndustryLevel] = useState<1 | 2>(2)
  const [topIndustries, setTopIndustries] = useState('5')
  const [topStocks, setTopStocks] = useState('5')
  const [lookbackDays, setLookbackDays] = useState('90')
  const [sampleStocks, setSampleStocks] = useState('20')

  useEffect(() => {
    if (!loading) return
    const start = Date.now()
    setElapsedSec(0)
    setStage('准备中')
    const id = window.setInterval(() => {
      const sec = Math.max(0, Math.floor((Date.now() - start) / 1000))
      setElapsedSec(sec)
      const s = sec < 3 ? '准备中' : sec < 10 ? '读取数据' : sec < 20 ? '计算指标' : sec < 30 ? '生成报告' : '排版输出'
      setStage(s)
    }, 1000)
    return () => window.clearInterval(id)
  }, [loading])

  const runMorning = async () => {
    setLoading(true)
    setErr(null)
    try {
      const body: MorningTriggerRequest = {
        industry_level: industryLevel,
        top_n_industries: Number(topIndustries || 0) || 5,
        top_n_stocks: Number(topStocks || 0) || 5,
        lookback_days: Number(lookbackDays || 0) || 90,
        sample_stocks: Number(sampleStocks || 0) || 20,
      }
      const r = await postJson<MorningTriggerResponse>('/api/console/morning/trigger', body)
      setResult(r)
    } catch (e) {
      setResult(null)
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader title="晨会简报" />
      <CardBody className="space-y-4">
        {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <label className="block">
            <div className="text-xs text-zinc-500">行业层级</div>
            <select
              value={industryLevel}
              onChange={(e) => setIndustryLevel((Number(e.target.value) as 1 | 2) || 2)}
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            >
              <option value={2}>2</option>
              <option value={1}>1</option>
            </select>
          </label>
          <label className="block">
            <div className="text-xs text-zinc-500">Top 行业</div>
            <input
              value={topIndustries}
              onChange={(e) => setTopIndustries(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="block">
            <div className="text-xs text-zinc-500">Top 个股</div>
            <input
              value={topStocks}
              onChange={(e) => setTopStocks(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="block">
            <div className="text-xs text-zinc-500">回看天数</div>
            <input
              value={lookbackDays}
              onChange={(e) => setLookbackDays(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="block">
            <div className="text-xs text-zinc-500">样本股数</div>
            <input
              value={sampleStocks}
              onChange={(e) => setSampleStocks(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
        </div>
        <button
          onClick={runMorning}
          disabled={loading}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800 disabled:opacity-60"
        >
          <span className="inline-flex items-center gap-2">
            <RefreshCcw className="h-4 w-4" />
            {loading ? '运行中...' : '生成晨会简报'}
          </span>
        </button>
        {loading ? (
          <div className="text-xs text-zinc-500">
            已运行 {elapsedSec}s · {stage}
          </div>
        ) : null}
        {result ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">HTML（源码）</div>
              <pre className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">{result.result.report_html || ''}</pre>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">Markdown</div>
              <pre className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">{result.result.report_md}</pre>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">结构化结果</div>
              <pre className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
                {JSON.stringify({ industry_rank: result.result.industry_rank, picked_stocks: result.result.picked_stocks, messages: result.result.messages }, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <div className="text-sm text-zinc-500">点击按钮生成晨会简报</div>
        )}
      </CardBody>
    </Card>
  )
}

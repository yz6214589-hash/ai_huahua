import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { JobRunResult, SummaryResponse } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { ArrowRight, RefreshCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

export default function Dashboard() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [runs, setRuns] = useState<JobRunResult[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const s = await fetchJson<SummaryResponse>('/api/summary')
      const r = await fetchJson<{ runs: JobRunResult[] }>('/api/jobs/runs?limit=10')
      setSummary(s)
      setRuns(r.runs || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const kpis = useMemo(() => {
    if (!summary) return []
    return [
      { label: '行情表记录数', value: summary.trade_stock_daily.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_daily.latest)}` },
      { label: '财务表记录数', value: summary.trade_stock_financial.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_financial.latest)}` },
      { label: '新闻条数', value: summary.trade_stock_news.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_news.latest)}` },
      { label: '日历事件数', value: summary.trade_calendar_event.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_calendar_event.latest)}` },
    ]
  }, [summary])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-zinc-600">确保看到的市场是真实的：采集 → 清洗 → 交付</div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className="h-4 w-4" />
          刷新
        </button>
      </div>

      {err ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label}>
            <CardBody>
              <div className="text-xs text-zinc-500">{k.label}</div>
              <div className="mt-2 text-2xl font-semibold text-zinc-900">{k.value}</div>
              <div className="mt-1 text-xs text-zinc-500">{k.sub}</div>
            </CardBody>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="最近任务运行"
            right={
              <Link to="/jobs" className="inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-900">
                查看全部 <ArrowRight className="h-3 w-3" />
              </Link>
            }
          />
          <CardBody className="p-0">
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                    <th className="px-4 py-2">domain</th>
                    <th className="px-4 py-2">status</th>
                    <th className="px-4 py-2">source</th>
                    <th className="px-4 py-2">rows</th>
                    <th className="px-4 py-2">started</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-sm text-zinc-500" colSpan={5}>
                        暂无运行记录
                      </td>
                    </tr>
                  ) : (
                    runs.map((r) => (
                      <tr key={r.runId} className="border-b border-zinc-50">
                        <td className="px-4 py-2 font-medium text-zinc-900">{r.domain}</td>
                        <td className="px-4 py-2">
                          <JobStatusBadge status={r.status} />
                        </td>
                        <td className="px-4 py-2">
                          <DataSourceBadge source={r.dataSourceFinal} />
                        </td>
                        <td className="px-4 py-2 text-zinc-700">{r.rowsWritten.toLocaleString()}</td>
                        <td className="px-4 py-2 text-xs text-zinc-500">{formatDate(r.startedAt)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="数据源优先级规则" />
          <CardBody>
            <div className="space-y-2 text-sm text-zinc-700">
              <div>日线：QMT → Tushare → AkShare</div>
              <div>财务：QMT → Tushare → AkShare</div>
              <div>换手率：仅按 QMT 口径计算</div>
              <div>宏观/财经日历/研报：AkShare</div>
              <div>新闻：AkShare + LLM（可选，需配置 Key）</div>
              <div>关键催化剂：Qwen Max 联网搜索（需 DASHSCOPE_API_KEY）</div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}


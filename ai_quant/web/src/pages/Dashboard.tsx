import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { ConsoleOverview } from '@/api/types'
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
  const [overview, setOverview] = useState<ConsoleOverview | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const data = await fetchJson<ConsoleOverview>('/api/console/overview')
      setOverview(data)
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
    const summary = overview?.data_latest
    if (!summary) return []
    return [
      { label: '行情表记录数', value: summary.trade_stock_daily.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_daily.latest)}` },
      { label: '财务表记录数', value: summary.trade_stock_financial.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_financial.latest)}` },
      { label: '新闻条数', value: summary.trade_stock_news.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_news.latest)}` },
      { label: '日历事件数', value: summary.trade_calendar_event.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_calendar_event.latest)}` },
    ]
  }, [overview])

  const runs = overview?.recent_jobs || []
  const executionStatus = overview?.execution_status
  const riskStatus = overview?.risk_status
  const morning = overview?.morning
  const emptyData = useMemo(() => {
    const s = overview?.data_latest
    if (!s) return false
    const cnts = [s.trade_stock_daily.count, s.trade_stock_financial.count, s.trade_stock_news.count, s.trade_calendar_event.count]
    return runs.length === 0 && cnts.every((x) => Number(x || 0) <= 0)
  }, [overview, runs.length])

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

      {emptyData ? (
        <Card>
          <CardHeader title="新手引导" />
          <CardBody className="space-y-2 text-sm text-zinc-700">
            <div>1. 前往任务页运行采集任务，生成基础行情/财务/新闻数据</div>
            <div>
              2. 前往数据页确认数据入库与查询：<Link to="/data" className="text-zinc-900 underline">数据与交付</Link>
            </div>
            <div>
              3. 前往研报页生成智能研报：<Link to="/reports" className="text-zinc-900 underline">智能研报</Link>
            </div>
          </CardBody>
        </Card>
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
          <CardHeader title="跨模块状态总览" />
          <CardBody>
            <div className="space-y-2 text-sm text-zinc-700">
              <div>执行状态：{executionStatus?.status || 'unknown'}</div>
              <div>执行能力：{(executionStatus?.features || []).join(' / ') || '—'}</div>
              <div>风控状态：{String(riskStatus?.status || 'unknown')}</div>
              <div>风控能力：{Array.isArray(riskStatus?.features) ? riskStatus.features.join(' / ') : '—'}</div>
              <div>晨会运行次数：{morning?.run_count ?? 0}</div>
              <div>最近晨会时间：{formatDate(morning?.last_run?.created_at)}</div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}


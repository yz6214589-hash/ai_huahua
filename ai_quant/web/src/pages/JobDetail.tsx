import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import type { JobDomain, JobRunResult } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { ArrowLeft } from 'lucide-react'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

export default function JobDetail() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const domain = params.get('domain') || ''
  const domainName = params.get('name') || domain

  const [history, setHistory] = useState<JobRunResult[]>([])
  const [selected, setSelected] = useState<JobRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const loadHistory = async () => {
    if (!domain) return
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ runs: JobRunResult[] }>(
        `/api/v1/jobs/runs?domain=${encodeURIComponent(domain)}&limit=100`
      )
      setHistory(r.runs || [])
      if (r.runs && r.runs.length > 0) {
        setSelected(r.runs[0])
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadHistory() }, [domain])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/info-access/data-collection')}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50"
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </button>
        <div className="text-sm font-semibold text-zinc-900">{domainName}</div>
      </div>

      <Card>
        <CardHeader title="运行历史" />
        <CardBody className="p-0">
          {loading ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">加载中…</div>
          ) : err ? (
            <div className="px-4 py-8 text-center text-sm text-red-600">{err}</div>
          ) : history.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无运行记录</div>
          ) : (
            <div className="max-h-64 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                    <th className="px-4 py-2">时间</th>
                    <th className="px-4 py-2">状态</th>
                    <th className="px-4 py-2">rows</th>
                    <th className="px-4 py-2">source</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r) => (
                    <tr
                      key={r.runId}
                      onClick={() => setSelected(r)}
                      className={`cursor-pointer border-b border-zinc-50 hover:bg-zinc-50 ${selected?.runId === r.runId ? 'bg-zinc-50' : ''}`}
                    >
                      <td className="px-4 py-2 text-xs text-zinc-700">{formatDate(r.startedAt)}</td>
                      <td className="px-4 py-2"><JobStatusBadge status={r.status} /></td>
                      <td className="px-4 py-2 text-zinc-700">{r.rowsWritten.toLocaleString()}</td>
                      <td className="px-4 py-2"><DataSourceBadge source={r.dataSourceFinal} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {selected ? (
        <Card>
          <CardHeader title="运行详情" />
          <CardBody>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">runId</div>
                  <div className="mt-1 break-all text-xs text-zinc-900">{selected.runId}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">status</div>
                  <div className="mt-1"><JobStatusBadge status={selected.status} /></div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">dataSourceFinal</div>
                  <div className="mt-1"><DataSourceBadge source={selected.dataSourceFinal} /></div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">fallbackChain</div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {selected.fallbackChain.length === 0 ? <span className="text-xs text-zinc-500">—</span> : null}
                    {selected.fallbackChain.map((s, i) => (
                      <span key={`${s}-${i}`}><DataSourceBadge source={s} /></span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">itemsProcessed</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.itemsProcessed.toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">rowsWritten</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.rowsWritten.toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">耗时</div>
                  <div className="mt-1 text-xs text-zinc-700">{formatDate(selected.startedAt)} → {formatDate(selected.finishedAt)}</div>
                </div>
              </div>

              {selected.userMessage || selected.message ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {selected.userMessage || selected.message}
                </div>
              ) : null}

              <div>
                <div className="mb-2 text-sm font-semibold text-zinc-900">failedItems</div>
                <div className="max-h-40 overflow-auto rounded-lg border border-zinc-200 bg-white p-3 text-xs text-zinc-700">
                  {selected.failedItems.length === 0 ? '—' : selected.failedItems.join('\n')}
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      ) : (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">
          选择一条运行记录查看详情
        </div>
      )}
    </div>
  )
}

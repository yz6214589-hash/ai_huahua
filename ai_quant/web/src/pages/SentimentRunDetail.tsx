import { fetchJson } from '@/api/client'
import type { SentimentEvent, SentimentRun } from '@/api/types'
import { Badge } from '@/components/Badge'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ExternalLink, RefreshCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function EventTypeBadge({ t }: { t: string }) {
  const tone = t === '利好' ? 'green' : t === '利空' ? 'red' : t === '政策' ? 'blue' : 'zinc'
  return <Badge tone={tone}>{t || '—'}</Badge>
}

export default function SentimentRunDetail() {
  const { runId } = useParams()
  const [run, setRun] = useState<SentimentRun | null>(null)
  const [events, setEvents] = useState<SentimentEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    if (!runId) return
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ run: SentimentRun; events: SentimentEvent[] }>(`/api/sentiment/runs/${encodeURIComponent(runId)}`)
      setRun(r.run)
      setEvents(r.events || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [runId])

  return (
    <div className="space-y-4">
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

      <Card>
        <CardHeader
          title="舆情 Run 详情"
          right={
            <button
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
            >
              <RefreshCcw className="h-4 w-4" />
              刷新
            </button>
          }
        />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
              <div className="text-xs text-zinc-500">RunID</div>
              <div className="mt-1 text-sm font-semibold text-zinc-900">{run?.run_id || runId}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">创建时间</div>
              <div className="mt-1 text-sm text-zinc-900">{fmtDateTime(run?.created_at || null)}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">状态</div>
              <div className="mt-1 text-sm text-zinc-900">{run?.status || '—'}</div>
            </div>
          </div>

          {run?.stock_codes?.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {run.stock_codes.map((c, i) => (
                <Link
                  key={c}
                  to={`/sentiment/stocks/${encodeURIComponent(c)}?run_id=${encodeURIComponent(run.run_id)}`}
                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                >
                  <span className="font-semibold">{c}</span>
                  <span className="text-zinc-500">{run.stock_names?.[i] || ''}</span>
                  <ExternalLink className="h-3.5 w-3.5 text-zinc-400" />
                </Link>
              ))}
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="事件列表" />
        <CardBody>
          <div className="overflow-auto rounded-lg border border-zinc-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2">股票</th>
                  <th className="px-3 py-2">事件类型</th>
                  <th className="px-3 py-2">事件类别</th>
                  <th className="px-3 py-2">策略建议</th>
                  <th className="px-3 py-2">影响推断</th>
                  <th className="px-3 py-2">来源</th>
                  <th className="px-3 py-2">原文链接</th>
                  <th className="px-3 py-2">触发时间</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td className="px-3 py-6 text-sm text-zinc-500" colSpan={8}>
                      暂无事件
                    </td>
                  </tr>
                ) : (
                  events.map((e) => (
                    <tr key={e.id} className="border-t border-zinc-100">
                      <td className="px-3 py-2 text-sm text-zinc-900">
                        {e.stock_code} {e.stock_name || ''}
                      </td>
                      <td className="px-3 py-2">
                        <EventTypeBadge t={e.event_type} />
                      </td>
                      <td className="px-3 py-2 text-sm text-zinc-900">{e.event_category}</td>
                      <td className="px-3 py-2 text-sm text-zinc-900">{e.signal}</td>
                      <td className="px-3 py-2 text-sm text-zinc-700">{e.impact || e.signal_reason || '—'}</td>
                      <td className="px-3 py-2 text-sm text-zinc-900">{e.source_type === 'notice' ? '公告' : '新闻'}</td>
                      <td className="px-3 py-2">
                        {e.source_url ? (
                          <a className="text-blue-600 hover:underline" href={e.source_url} target="_blank" rel="noreferrer">
                            打开
                          </a>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(e.published_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}


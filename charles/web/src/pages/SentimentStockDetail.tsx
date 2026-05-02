import { fetchJson } from '@/api/client'
import type { SentimentEvent } from '@/api/types'
import { Badge } from '@/components/Badge'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ExternalLink, RefreshCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function EventTypeBadge({ t }: { t: string }) {
  const tone = t === '利好' ? 'green' : t === '利空' ? 'red' : t === '政策' ? 'blue' : 'zinc'
  return <Badge tone={tone}>{t || '—'}</Badge>
}

export default function SentimentStockDetail() {
  const { code } = useParams()
  const [sp] = useSearchParams()
  const runId = sp.get('run_id') || ''

  const [news, setNews] = useState<any[]>([])
  const [events, setEvents] = useState<SentimentEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const title = useMemo(() => (code ? decodeURIComponent(code) : ''), [code])

  const load = async () => {
    if (!code || !runId) return
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ news: any[]; events: SentimentEvent[] }>(
        `/api/sentiment/stocks/${encodeURIComponent(code)}?run_id=${encodeURIComponent(runId)}`
      )
      setNews(r.news || [])
      setEvents(r.events || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [code, runId])

  return (
    <div className="space-y-4">
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

      <Card>
        <CardHeader
          title={`股票舆情详情 ${title}`}
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
          <div className="text-xs text-zinc-500">run_id：{runId}</div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="事件" />
        <CardBody>
          <div className="overflow-auto rounded-lg border border-zinc-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
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
                    <td className="px-3 py-6 text-sm text-zinc-500" colSpan={7}>
                      暂无事件
                    </td>
                  </tr>
                ) : (
                  events.map((e) => (
                    <tr key={e.id} className="border-t border-zinc-100">
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
                            <span className="inline-flex items-center gap-2">
                              <ExternalLink className="h-4 w-4" />
                              打开
                            </span>
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

      <Card>
        <CardHeader title="新闻/公告" />
        <CardBody>
          <div className="space-y-3">
            {news.length === 0 ? (
              <div className="text-sm text-zinc-500">暂无新闻</div>
            ) : (
              news.map((n) => (
                <div key={n.id} className="rounded-lg border border-zinc-200 bg-white p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-zinc-900">{n.title}</div>
                      <div className="mt-1 text-xs text-zinc-500">
                        {n.source_type === 'notice' ? '公告' : '新闻'} · {fmtDateTime(n.published_at)}
                      </div>
                    </div>
                    {n.url ? (
                      <a className="text-blue-600 hover:underline" href={n.url} target="_blank" rel="noreferrer">
                        <span className="inline-flex items-center gap-2 text-sm">
                          <ExternalLink className="h-4 w-4" />
                          打开
                        </span>
                      </a>
                    ) : null}
                  </div>
                  {n.summary ? <div className="mt-2 text-sm text-zinc-700">{n.summary}</div> : null}
                  {n.market_impact ? <div className="mt-1 text-sm text-zinc-700">{n.market_impact}</div> : null}
                </div>
              ))
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}


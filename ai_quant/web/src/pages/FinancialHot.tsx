import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ExternalLink, RefreshCcw } from 'lucide-react'

interface FinancialHotData {
  date: string
  events: Array<{
    event_date: string
    country: string
    importance: string
    source: string
    event_name: string
  }>
  news: Array<{
    stock_code: string
    stock_name: string
    title: string
    source: string
    published_at: string
    url: string
  }>
}

function ImportanceBadge({ importance }: { importance: string }) {
  const tone = importance === '高' ? 'red' : importance === '中' ? 'amber' : 'zinc'
  return <Badge tone={tone}>{importance}</Badge>
}

function fmtDate(v: string) {
  if (!v || v === '—') return '—'
  const s = String(v)
  return s.length > 16 ? s.slice(0, 16).replace('T', ' ') : s
}

export default function FinancialHot() {
  const [data, setData] = useState<FinancialHotData | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<FinancialHotData>('/api/v1/financial-hot')
      setData(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">
          {data?.date ? `财经热点 · ${data.date}` : '财经热点'}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {err ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>
      ) : null}

      {(!data && !loading) ? (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-12 text-center text-sm text-zinc-500">暂无热点数据</div>
      ) : (
        <>
          <Card>
            <CardHeader title={`今日财经日历（${data?.events?.length || 0} 条）`} />
            <CardBody className="p-0">
              {!data?.events || data.events.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-zinc-500">今日暂无财经日历事件</div>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-zinc-50 text-xs text-zinc-500">
                      <tr>
                        <th className="px-3 py-2">时间</th>
                        <th className="px-3 py-2">国家/地区</th>
                        <th className="px-3 py-2">重要性</th>
                        <th className="px-3 py-2">事件名称</th>
                        <th className="px-3 py-2">来源</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data!.events.map((e, i) => (
                        <tr key={i} className="border-t border-zinc-100">
                          <td className="px-3 py-2 text-xs text-zinc-700">{e.event_date}</td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{e.country}</td>
                          <td className="px-3 py-2"><ImportanceBadge importance={e.importance} /></td>
                          <td className="px-3 py-2 text-xs text-zinc-900">{e.event_name}</td>
                          <td className="px-3 py-2 text-xs text-zinc-500">{e.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title={`近期重要新闻（近3天 · ${data?.news?.length || 0} 条）`} />
            <CardBody className="p-0">
              {!data?.news || data.news.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无新闻数据</div>
              ) : (
                <div className="divide-y divide-zinc-100">
                  {data!.news.map((n, i) => (
                    <div key={i} className="flex items-start justify-between gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-zinc-900">{n.title}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                          {n.stock_code && <span className="font-medium text-zinc-700">{n.stock_code}</span>}
                          {n.stock_name && <span>{n.stock_name}</span>}
                          {n.source && <span>{n.source}</span>}
                          <span>{fmtDate(n.published_at)}</span>
                        </div>
                      </div>
                      {n.url && (
                        <a
                          href={n.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 text-zinc-400 hover:text-zinc-700"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}

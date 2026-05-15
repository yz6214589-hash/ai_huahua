import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import type { JobDomain, JobRunResult } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { History, GitBranch, RefreshCcw } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

export default function DataDelivery() {
  const navigate = useNavigate()
  const [history, setHistory] = useState<JobRunResult[]>([])
  const [selected, setSelected] = useState<JobRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const loadHistory = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ runs: JobRunResult[] }>('/api/v1/jobs/runs?limit=100')
      setHistory(r.runs || [])
      if (r.runs && r.runs.length > 0 && !selected) {
        setSelected(r.runs[0])
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
    const t = window.setInterval(() => { loadHistory() }, 5000)
    return () => window.clearInterval(t)
  }, [])

  return (
    <div className="space-y-4">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">数据与交付</h2>
        <p className="mt-1 text-sm text-zinc-500">查看数据采集历史记录和Git状态</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="历史记录"
            right={
              <button
                onClick={() => loadHistory()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
                刷新
              </button>
            }
          />
          <CardBody className="p-0">
            {loading && history.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">加载中…</div>
            ) : err ? (
              <div className="px-4 py-8 text-center text-sm text-red-600">{err}</div>
            ) : history.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无运行记录</div>
            ) : (
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                      <th className="px-4 py-2">时间</th>
                      <th className="px-4 py-2">任务</th>
                      <th className="px-4 py-2">状态</th>
                      <th className="px-4 py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((r) => (
                      <tr
                        key={r.runId}
                        onClick={() => setSelected(r)}
                        className={cn(
                          'cursor-pointer border-b border-zinc-50 hover:bg-zinc-50',
                          selected?.runId === r.runId ? 'bg-zinc-50' : ''
                        )}
                      >
                        <td className="px-4 py-2 text-xs text-zinc-700">{formatDate(r.startedAt)}</td>
                        <td className="px-4 py-2 text-xs text-zinc-700">{r.domain}</td>
                        <td className="px-4 py-2"><JobStatusBadge status={r.status} /></td>
                        <td className="px-4 py-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/info-access/data-collection/detail?domain=${encodeURIComponent(r.domain)}&name=${encodeURIComponent(r.domain)}`)
                            }}
                            className="text-xs text-zinc-600 hover:text-zinc-900"
                          >
                            详情
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Git 状态"
          />
          <CardBody>
            <div className="space-y-3">
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="text-xs text-zinc-500">当前版本</div>
                <div className="mt-1 text-sm font-medium text-zinc-900">main</div>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="text-xs text-zinc-500">数据同步状态</div>
                <div className="mt-1 text-sm font-medium text-zinc-900">已同步</div>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="text-xs text-zinc-500">最近更新</div>
                <div className="mt-1 text-sm text-zinc-700">
                  {history.length > 0 ? formatDate(history[0].finishedAt) : '—'}
                </div>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="text-xs text-zinc-500">交付统计</div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <div className="text-center">
                    <div className="text-lg font-semibold text-zinc-900">{history.filter(h => h.status === 'success').length}</div>
                    <div className="text-xs text-zinc-500">成功</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-zinc-900">{history.filter(h => h.status === 'failed').length}</div>
                    <div className="text-xs text-zinc-500">失败</div>
                  </div>
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {selected && (
        <Card>
          <CardHeader title="选中记录详情" />
          <CardBody>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">runId</div>
                  <div className="mt-1 break-all text-xs text-zinc-900">{selected.runId}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">状态</div>
                  <div className="mt-1"><JobStatusBadge status={selected.status} /></div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">数据源</div>
                  <div className="mt-1"><DataSourceBadge source={selected.dataSourceFinal} /></div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                  <div className="text-xs text-zinc-500">写入行数</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.rowsWritten.toLocaleString()}</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">处理条目</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.itemsProcessed.toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">失败条目</div>
                  <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.failedItems.length}</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-xs text-zinc-500">耗时</div>
                  <div className="mt-1 text-xs text-zinc-700">{formatDate(selected.startedAt)}</div>
                </div>
              </div>
              {selected.userMessage || selected.message ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {selected.userMessage || selected.message}
                </div>
              ) : null}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

import { fetchJson, postJson } from '@/api/client'
import type { StockSearchItem, WatchlistItem } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Pin, Plus, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

function SortableRow({
  item,
  onPin,
  onDelete,
}: {
  item: WatchlistItem
  onPin: (code: string, pinned: boolean) => void
  onDelete: (code: string) => void
}) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.stock_code })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-white px-3 py-2',
        isDragging ? 'opacity-70' : ''
      )}
      onClick={() => navigate(`/stock/${encodeURIComponent(item.stock_code)}`)}
    >
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-50 hover:text-zinc-700"
          onClick={(e) => e.stopPropagation()}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-zinc-900">{item.stock_code}</div>
          <div className="truncate text-xs text-zinc-500">{item.stock_name || '—'}</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {item.pinned ? <Badge tone="amber">置顶</Badge> : null}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onPin(item.stock_code, !item.pinned)
          }}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
        >
          <Pin className="h-3.5 w-3.5" />
          {item.pinned ? '取消置顶' : '置顶'}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onDelete(item.stock_code)
          }}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
          删除
        </button>
      </div>
    </div>
  )
}

export default function Watchlist() {
  const [params] = useSearchParams()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<StockSearchItem[]>([])
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [searchErr, setSearchErr] = useState<string | null>(null)

  const pinned = useMemo(() => items.filter((x) => x.pinned), [items])
  const normal = useMemo(() => items.filter((x) => !x.pinned), [items])

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ items: WatchlistItem[]; max: number }>('/api/watchlist')
      setItems(r.items || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    const v = (params.get('q') || '').trim()
    if (v) setQ(v)
  }, [params])

  useEffect(() => {
    let alive = true
    const t = window.setTimeout(async () => {
      const v = q.trim()
      if (!v) {
        setResults([])
        setSearchErr(null)
        return
      }
      const ctrl = new AbortController()
      const tt = window.setTimeout(() => ctrl.abort(), 5000)
      setSearching(true)
      try {
        setSearchErr(null)
        const r = await fetchJson<{ items: StockSearchItem[] }>(`/api/stocks?q=${encodeURIComponent(v)}&limit=20`, { signal: ctrl.signal })
        if (!alive) return
        setResults(r.items || [])
      } catch {
        if (!alive) return
        setResults([])
        setSearchErr('搜索超时或失败')
      } finally {
        window.clearTimeout(tt)
        if (alive) setSearching(false)
      }
    }, 250)
    return () => {
      alive = false
      window.clearTimeout(t)
    }
  }, [q])

  const add = async (code: string) => {
    setErr(null)
    try {
      await postJson<{ ok: boolean }>('/api/watchlist', { stock_code: code })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const del = async (code: string) => {
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/watchlist/${encodeURIComponent(code)}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const pin = async (code: string, pinned: boolean) => {
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/watchlist/${encodeURIComponent(code)}/pin`, {
        method: 'PUT',
        body: JSON.stringify({ pinned }),
      })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const saveOrder = async (nextPinned: WatchlistItem[], nextNormal: WatchlistItem[]) => {
    const ordered = [...nextPinned, ...nextNormal].map((x) => x.stock_code)
    await fetchJson<{ ok: boolean }>('/api/watchlist/reorder', { method: 'PUT', body: JSON.stringify({ codes: ordered }) })
  }

  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeId = String(active.id)
    const overId = String(over.id)

    const inPinned = pinned.some((x) => x.stock_code === activeId)
    const inPinnedOver = pinned.some((x) => x.stock_code === overId)
    const inNormal = normal.some((x) => x.stock_code === activeId)
    const inNormalOver = normal.some((x) => x.stock_code === overId)

    if (inPinned && inPinnedOver) {
      const oldIndex = pinned.findIndex((x) => x.stock_code === activeId)
      const newIndex = pinned.findIndex((x) => x.stock_code === overId)
      const nextPinned = arrayMove(pinned, oldIndex, newIndex)
      const next = [...nextPinned, ...normal]
      setItems(next)
      try {
        await saveOrder(nextPinned, normal)
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e))
        await load()
      }
      return
    }

    if (inNormal && inNormalOver) {
      const oldIndex = normal.findIndex((x) => x.stock_code === activeId)
      const newIndex = normal.findIndex((x) => x.stock_code === overId)
      const nextNormal = arrayMove(normal, oldIndex, newIndex)
      const next = [...pinned, ...nextNormal]
      setItems(next)
      try {
        await saveOrder(pinned, nextNormal)
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e))
        await load()
      }
      return
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="手动添加" />
          <CardBody>
            {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const v = q.trim()
                    if (v && results.length === 0 && !searching) setSearchErr('股票不存在')
                  }
                }}
                placeholder="按代码/名称搜索，例如 600 或 贵州"
                className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm outline-none transition focus:border-zinc-400"
              />
            </div>
            <div className="mt-3 space-y-2">
              {searching ? <div className="text-xs text-zinc-500">搜索中…</div> : null}
              {searchErr ? <div className="text-xs text-red-600">{searchErr}</div> : null}
              {q.trim() && results.length === 0 && !searching ? <div className="text-xs text-zinc-500">无匹配结果</div> : null}
              {results.map((r) => (
                <div key={r.code} className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-white px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-zinc-900">{r.code}</div>
                    <div className="truncate text-xs text-zinc-500">{r.name || '—'}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => add(r.code)}
                    className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-zinc-800"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    添加
                  </button>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader title="自选股列表" />
          <CardBody>
            {loading ? <div className="text-sm text-zinc-500">加载中…</div> : null}
            {!loading && items.length === 0 ? <div className="text-sm text-zinc-500">暂无自选股</div> : null}
            {items.length > 0 ? (
              <div className="space-y-4">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  {pinned.length > 0 ? (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-zinc-600">置顶</div>
                      <SortableContext items={pinned.map((x) => x.stock_code)} strategy={verticalListSortingStrategy}>
                        <div className="space-y-2">
                          {pinned.map((it) => (
                            <SortableRow key={it.stock_code} item={it} onPin={pin} onDelete={del} />
                          ))}
                        </div>
                      </SortableContext>
                    </div>
                  ) : null}
                  {normal.length > 0 ? (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-zinc-600">普通</div>
                      <SortableContext items={normal.map((x) => x.stock_code)} strategy={verticalListSortingStrategy}>
                        <div className="space-y-2">
                          {normal.map((it) => (
                            <SortableRow key={it.stock_code} item={it} onPin={pin} onDelete={del} />
                          ))}
                        </div>
                      </SortableContext>
                    </div>
                  ) : null}
                </DndContext>
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}


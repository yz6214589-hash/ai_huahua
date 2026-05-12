import { fetchJson, postJson } from '@/api/client'
import type { StockSearchItem, WatchlistGroup, WatchlistItem, WatchlistSnapshot } from '@/api/types'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { StockPicker } from '@/components/StockPicker'
import { cn } from '@/lib/utils'
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Minus, Pencil, Pin, Plus, RefreshCcw, Settings, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

function ChangeCell({ change, pct }: { change: number | null | undefined; pct: number | null | undefined }) {
  if (change == null && pct == null) {
    return <span className="text-sm text-zinc-400">—</span>
  }
  const up = (pct ?? change ?? 0) >= 0
  const cls = up ? 'text-red-600' : 'text-green-600'
  return (
    <div className="text-right">
      <div className={cn('text-sm font-semibold', cls)}>{up ? '+' : ''}{fmt(change)}</div>
      <div className={cn('text-xs', cls)}>{up ? '+' : ''}{fmt(pct)}%</div>
    </div>
  )
}

function SortableRow({
  item,
  snapshot,
  groupNames,
  onPin,
  onDelete,
}: {
  item: WatchlistItem
  snapshot?: WatchlistSnapshot
  groupNames?: Map<number, string>
  onPin: (code: string, pinned: boolean) => void
  onDelete: (code: string) => void
}) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.stock_code })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }
  const price = snapshot?.price

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2',
        isDragging ? 'opacity-70' : 'hover:border-zinc-400 cursor-pointer'
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
        {item.group_ids && item.group_ids.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.group_ids.map((gid) => (
              <span key={gid} className="rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">
                {groupNames?.get(gid) || `分组${gid}`}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="flex min-w-0 items-center gap-3">
        <ChangeCell change={snapshot?.change} pct={snapshot?.pctChange} />
        <div className="w-20 text-right">
          <div className="text-sm font-semibold text-zinc-900">{price != null ? fmt(price) : '—'}</div>
          <div className="text-xs text-zinc-500">最新价</div>
        </div>
        {item.pinned ? (
          <span className="rounded-md border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">置顶</span>
        ) : null}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onPin(item.stock_code, !item.pinned) }}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
        >
          <Pin className="h-3.5 w-3.5" />
          {item.pinned ? '取消置顶' : '置顶'}
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(item.stock_code) }}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
          删除
        </button>
      </div>
    </div>
  )
}

function GroupManagerModal({
  groups,
  onClose,
  onCreate,
  onRename,
  onDelete,
}: {
  groups: WatchlistGroup[]
  onClose: () => void
  onCreate: (name: string) => void
  onRename: (id: number, name: string) => void
  onDelete: (id: number) => void
}) {
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    onCreate(name)
    setNewName('')
  }

  const startEdit = (g: WatchlistGroup) => {
    setEditingId(g.id)
    setEditingName(g.name)
  }

  const handleRename = (id: number) => {
    const name = editingName.trim()
    if (!name) return
    onRename(id, name)
    setEditingId(null)
    setEditingName('')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
          <div className="text-sm font-semibold text-zinc-900">管理分组</div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              placeholder="新分组名称"
              className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
            />
            <button
              onClick={handleCreate}
              className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            >
              <Plus className="h-4 w-4" />
              新建
            </button>
          </div>
          <div className="space-y-2">
            {groups.length === 0 ? (
              <div className="py-4 text-center text-sm text-zinc-400">暂无自定义分组</div>
            ) : (
              groups.map((g) => (
                <div key={g.id} className="flex items-center gap-2 rounded-lg border border-zinc-100 px-3 py-2">
                  {editingId === g.id ? (
                    <>
                      <input
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleRename(g.id); if (e.key === 'Escape') setEditingId(null) }}
                        autoFocus
                        className="flex-1 rounded border border-zinc-200 px-2 py-1 text-sm outline-none focus:border-zinc-400"
                      />
                      <button onClick={() => handleRename(g.id)} className="text-xs text-zinc-700 hover:text-zinc-900">保存</button>
                      <button onClick={() => setEditingId(null)} className="text-xs text-zinc-400 hover:text-zinc-700">取消</button>
                    </>
                  ) : (
                    <>
                      <span className="flex-1 text-sm text-zinc-900">{g.name}</span>
                      <button onClick={() => startEdit(g)} className="text-zinc-400 hover:text-zinc-700">
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => onDelete(g.id)} className="text-zinc-400 hover:text-red-600">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Watchlist() {
  const [groups, setGroups] = useState<WatchlistGroup[]>([])
  const [activeGroupId, setActiveGroupId] = useState<number | null>(null)
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [snapshots, setSnapshots] = useState<Record<string, WatchlistSnapshot>>({})
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingSnapshot, setLoadingSnapshot] = useState(false)
  const [showGroupManager, setShowGroupManager] = useState(false)
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([])
  const groupNameMap = useMemo(() => {
    const m = new Map<number, string>()
    for (const g of groups) m.set(g.id, g.name)
    return m
  }, [groups])

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const loadGroups = async () => {
    try {
      const r = await fetchJson<{ items: WatchlistGroup[] }>('/api/watchlist/groups')
      setGroups(r.items || [])
    } catch { /* ignore */ }
  }

  const loadItems = async () => {
    setLoading(true)
    setErr(null)
    try {
      const qs = activeGroupId != null ? `?group_id=${activeGroupId}` : ''
      const r = await fetchJson<{ items: WatchlistItem[] }>(`/api/watchlist/list${qs}`)
      setItems(r.items || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const loadSnapshots = async () => {
    if (items.length === 0) return
    setLoadingSnapshot(true)
    try {
      const r = await fetchJson<{ items: WatchlistSnapshot[] }>('/api/watchlist/snapshots')
      const map: Record<string, WatchlistSnapshot> = {}
      for (const it of r.items || []) map[it.stock_code] = it
      setSnapshots(map)
    } catch { /* ignore */ }
    finally { setLoadingSnapshot(false) }
  }

  useEffect(() => { loadGroups() }, [])
  useEffect(() => { loadItems() }, [activeGroupId])
  useEffect(() => { if (items.length > 0) loadSnapshots() }, [items.length])

  const pinned = useMemo(() => items.filter((x) => x.pinned), [items])
  const normal = useMemo(() => items.filter((x) => !x.pinned), [items])

  const handleCreateGroup = async (name: string) => {
    try {
      await postJson('/api/watchlist/groups', { name })
      toast('success', `分组「${name}」创建成功`)
      await loadGroups()
    } catch (e) {
      toast('error', `分组创建失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const handleRenameGroup = async (id: number, name: string) => {
    try {
      await postJson(`/api/watchlist/groups/${id}/rename`, { name })
      toast('success', `分组重命名成功`)
      await loadGroups()
    } catch (e) {
      toast('error', `分组重命名失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const handleDeleteGroup = async (id: number) => {
    try {
      await fetchJson(`/api/watchlist/groups/${id}`, { method: 'DELETE' })
      toast('success', `分组删除成功`)
      if (activeGroupId === id) setActiveGroupId(null)
      await loadGroups()
    } catch (e) {
      toast('error', `分组删除失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const add = async (item: StockSearchItem) => {
    setErr(null)
    try {
      await postJson('/api/watchlist/with-groups', { stock_code: item.code, group_ids: selectedGroupIds })
      setSelectedGroupIds([])
      await loadItems()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const del = async (code: string) => {
    setErr(null)
    try {
      await fetchJson(`/api/watchlist/${encodeURIComponent(code)}`, { method: 'DELETE' })
      await loadItems()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const pin = async (code: string, pinned: boolean) => {
    setErr(null)
    try {
      await fetchJson(`/api/watchlist/${encodeURIComponent(code)}/pin`, {
        method: 'PUT', body: JSON.stringify({ pinned })
      })
      await loadItems()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const saveOrder = async (nextPinned: WatchlistItem[], nextNormal: WatchlistItem[]) => {
    const ordered = [...nextPinned, ...nextNormal].map((x) => x.stock_code)
    await fetchJson('/api/watchlist/reorder', { method: 'PUT', body: JSON.stringify({ codes: ordered }) })
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
      const nextPinned = arrayMove(pinned, pinned.findIndex((x) => x.stock_code === activeId), pinned.findIndex((x) => x.stock_code === overId))
      setItems([...nextPinned, ...normal])
      try { await saveOrder(nextPinned, normal) } catch (e) { setErr(e instanceof Error ? e.message : String(e)); await loadItems() }
      return
    }
    if (inNormal && inNormalOver) {
      const nextNormal = arrayMove(normal, normal.findIndex((x) => x.stock_code === activeId), normal.findIndex((x) => x.stock_code === overId))
      setItems([...pinned, ...nextNormal])
      try { await saveOrder(pinned, nextNormal) } catch (e) { setErr(e instanceof Error ? e.message : String(e)); await loadItems() }
    }
  }

  const allTab = { id: null, label: `全部 (${items.length})` }
  const tabs = [allTab, ...groups.map((g) => ({ id: g.id, label: `${g.name}` }))]

  return (
    <div className="space-y-4">
      {/* 手动添加 */}
      <Card>
        <CardHeader title="手动添加" />
        <CardBody>
          {err && !showGroupManager ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-full max-w-sm">
              <StockPicker
                mode="single"
                placeholder="搜索股票代码或名称"
                onChange={(v) => { if (v) add(v as StockSearchItem) }}
              />
            </div>
            {groups.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-zinc-500">添加到分组：</span>
                {groups.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => setSelectedGroupIds((prev) =>
                      prev.includes(g.id) ? prev.filter((id) => id !== g.id) : [...prev, g.id]
                    )}
                    className={cn(
                      'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition',
                      selectedGroupIds.includes(g.id)
                        ? 'border-blue-300 bg-blue-50 text-blue-700'
                        : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                    )}
                  >
                    {selectedGroupIds.includes(g.id) ? <Minus className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
                    {g.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      {/* 分组 Tab + 自选股列表 */}
      <Card>
        <CardHeader
          title="自选股列表"
          right={
            <button
              type="button"
              onClick={() => setShowGroupManager(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 transition hover:bg-zinc-50"
            >
              <Settings className="h-3.5 w-3.5" />
              管理分组
            </button>
          }
        />
        <div className="border-b border-zinc-100 px-4 pt-3">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => (
              <button
                key={String(tab.id)}
                type="button"
                onClick={() => setActiveGroupId(tab.id)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm transition',
                  activeGroupId === tab.id
                    ? 'bg-zinc-900 font-medium text-white'
                    : 'text-zinc-600 hover:bg-zinc-100'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <CardBody>
          {loading ? <div className="py-6 text-center text-sm text-zinc-500">加载中…</div>
            : items.length === 0 ? <div className="py-6 text-center text-sm text-zinc-500">暂无自选股</div>
            : (
              <div className="space-y-4">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  {pinned.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-zinc-600">置顶</div>
                      <SortableContext items={pinned.map((x) => x.stock_code)} strategy={verticalListSortingStrategy}>
                        <div className="space-y-2">
                          {pinned.map((it) => (
                            <SortableRow key={it.stock_code} item={it} snapshot={snapshots[it.stock_code]}
                              groupNames={groupNameMap} onPin={pin} onDelete={del} />
                          ))}
                        </div>
                      </SortableContext>
                    </div>
                  )}
                  {normal.length > 0 && (
                    <div className="space-y-2">
                      {pinned.length > 0 && <div className="text-xs font-semibold text-zinc-600">普通</div>}
                      <SortableContext items={normal.map((x) => x.stock_code)} strategy={verticalListSortingStrategy}>
                        <div className="space-y-2">
                          {normal.map((it) => (
                            <SortableRow key={it.stock_code} item={it} snapshot={snapshots[it.stock_code]}
                              groupNames={groupNameMap} onPin={pin} onDelete={del} />
                          ))}
                        </div>
                      </SortableContext>
                    </div>
                  )}
                </DndContext>
              </div>
            )}
        </CardBody>
      </Card>

      {showGroupManager && (
        <GroupManagerModal
          groups={groups}
          onClose={() => setShowGroupManager(false)}
          onCreate={handleCreateGroup}
          onRename={handleRenameGroup}
          onDelete={handleDeleteGroup}
        />
      )}
    </div>
  )
}

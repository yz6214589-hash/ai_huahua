/**
 * 股票列表管理页面
 * 提供股票分组的 CRUD 操作以及组内股票的管理功能
 */

import { Loading } from '@/components/Loading'
import { useEffect, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { ArrowLeft, Edit, Plus, Trash2, Upload, X } from 'lucide-react'

/* ───────────── 类型定义 ───────────── */

interface StockGroup {
  id: number
  name: string
  description?: string
  stock_count: number
}

interface StockGroupItem {
  id: number
  stock_code: string
  stock_name?: string | null
}

interface StockGroupsResponse {
  groups: StockGroup[]
}

interface StockGroupItemsResponse {
  items: StockGroupItem[]
}

/* ───────────── 子组件：创建 / 编辑分组弹窗 ───────────── */

interface GroupFormModalProps {
  group: StockGroup | null          // null 表示新建，非 null 表示编辑
  onClose: () => void
  onSaved: () => void
}

function GroupFormModal({ group, onClose, onSaved }: GroupFormModalProps) {
  const [name, setName] = useState(group?.name ?? '')
  const [description, setDescription] = useState(group?.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError('分组名称不能为空')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const body = { name: trimmedName, description: description.trim() }
      if (group) {
        // 编辑已有分组
        await fetchJson<{ ok: boolean }>(`/api/v1/stock-groups/${group.id}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        })
      } else {
        // 新建分组
        await postJson<{ ok: boolean }>('/api/v1/stock-groups', body)
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900">
            {group ? '编辑分组' : '新建分组'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}

        <div className="space-y-3">
          <label className="block">
            <span className="text-xs text-zinc-500">分组名称</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入分组名称"
              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
            />
          </label>
          <label className="block">
            <span className="text-xs text-zinc-500">描述（可选）</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="请输入分组描述"
              rows={3}
              className="mt-1 w-full resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
            />
          </label>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
          >
            取消
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={handleSubmit}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ───────────── 子组件：批量添加股票弹窗 ───────────── */

interface BatchAddModalProps {
  groupId: number
  onClose: () => void
  onSaved: () => void
}

function BatchAddModal({ groupId, onClose, onSaved }: BatchAddModalProps) {
  const [selectedStocks, setSelectedStocks] = useState<StockSearchItem[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    const codes = selectedStocks.map((s) => s.code)
    if (codes.length === 0) {
      setError('请至少选择一只股票')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await postJson<{ ok: boolean }>(`/api/v1/stock-groups/${groupId}/items`, {
        stock_codes: codes,
      })
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900">批量添加股票</h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="text-xs text-zinc-500">
            选择股票（多选，可搜索添加）
          </span>
          <StockPicker
            mode="multiple"
            value={selectedStocks}
            onChange={(v) => setSelectedStocks((v as StockSearchItem[]) || [])}
            placeholder="搜索股票代码或名称"
            className="mt-1"
          />
        </label>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
          >
            取消
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={handleSubmit}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            <Upload className="h-3.5 w-3.5" />
            {saving ? '添加中...' : '添加'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ───────────── 主页面 ───────────── */

export default function StockGroups() {
  // 列表状态
  const [groups, setGroups] = useState<StockGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // 弹窗状态
  const [showForm, setShowForm] = useState(false)
  const [editingGroup, setEditingGroup] = useState<StockGroup | null>(null)

  // 详情视图状态
  const [detailGroup, setDetailGroup] = useState<StockGroup | null>(null)
  const [detailItems, setDetailItems] = useState<StockGroupItem[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [showBatch, setShowBatch] = useState(false)

  // ---------- 加载分组列表 ----------

  const loadGroups = async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setErr(null)
    setLoading(true)
    try {
      const data = await fetchJson<StockGroupsResponse>('/api/v1/stock-groups')
      setGroups(data.groups || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadGroups()
  }, [])

  // ---------- 加载分组详情（组内股票列表） ----------

  const loadDetailItems = async (groupId: number) => {
    setDetailLoading(true)
    try {
      const data = await fetchJson<StockGroupItemsResponse>(
        `/api/v1/stock-groups/${groupId}/items`
      )
      setDetailItems(data.items || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setDetailLoading(false)
    }
  }

  const openDetail = (group: StockGroup) => {
    setDetailGroup(group)
    loadDetailItems(group.id)
  }

  const closeDetail = () => {
    setDetailGroup(null)
    setDetailItems([])
    setShowBatch(false)
  }

  // ---------- 删除分组 ----------

  const handleDeleteGroup = async (group: StockGroup) => {
    if (!window.confirm(`确定要删除分组「${group.name}」吗？`)) return
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/v1/stock-groups/${group.id}`, {
        method: 'DELETE',
      })
      await loadGroups()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  // ---------- 删除组内单只股票 ----------

  const handleDeleteItem = async (item: StockGroupItem) => {
    if (!detailGroup) return
    if (!window.confirm(`确定要移出股票「${item.stock_code}」吗？`)) return
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(
        `/api/v1/stock-groups/${detailGroup.id}/items/${item.id}`,
        { method: 'DELETE' }
      )
      await loadDetailItems(detailGroup.id)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  // ---------- 保存成功后回调 ----------

  const handleFormSaved = async () => {
    setShowForm(false)
    setEditingGroup(null)
    await loadGroups()
  }

  const handleBatchSaved = async () => {
    setShowBatch(false)
    if (detailGroup) {
      await loadDetailItems(detailGroup.id)
    }
  }

  // ========== 渲染：分组详情视图 ==========

  if (detailGroup) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button
            onClick={closeDetail}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            返回
          </button>
          <div>
            <div className="text-sm font-semibold text-zinc-900">
              {detailGroup.name}
            </div>
            {detailGroup.description ? (
              <div className="mt-0.5 text-xs text-zinc-500">
                {detailGroup.description}
              </div>
            ) : null}
          </div>
        </div>

        <Card>
          <CardHeader
            title="股票列表"
            right={
              <button
                onClick={() => setShowBatch(true)}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
              >
                <Plus className="h-3.5 w-3.5" />
                批量添加
              </button>
            }
          />
          <CardBody>
            {err ? (
              <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {err}
              </div>
            ) : null}

            {detailLoading ? (
              <div className="py-8 text-center text-xs text-zinc-500">
                加载中...
              </div>
            ) : detailItems.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-400">
                暂无股票数据，请点击"批量添加"按钮添加股票
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-zinc-200 text-zinc-500">
                      <th className="py-2 font-medium">股票代码</th>
                      <th className="py-2 font-medium">股票名称</th>
                      <th className="py-2 text-right font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailItems.map((item) => (
                      <tr
                        key={item.id}
                        className="border-b border-zinc-100 hover:bg-zinc-50"
                      >
                        <td className="py-2 font-mono text-zinc-900">
                          {item.stock_code}
                        </td>
                        <td className="py-2 text-zinc-700">
                          {item.stock_name || '—'}
                        </td>
                        <td className="py-2 text-right">
                          <button
                            onClick={() => handleDeleteItem(item)}
                            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-red-600 transition hover:bg-red-50"
                          >
                            <Trash2 className="h-3 w-3" />
                            删除
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

        {/* 批量添加弹窗 */}
        {showBatch ? (
          <BatchAddModal
            groupId={detailGroup.id}
            onClose={() => setShowBatch(false)}
            onSaved={handleBatchSaved}
          />
        ) : null}
      </div>
    )
  }

  // ========== 渲染：分组列表视图 ==========

  return (
    <div className="space-y-4">
      {/* 标题与操作栏 */}
      <Card>
        <CardHeader
          title="股票分组管理"
          right={
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setEditingGroup(null)
                  setShowForm(true)
                }}
                className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-800"
              >
                <Plus className="h-3.5 w-3.5" />
                新建分组
              </button>
              <button
                onClick={() => loadGroups()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                刷新
              </button>
            </div>
          }
        />
        <CardBody>
          {err ? (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {err}
            </div>
          ) : null}

          {loading && groups.length === 0 ? (
            <Loading className="py-8" size="sm" />
          ) : groups.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-400">
              暂无分组，请点击"新建分组"按钮创建
            </div>
          ) : (
            <div className="space-y-3">
              {groups.map((g) => (
                <div
                  key={g.id}
                  className="flex cursor-pointer items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 transition hover:border-zinc-300"
                  onClick={() => openDetail(g)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-zinc-900">
                      {g.name}
                    </div>
                    {g.description ? (
                      <div className="mt-0.5 truncate text-xs text-zinc-500">
                        {g.description}
                      </div>
                    ) : null}
                    <div className="mt-1 text-xs text-zinc-400">
                      共 {g.stock_count} 只股票
                    </div>
                  </div>
                  <div
                    className="ml-4 flex flex-shrink-0 items-center gap-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      onClick={() => {
                        setEditingGroup(g)
                        setShowForm(true)
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                    >
                      <Edit className="h-3 w-3" />
                      编辑
                    </button>
                    <button
                      onClick={() => handleDeleteGroup(g)}
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-red-600 transition hover:bg-red-50"
                    >
                      <Trash2 className="h-3 w-3" />
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* 创建 / 编辑分组弹窗 */}
      {showForm ? (
        <GroupFormModal
          group={editingGroup}
          onClose={() => {
            setShowForm(false)
            setEditingGroup(null)
          }}
          onSaved={handleFormSaved}
        />
      ) : null}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { fetchJson, postJson } from '@/api/client'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'

interface Group {
  id: number
  name: string
  stock_count: number
}

interface Props {
  defaultValue?: { scopeType: string; groupId: number }
  onChange: (v: { scopeType: string; groupId: number }) => void
}

export default function StockScopeSelector({ defaultValue, onChange }: Props) {
  const [scopeType, setScopeType] = useState(defaultValue?.scopeType || 'all')
  const [groupId, setGroupId] = useState(defaultValue?.groupId || 0)
  const [groups, setGroups] = useState<Group[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newStocks, setNewStocks] = useState<StockSearchItem[]>([])
  const [showAddStock, setShowAddStock] = useState(false)
  const [addStocks, setAddStocks] = useState<StockSearchItem[]>([])

  const loadGroups = () => {
    console.log('[StockScopeSelector] loadGroups: 开始获取分组列表...')
    fetchJson<{ groups: Group[] }>('/api/v1/stock-groups').then(d => {
      if (d.groups) {
        console.log(`[StockScopeSelector] loadGroups: 成功获取 ${d.groups.length} 个分组`, d.groups.map(g => ({ id: g.id, name: g.name, count: g.stock_count })))
        setGroups(d.groups)
      } else {
        console.log('[StockScopeSelector] loadGroups: API 返回空数据', d)
      }
    }).catch((err) => {
      console.error('[StockScopeSelector] loadGroups: 获取分组列表失败', err)
    })
  }

  useEffect(() => { loadGroups() }, [])

  const emit = (st: string, gid: number) => {
    console.log(`[StockScopeSelector] emit: scopeType=${st}, groupId=${gid}`)
    onChange({ scopeType: st, groupId: gid })
  }

  const handleScopeChange = (val: string) => {
    console.log(`[StockScopeSelector] handleScopeChange: ${scopeType} -> ${val}`)
    setScopeType(val)
    if (val !== 'group') setGroupId(0)
    emit(val, val === 'group' ? groupId : 0)
  }

  const handleGroupChange = (gid: number) => {
    console.log(`[StockScopeSelector] handleGroupChange: group ${groupId} -> ${gid}, scopeType=${scopeType}`)
    setGroupId(gid)
    emit(scopeType, gid)
  }

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) {
      console.warn('[StockScopeSelector] handleCreate: 列表名称为空，取消创建')
      return
    }
    console.log(`[StockScopeSelector] handleCreate: 开始创建分组 name="${name}"...`)
    try {
      const resp = await postJson<{ ok: boolean; group: { id: number } }>('/api/v1/stock-groups', { name, description: '' })
      console.log(`[StockScopeSelector] handleCreate: 创建分组响应`, resp)
      if (resp.ok && resp.group) {
        const gid = resp.group.id
        console.log(`[StockScopeSelector] handleCreate: 分组创建成功 id=${gid}`)
        const codes = newStocks.map(s => s.code)
        if (codes.length > 0) {
          console.log(`[StockScopeSelector] handleCreate: 准备添加 ${codes.length} 只股票到分组 ${gid}`, codes)
          const addResp = await postJson(`/api/v1/stock-groups/${gid}/items`, { stock_codes: codes })
          console.log(`[StockScopeSelector] handleCreate: 添加股票响应`, addResp)
        }
        setShowCreate(false)
        setNewName('')
        setNewStocks([])
        loadGroups()
        setScopeType('group')
        setGroupId(gid)
        emit('group', gid)
      } else {
        console.warn(`[StockScopeSelector] handleCreate: 创建失败`, resp)
      }
    } catch (e) {
      console.error(`[StockScopeSelector] handleCreate: 创建异常`, e)
    }
  }

  const handleDelete = async () => {
    if (!groupId) {
      console.warn('[StockScopeSelector] handleDelete: groupId 为 0，无法删除')
      return
    }
    const groupName = groups.find(g => g.id === groupId)?.name || `id=${groupId}`
    console.log(`[StockScopeSelector] handleDelete: 开始删除分组 ${groupName} (id=${groupId})...`)
    try {
      const resp = await fetchJson(`/api/v1/stock-groups/${groupId}`, { method: 'DELETE' })
      console.log(`[StockScopeSelector] handleDelete: 删除响应`, resp)
      setShowDeleteConfirm(false)
      setGroupId(0)
      setScopeType('all')
      emit('all', 0)
      loadGroups()
    } catch (e) {
      console.error(`[StockScopeSelector] handleDelete: 删除异常`, e)
    }
  }

  const handleAddStock = async () => {
    if (!groupId) {
      console.warn('[StockScopeSelector] handleAddStock: groupId 为 0，无法添加')
      return
    }
    const codes = addStocks.map(s => s.code)
    if (codes.length === 0) {
      console.warn('[StockScopeSelector] handleAddStock: 未选择股票')
      return
    }
    const groupName = groups.find(g => g.id === groupId)?.name || `id=${groupId}`
    console.log(`[StockScopeSelector] handleAddStock: 向分组 ${groupName} (id=${groupId}) 添加 ${codes.length} 只股票`, codes)
    try {
      const resp = await postJson(`/api/v1/stock-groups/${groupId}/items`, { stock_codes: codes })
      console.log(`[StockScopeSelector] handleAddStock: 添加结果`, resp)
      setShowAddStock(false)
      setAddStocks([])
      loadGroups()
    } catch (e) {
      console.error(`[StockScopeSelector] handleAddStock: 添加异常`, e)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={scopeType}
        onChange={(e) => handleScopeChange(e.target.value)}
        className="h-7 rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-900 outline-none focus:border-zinc-400"
      >
        <option value="all">全市场</option>
        <option value="watchlist">自选股</option>
        <option value="group">自定义列表</option>
      </select>

      {scopeType === 'group' && (
        <>
          <select
            value={groupId}
            onChange={(e) => handleGroupChange(parseInt(e.target.value) || 0)}
            className="h-7 rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-900 outline-none focus:border-zinc-400"
          >
            <option value={0}>-- 选择分组 --</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}（{g.stock_count}只）</option>
            ))}
          </select>

          {groupId > 0 && (
            <button
              onClick={() => setShowAddStock(true)}
              className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-zinc-200 bg-white text-xs text-zinc-600 transition hover:bg-zinc-50"
              title="添加股票"
            >
              +
            </button>
          )}

          <button
            onClick={() => { setNewName(''); setNewStocks([]); setShowCreate(true) }}
            className="h-7 rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-600 transition hover:bg-zinc-50"
          >
            新建列表
          </button>

          {groupId > 0 && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="h-7 rounded-lg border border-red-200 bg-white px-2 text-xs text-red-500 transition hover:bg-red-50"
            >
              删除列表
            </button>
          )}
        </>
      )}

      {scopeType !== 'group' && (
        <button
          onClick={() => { setNewName(''); setNewStocks([]); setShowCreate(true) }}
          className="h-7 rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-600 transition hover:bg-zinc-50"
        >
          新建列表
        </button>
      )}

      {/* 新建弹窗 */}
      {showCreate && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowCreate(false)}>
          <div className="w-96 rounded-xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 text-sm font-semibold text-zinc-900">新建自定义列表</div>
            <div className="mb-3">
              <label className="mb-1 block text-xs text-zinc-500">列表名称</label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="例如：我的自选股"
                className="h-8 w-full rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-900 outline-none focus:border-zinc-400"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-xs text-zinc-500">选择股票（可搜索多选）</label>
              <StockPicker
                mode="multiple"
                value={newStocks}
                onChange={(v) => setNewStocks((v as StockSearchItem[]) || [])}
                placeholder="搜索股票代码或名称"
                className="mt-1"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-zinc-200 bg-white px-4 py-1.5 text-xs text-zinc-600 transition hover:bg-zinc-50"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                className="rounded-lg bg-zinc-900 px-4 py-1.5 text-xs text-white transition hover:bg-zinc-800"
              >
                确认创建
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* 删除确认 */}
      {showDeleteConfirm && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowDeleteConfirm(false)}>
          <div className="w-80 rounded-xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 text-sm font-semibold text-zinc-900">确认删除</div>
            <div className="mb-4 text-xs text-zinc-500">确定要删除当前选中的分组吗？分组内的股票不会被删除。此操作不可撤销。</div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg border border-zinc-200 bg-white px-4 py-1.5 text-xs text-zinc-600 transition hover:bg-zinc-50"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                className="rounded-lg bg-red-600 px-4 py-1.5 text-xs text-white transition hover:bg-red-700"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* 添加股票弹窗 */}
      {showAddStock && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowAddStock(false)}>
          <div className="w-96 rounded-xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 text-sm font-semibold text-zinc-900">添加股票到当前列表</div>
            <div className="mb-4">
              <label className="mb-1 block text-xs text-zinc-500">选择股票（可搜索多选）</label>
              <StockPicker
                mode="multiple"
                value={addStocks}
                onChange={(v) => setAddStocks((v as StockSearchItem[]) || [])}
                placeholder="搜索股票代码或名称"
                className="mt-1"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddStock(false)}
                className="rounded-lg border border-zinc-200 bg-white px-4 py-1.5 text-xs text-zinc-600 transition hover:bg-zinc-50"
              >
                取消
              </button>
              <button
                onClick={handleAddStock}
                className="rounded-lg bg-zinc-900 px-4 py-1.5 text-xs text-white transition hover:bg-zinc-800"
              >
                确认添加
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

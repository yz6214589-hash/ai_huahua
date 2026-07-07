import { useState, useEffect, useCallback } from 'react'
import { Loading } from '@/components/Loading'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Plus, RefreshCcw, Trash2, TestTube, Key } from 'lucide-react'
import type { ApiKeyItem, ApiKeyCreate } from '@/api/admin'
import { fetchApiKeys, createApiKey, updateApiKey, deleteApiKey, testApiKey, testAllApiKeys } from '@/api/admin'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  moonshot: 'Moonshot',
  azure: 'Azure',
  google: 'Google',
  other: '其他',
}

const KEY_TYPE_LABELS: Record<string, string> = {
  llm: '大语言模型',
  embedding: '嵌入模型',
  image: '图像模型',
}

const STATUS_LABELS: Record<string, { label: string; tone: 'green' | 'red' | 'zinc' }> = {
  active: { label: '正常', tone: 'green' },
  inactive: { label: '已停用', tone: 'zinc' },
  expired: { label: '已过期', tone: 'red' },
}

interface ModalProps {
  open: boolean
  title: string
  initial?: ApiKeyItem
  onClose: () => void
  onConfirm: (data: ApiKeyCreate) => void
}

function ApiKeyModal({ open, title, initial, onClose, onConfirm }: ModalProps) {
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('openai')
  const [keyType, setKeyType] = useState('llm')
  const [plainKey, setPlainKey] = useState('')

  useEffect(() => {
    if (open) {
      setName(initial?.name || '')
      setProvider(initial?.provider || 'openai')
      setKeyType(initial?.key_type || 'llm')
      setPlainKey('')
    }
  }, [open, initial])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-base font-semibold text-zinc-900">{title}</h3>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              placeholder="例如: OpenAI GPT-4"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">提供商</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
            >
              {Object.entries(PROVIDER_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">密钥类型</label>
            <select
              value={keyType}
              onChange={(e) => setKeyType(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
            >
              {Object.entries(KEY_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">密钥值</label>
            <input
              value={plainKey}
              onChange={(e) => setPlainKey(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              placeholder={initial ? '留空则不修改' : 'sk-...'}
              type="password"
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button
            size="sm"
            onClick={() => onConfirm({ name, provider, key_type: keyType, plain_key: plainKey })}
            disabled={!name || (!initial && !plainKey)}
          >
            确认
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function ApiKeysPage() {
  const [items, setItems] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<ApiKeyItem | undefined>(undefined)
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; message: string } | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchApiKeys()
      setItems(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleCreate = useCallback(async (data: ApiKeyCreate) => {
    try {
      await createApiKey(data)
      setModalOpen(false)
      load()
    } catch (e) {
      alert('创建失败: ' + (e instanceof Error ? e.message : String(e)))
    }
  }, [load])

  const handleUpdate = useCallback(async (data: ApiKeyCreate) => {
    if (!editItem) return
    try {
      const payload: Partial<ApiKeyCreate> = { name: data.name, provider: data.provider, key_type: data.key_type }
      if (data.plain_key) payload.plain_key = data.plain_key
      await updateApiKey(editItem.id, payload)
      setModalOpen(false)
      setEditItem(undefined)
      load()
    } catch (e) {
      alert('更新失败: ' + (e instanceof Error ? e.message : String(e)))
    }
  }, [editItem, load])

  const handleDelete = useCallback(async (id: string) => {
    if (!window.confirm('确定要删除此 API 密钥吗？')) return
    try {
      await deleteApiKey(id)
      load()
    } catch (e) {
      alert('删除失败: ' + (e instanceof Error ? e.message : String(e)))
    }
  }, [load])

  const handleTest = useCallback(async (id: string) => {
    setTestingId(id)
    setTestResult(null)
    try {
      const result = await testApiKey(id)
      setTestResult({ id, ...result })
    } catch (e) {
      setTestResult({ id, ok: false, message: e instanceof Error ? e.message : String(e) })
    } finally {
      setTestingId(null)
    }
  }, [])

  const handleTestAll = useCallback(async () => {
    setTestingId('all')
    setTestResult(null)
    try {
      const result = await testAllApiKeys()
      setTestResult({ id: 'all', ...result })
    } catch (e) {
      setTestResult({ id: 'all', ok: false, message: e instanceof Error ? e.message : String(e) })
    } finally {
      setTestingId(null)
    }
  }, [])

  if (loading) return <Loading className="py-20" text="加载中..." />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">管理第三方 AI 服务的 API 密钥</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleTestAll} disabled={testingId === 'all'}>
            <TestTube className="mr-1 h-3.5 w-3.5" />
            全部测试
          </Button>
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCcw className="mr-1 h-3.5 w-3.5" />
            刷新
          </Button>
          <Button size="sm" onClick={() => { setEditItem(undefined); setModalOpen(true) }}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            添加密钥
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          加载失败: {error}
        </div>
      )}

      {testResult && (
        <div className={`rounded-md border px-4 py-2 text-sm ${
          testResult.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'
        }`}>
          {testResult.ok ? '测试通过: ' : '测试失败: '}{testResult.message}
        </div>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 text-left text-xs font-medium text-zinc-500">
                <th className="px-4 py-3">名称</th>
                <th className="px-4 py-3">提供商</th>
                <th className="px-4 py-3">密钥类型</th>
                <th className="px-4 py-3">密钥前缀</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">创建时间</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-zinc-400">
                    <Key className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
                    暂无 API 密钥，点击上方"添加密钥"按钮添加
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const st = STATUS_LABELS[item.status] || { label: item.status, tone: 'zinc' as const }
                  return (
                    <tr key={item.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-4 py-3 font-medium text-zinc-900">{item.name}</td>
                      <td className="px-4 py-3 text-zinc-600">{PROVIDER_LABELS[item.provider] || item.provider}</td>
                      <td className="px-4 py-3 text-zinc-600">{KEY_TYPE_LABELS[item.key_type] || item.key_type}</td>
                      <td className="px-4 py-3 font-mono text-zinc-500">{item.key_prefix}...</td>
                      <td className="px-4 py-3">
                        <Badge tone={st.tone}>{st.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-zinc-500">{item.created_at?.slice(0, 10) || '--'}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleTest(item.id)}
                            disabled={testingId === item.id}
                            className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 disabled:opacity-40"
                            title="测试连接"
                          >
                            {testingId === item.id ? '测试中...' : '测试'}
                          </button>
                          <button
                            onClick={() => { setEditItem(item); setModalOpen(true) }}
                            className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
                            title="编辑"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => handleDelete(item.id)}
                            className="rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50"
                            title="删除"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <ApiKeyModal
        open={modalOpen}
        title={editItem ? '编辑 API 密钥' : '添加 API 密钥'}
        initial={editItem}
        onClose={() => { setModalOpen(false); setEditItem(undefined) }}
        onConfirm={editItem ? handleUpdate : handleCreate}
      />
    </div>
  )
}

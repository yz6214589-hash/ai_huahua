import { useState, useCallback, useEffect } from 'react'
import { Card, CardBody } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Plus, RefreshCcw, Trash2, TestTube, Cpu, Power, PowerOff, Link } from 'lucide-react'
import type { ModelConfig, ModelCreate } from '@/api/admin'
import { cn } from '@/lib/utils'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  moonshot: 'Moonshot',
  azure: 'Azure',
  google: 'Google',
  qwen: 'Qwen',
  other: '其他',
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-green-100 text-green-700',
  anthropic: 'bg-purple-100 text-purple-700',
  deepseek: 'bg-blue-100 text-blue-700',
  moonshot: 'bg-amber-100 text-amber-700',
  azure: 'bg-sky-100 text-sky-700',
  google: 'bg-indigo-100 text-indigo-700',
  qwen: 'bg-orange-100 text-orange-700',
}

const STATUS_LABELS: Record<string, { label: string; tone: 'green' | 'red' | 'zinc' }> = {
  active: { label: '已启用', tone: 'green' },
  inactive: { label: '已停用', tone: 'zinc' },
}

// Mock data
const MOCK_MODELS: ModelConfig[] = [
  { id: '1', name: '默认对话模型', provider: 'openai', model_name: 'gpt-4o', api_key_ref: '主密钥', base_url: 'https://api.openai.com/v1', status: 'active', sort_order: 1, created_at: '2026-01-15T08:00:00Z', updated_at: '2026-05-20T10:30:00Z' },
  { id: '2', name: '备用对话模型', provider: 'anthropic', model_name: 'claude-3-5-sonnet-20241022', api_key_ref: 'Claude密钥', base_url: 'https://api.anthropic.com', status: 'active', sort_order: 2, created_at: '2026-02-10T08:00:00Z', updated_at: '2026-05-18T14:00:00Z' },
  { id: '3', name: '嵌入模型', provider: 'openai', model_name: 'text-embedding-3-small', api_key_ref: '主密钥', base_url: 'https://api.openai.com/v1', status: 'active', sort_order: 3, created_at: '2026-01-20T08:00:00Z', updated_at: '2026-04-15T09:00:00Z' },
  { id: '4', name: '图像生成模型', provider: 'openai', model_name: 'dall-e-3', api_key_ref: '主密钥', base_url: 'https://api.openai.com/v1', status: 'inactive', sort_order: 4, created_at: '2026-03-01T08:00:00Z', updated_at: '2026-03-01T08:00:00Z' },
  { id: '5', name: '本地推理模型', provider: 'other', model_name: 'qwen2.5-14b', api_key_ref: '本地密钥', base_url: 'http://localhost:8000/v1', status: 'active', sort_order: 5, created_at: '2026-04-10T08:00:00Z', updated_at: '2026-05-22T16:00:00Z' },
]

const MOCK_API_KEYS = ['主密钥', 'Claude密钥', 'DeepSeek密钥', '本地密钥']

interface ModelModalProps {
  open: boolean
  title: string
  initial?: ModelConfig
  onClose: () => void
  onConfirm: (data: ModelCreate) => void
}

function ModelModal({ open, title, initial, onClose, onConfirm }: ModelModalProps) {
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('openai')
  const [modelName, setModelName] = useState('')
  const [apiKeyRef, setApiKeyRef] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [sortOrder, setSortOrder] = useState(0)

  useEffect(() => {
    if (open) {
      setName(initial?.name || '')
      setProvider(initial?.provider || 'openai')
      setModelName(initial?.model_name || '')
      setApiKeyRef(initial?.api_key_ref || '')
      setBaseUrl(initial?.base_url || '')
      setSortOrder(initial?.sort_order || 0)
    }
  }, [open, initial])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-base font-semibold text-zinc-900">{title}</h3>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">模型名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              placeholder="例如: 默认对话模型"
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
            <label className="mb-1 block text-xs font-medium text-zinc-600">模型标识</label>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm font-mono focus:border-zinc-500 focus:outline-none"
              placeholder="例如: gpt-4o"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">关联 API 密钥</label>
            <select
              value={apiKeyRef}
              onChange={(e) => setApiKeyRef(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
            >
              <option value="">请选择</option>
              {MOCK_API_KEYS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm font-mono focus:border-zinc-500 focus:outline-none"
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">排序权重</label>
            <input
              type="number"
              value={sortOrder}
              onChange={(e) => setSortOrder(Number(e.target.value))}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
              placeholder="数值越小越靠前"
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button
            size="sm"
            onClick={() => onConfirm({ name, provider, model_name: modelName, api_key_ref: apiKeyRef || undefined, base_url: baseUrl || undefined, sort_order: sortOrder || undefined })}
            disabled={!name || !modelName}
          >
            确认
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AdminModels() {
  const [items, setItems] = useState<ModelConfig[]>(MOCK_MODELS)
  const [modalOpen, setModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<ModelConfig | undefined>(undefined)
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; message: string } | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeModels = items.filter((m) => m.status === 'active')
  const providers = [...new Set(items.map((m) => m.provider))]
  const defaultModel = items.find((m) => m.sort_order === 1)

  const statsCards = [
    { label: '已配置模型', value: items.length, icon: Cpu, color: 'text-blue-600 bg-blue-50' },
    { label: '默认模型', value: defaultModel?.name || '无', icon: Cpu, color: 'text-green-600 bg-green-50' },
    { label: '可用提供商', value: providers.length, icon: Cpu, color: 'text-amber-600 bg-amber-50' },
    { label: '已启用', value: activeModels.length, icon: Power, color: 'text-zinc-600 bg-zinc-50' },
  ]

  const handleCreate = useCallback((data: ModelCreate) => {
    const newItem: ModelConfig = {
      id: String(Date.now()),
      ...data,
      api_key_ref: data.api_key_ref || '',
      base_url: data.base_url || '',
      status: 'active',
      sort_order: data.sort_order || items.length + 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setItems((prev) => [...prev, newItem])
    setModalOpen(false)
  }, [items])

  const handleUpdate = useCallback((data: ModelCreate) => {
    if (!editItem) return
    setItems((prev) =>
      prev.map((item) =>
        item.id === editItem.id
          ? { ...item, ...data, api_key_ref: data.api_key_ref || '', base_url: data.base_url || '', sort_order: data.sort_order || 0, updated_at: new Date().toISOString() }
          : item
      )
    )
    setModalOpen(false)
    setEditItem(undefined)
  }, [editItem])

  const handleDelete = useCallback((id: string) => {
    if (!window.confirm('确定要删除此模型配置吗？')) return
    setItems((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const handleTest = useCallback(async (id: string) => {
    setTestingId(id)
    setTestResult(null)
    await new Promise((r) => setTimeout(r, 800))
    const item = items.find((m) => m.id === id)
    if (item) {
      setTestResult({ id, ok: true, message: `${item.name} 连接测试通过 (模拟结果)` })
    } else {
      setTestResult({ id, ok: false, message: '模型未找到' })
    }
    setTestingId(null)
  }, [items])

  const handleToggleStatus = useCallback((id: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active'
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, status: newStatus, updated_at: new Date().toISOString() } : item
      )
    )
  }, [])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {statsCards.map((card) => (
          <Card key={card.label}>
            <CardBody className="flex items-center gap-3 px-4 py-3">
              <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', card.color)}>
                <card.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-lg font-semibold text-zinc-900">{card.value}</div>
                <div className="text-xs text-zinc-500">{card.label}</div>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">管理和配置 AI 模型连接信息</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setItems([...MOCK_MODELS])}>
            <RefreshCcw className="mr-1 h-3.5 w-3.5" />
            刷新
          </Button>
          <Button size="sm" onClick={() => { setEditItem(undefined); setModalOpen(true) }}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            添加模型
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
                <th className="px-4 py-3">模型名称</th>
                <th className="px-4 py-3">提供商</th>
                <th className="px-4 py-3">模型标识</th>
                <th className="px-4 py-3">关联密钥</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">排序</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-zinc-400">
                    <Cpu className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
                    暂无模型配置，点击上方"添加模型"按钮添加
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const st = STATUS_LABELS[item.status] || { label: item.status, tone: 'zinc' as const }
                  const providerColor = PROVIDER_COLORS[item.provider] || 'bg-zinc-100 text-zinc-700'
                  return (
                    <tr key={item.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-4 py-3 font-medium text-zinc-900">{item.name}</td>
                      <td className="px-4 py-3">
                        <span className={cn('inline-block rounded px-2 py-0.5 text-xs font-medium', providerColor)}>
                          {PROVIDER_LABELS[item.provider] || item.provider}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-600">{item.model_name}</td>
                      <td className="px-4 py-3">
                        <a
                          href="/admin/api-keys"
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                          onClick={(e) => { e.preventDefault(); window.location.href = '/admin/api-keys' }}
                        >
                          <Link className="h-3 w-3" />
                          {item.api_key_ref}
                        </a>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={st.tone}>{st.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-zinc-500">{item.sort_order}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleToggleStatus(item.id, item.status)}
                            className="rounded px-2 py-1 text-xs hover:bg-zinc-100"
                            title={item.status === 'active' ? '停用' : '启用'}
                          >
                            {item.status === 'active' ? (
                              <Power className="h-3.5 w-3.5 text-green-600" />
                            ) : (
                              <PowerOff className="h-3.5 w-3.5 text-zinc-400" />
                            )}
                          </button>
                          <button
                            onClick={() => handleTest(item.id)}
                            disabled={testingId === item.id}
                            className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 disabled:opacity-40"
                            title="测试连接"
                          >
                            {testingId === item.id ? '测试中...' : <TestTube className="h-3.5 w-3.5" />}
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

      <ModelModal
        open={modalOpen}
        title={editItem ? '编辑模型配置' : '添加模型'}
        initial={editItem}
        onClose={() => { setModalOpen(false); setEditItem(undefined) }}
        onConfirm={editItem ? handleUpdate : handleCreate}
      />
    </div>
  )
}

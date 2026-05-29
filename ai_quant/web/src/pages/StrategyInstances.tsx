import { useEffect, useState, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ChevronDown, Plus, Trash2, RefreshCcw } from 'lucide-react'

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'object'
    label: string; help: string
    min?: number; max?: number; step?: number
    default?: number | string | boolean
    values?: string[]
  }>
  default_params: Record<string, unknown>
}

interface StrategyInstance {
  instance_id: string
  strategy_id: string
  name: string
  params: Record<string, unknown>
}

export default function StrategyInstances() {
  const [searchParams] = useSearchParams()
  const urlStrategyId = searchParams.get('strategy_id')
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [instances, setInstances] = useState<StrategyInstance[]>([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [formStrategyId, setFormStrategyId] = useState('')
  const [formName, setFormName] = useState('')
  const [formParams, setFormParams] = useState<Record<string, string>>({})
  // 记录用户是否手动编辑过实例名称
  const nameEditedByUser = useRef(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [s, i] = await Promise.all([
        fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies'),
        fetchJson<{ instances: StrategyInstance[] }>('/api/v1/analysis/strategy-instances'),
      ])
      setStrategies(s.strategies || [])
      setInstances(i.instances || [])
      // 如果 URL 中携带了 strategy_id，自动打开表单并选中该策略
      if (urlStrategyId && s.strategies?.find((st) => st.strategy_id === urlStrategyId)) {
        setShowForm(true)
        setFormName('')
        handleStrategyChange(urlStrategyId, s.strategies)
      }
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  const currentStrategy = strategies.find((s) => s.strategy_id === formStrategyId)

  /** 根据策略名称和参数值自动生成实例名 */
  const generateAutoName = (sid: string, params: Record<string, string>) => {
    const def = strategies.find((s) => s.strategy_id === sid)
    if (!def) return ''
    const paramValues = Object.values(params)
      .filter((v) => v !== '' && v !== undefined && v !== null)
      .join('_')
    return paramValues ? `${def.name}_${paramValues}` : def.name
  }

  // 当策略或参数变化时，自动生成实例名称（仅当用户未手动编辑时）
  useEffect(() => {
    if (!nameEditedByUser.current) {
      setFormName(generateAutoName(formStrategyId, formParams))
    }
  }, [formStrategyId, formParams])

  const openForm = () => {
    nameEditedByUser.current = false
    setShowForm(true)
    setFormStrategyId(strategies[0]?.strategy_id || '')
    setFormName('')
    const def = strategies[0]
    if (def) {
      const p: Record<string, string> = {}
      for (const [k, v] of Object.entries(def.default_params)) {
        p[k] = String(v ?? '')
      }
      setFormParams(p)
    }
    // 确保新建实例面板在视口内可见
    setTimeout(() => {
      const formCard = document.querySelector('[data-testid="create-instance-form"]')
      if (formCard) {
        formCard.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 100)
  }

  const handleStrategyChange = (sid: string, allStrategies?: StrategyDef[]) => {
    nameEditedByUser.current = false
    setFormStrategyId(sid)
    const src = allStrategies || strategies
    const def = src.find((s) => s.strategy_id === sid)
    if (def) {
      const p: Record<string, string> = {}
      for (const [k, v] of Object.entries(def.default_params)) {
        p[k] = String(v ?? '')
      }
      setFormParams(p)
    }
  }

  const submit = async () => {
    if (!formStrategyId || !formName.trim()) {
      toast('error', '请填写策略和实例名称')
      return
    }
    const def = strategies.find((s) => s.strategy_id === formStrategyId)
    if (!def) return
    const params: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(formParams)) {
      if (k in (def.params_schema || {})) {
        const meta = def.params_schema[k]
        if (meta.type === 'int') params[k] = parseInt(String(v), 10)
        else if (meta.type === 'float') params[k] = parseFloat(String(v))
        else if (meta.type === 'bool') params[k] = v === 'true'
        else if (meta.type === 'enum') params[k] = String(v)
        else if (meta.type === 'object') {
          try { params[k] = JSON.parse(String(v)) }
          catch { params[k] = {} }
        } else params[k] = v
      }
    }
    try {
      await postJson('/api/v1/analysis/strategy-instances', { strategy_id: formStrategyId, name: formName.trim(), params })
      toast('success', `实例「${formName}」创建成功`)
      setShowForm(false)
      nameEditedByUser.current = false
      await loadAll()
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    }
  }

  const delInstance = async (id: string) => {
    try {
      await fetchJson(`/api/v1/analysis/strategy-instances/${id}`, { method: 'DELETE' })
      toast('success', '实例删除成功')
      await loadAll()
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    }
  }

  const grouped = instances.reduce((acc, inst) => {
    const s = strategies.find((s) => s.strategy_id === inst.strategy_id)
    const groupName = s?.name || inst.strategy_id
    if (!acc[groupName]) acc[groupName] = []
    acc[groupName].push(inst)
    return acc
  }, {} as Record<string, StrategyInstance[]>)

  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const toggleGroup = (name: string) => {
    setExpandedGroups((prev) => ({ ...prev, [name]: prev[name] === false ? true : false }))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">共 {instances.length} 个策略实例</div>
        <div className="flex gap-2">
          <button onClick={loadAll} disabled={loading} className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
            <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button onClick={openForm} className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800">
            <Plus className="h-4 w-4" />
            新建实例
          </button>
        </div>
      </div>

      {showForm && (
        <Card data-testid="create-instance-form">
          <CardHeader title="新建策略实例" />
          <CardBody>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="mb-1 text-xs text-zinc-500">所属策略</div>
                  <select
                    value={formStrategyId}
                    onChange={(e) => handleStrategyChange(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    {strategies.map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">实例名称</div>
                  <input
                    value={formName}
                    onChange={(e) => {
                      nameEditedByUser.current = true
                      setFormName(e.target.value)
                    }}
                    placeholder="自动生成策略名称_参数值"
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
              </div>
              {currentStrategy && Object.keys(currentStrategy.params_schema).length > 0 && (
                <div>
                  <div className="mb-2 text-xs font-semibold text-zinc-900">参数配置</div>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(currentStrategy.params_schema).map(([key, meta]) => (
                      <div key={key}>
                        <div className="mb-1 text-xs text-zinc-500">{meta.label}</div>
                        {meta.type === 'bool' ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={formParams[key] === 'true'}
                              onChange={(e) => setFormParams((p) => ({ ...p, [key]: String(e.target.checked) }))}
                              className="h-4 w-4 accent-zinc-900"
                            />
                            <span className="text-xs text-zinc-500">{formParams[key] === 'true' ? '开启' : '关闭'}</span>
                          </div>
                        ) : meta.type === 'enum' ? (
                          <select
                            value={formParams[key] ?? ''}
                            onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          >
                            {meta.values?.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        ) : meta.type === 'object' ? (
                          <textarea
                            value={formParams[key] ?? '{}'}
                            onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                            rows={2}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-mono outline-none focus:border-zinc-400"
                            placeholder='{"key": "value"}'
                          />
                        ) : (
                          <input
                            type="number"
                            value={formParams[key] ?? String(meta.default ?? '')}
                            onChange={(e) => setFormParams((p) => ({ ...p, [key]: e.target.value }))}
                            min={meta.min}
                            max={meta.max}
                            step={meta.step}
                            className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        )}
                        <div className="mt-0.5 text-xs text-zinc-400">{meta.help}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={submit} className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">
                  <Plus className="h-4 w-4" />
                  保存实例
                </button>
                <button onClick={() => { nameEditedByUser.current = false; setShowForm(false) }} className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  取消
                </button>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {Object.entries(grouped).map(([groupName, insts]) => {
        const isExpanded = expandedGroups[groupName] !== false
        return (
          <div key={groupName} className="rounded-lg border border-zinc-200 bg-white">
            <button
              onClick={() => toggleGroup(groupName)}
              className="flex w-full items-center justify-between px-6 py-4 border-b border-zinc-200"
            >
              <h3 className="text-lg font-semibold text-zinc-900">{groupName}</h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400">{insts.length} 个实例</span>
                <ChevronDown className={`h-4 w-4 text-zinc-400 transition-transform ${isExpanded ? 'rotate-0' : '-rotate-90'}`} />
              </div>
            </button>
            {isExpanded && (
              <div className="px-6 py-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {insts.map((inst) => (
                    <div key={inst.instance_id} className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-zinc-900 truncate">{inst.name}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {Object.entries(inst.params).map(([k, v]) => (
                            <span key={k} className="rounded border border-zinc-200 bg-white px-1.5 py-0.5 text-xs text-zinc-600">
                              {k}={String(v)}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-2 ml-3">
                        <a
                          href={`/strategy/backtest?instance_id=${inst.instance_id}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                        >
                          回测
                        </a>
                        <button
                          onClick={() => delInstance(inst.instance_id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )
      })}

      {!loading && instances.length === 0 && !showForm && (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-12 text-center text-sm text-zinc-500">
          暂无策略实例，点击上方「新建实例」开始
        </div>
      )}
    </div>
  )
}

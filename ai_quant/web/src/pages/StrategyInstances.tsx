import { Loading } from '@/components/Loading'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { ChevronDown, Plus, Trash2, RefreshCcw } from 'lucide-react'

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'select' | 'object'
    label: string; help: string
    min?: number; max?: number; step?: number
    default?: number | string | boolean
    values?: string[]
    options?: { value: string; label: string }[]
    section?: string
    show_if?: { field: string; value: string | boolean }
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
  const navigate = useNavigate()
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [instances, setInstances] = useState<StrategyInstance[]>([])
  const [loading, setLoading] = useState(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [s, i] = await Promise.all([
        fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies'),
        fetchJson<{ instances: StrategyInstance[] }>('/api/v1/analysis/strategy-instances'),
      ])
      setStrategies(s.strategies || [])
      setInstances(i.instances || [])
    } catch (e) {
      toast('error', e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

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
          <button onClick={() => navigate('/strategy/instances/create' + (urlStrategyId ? `?strategy_id=${urlStrategyId}` : ''))} className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800">
            <Plus className="h-4 w-4" />
            新建实例
          </button>
        </div>
      </div>

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

      {loading ? <Loading className="py-12" /> : null}

      {!loading && instances.length === 0 && (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-12 text-center text-sm text-zinc-500">
          暂无策略实例
        </div>
      )}
    </div>
  )
}

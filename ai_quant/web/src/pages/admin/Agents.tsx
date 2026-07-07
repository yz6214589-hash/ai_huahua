import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardBody } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Loading } from '@/components/Loading'
import { cn } from '@/lib/utils'
import { RefreshCcw, Save, User, Wrench, Braces, Cpu, ChevronDown, Check, X, Search } from 'lucide-react'
import type { AgentConfig, AgentDefault, ModelConfig, ToolItem } from '@/api/admin'
import { fetchAgents, updateAgent, fetchAgentDefaults, fetchModels, fetchTools } from '@/api/admin'

const AGENT_COLORS: Record<string, string> = {
  charles: 'bg-blue-100 text-blue-700 border-blue-200',
  zoe: 'bg-purple-100 text-purple-700 border-purple-200',
  kris: 'bg-amber-100 text-amber-700 border-amber-200',
  ethan: 'bg-red-100 text-red-700 border-ethan-200',
  ceo: 'bg-zinc-100 text-zinc-700 border-zinc-200',
}

const AGENT_BADGE_COLORS: Record<string, string> = {
  charles: 'bg-blue-100 text-blue-700',
  zoe: 'bg-purple-100 text-purple-700',
  kris: 'bg-amber-100 text-amber-700',
  ethan: 'bg-red-100 text-red-700',
  ceo: 'bg-zinc-100 text-zinc-700',
}

const DEFAULT_AGENTS: AgentDefault[] = [
  { role: 'charles', name: 'Charles', description: 'AI 投资研究助手，负责信息收集、市场分析和研究报告生成', color: 'blue' },
  { role: 'zoe', name: 'Zoe', description: 'AI 数据分析助手，负责技术指标计算、数据可视化和量化分析', color: 'purple' },
  { role: 'kris', name: 'Kris', description: 'AI 交易执行助手，负责策略执行、订单管理和风险控制', color: 'amber' },
  { role: 'ethan', name: 'Ethan', description: 'AI 风控审核助手，负责合规检查、规则匹配和异常监控', color: 'red' },
  { role: 'ceo', name: 'CEO', description: 'AI 决策汇总助手，负责多智能体协调、综合决策和报告整合', color: 'gray' },
]

// 多选下拉组件
function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = '请选择...',
  emptyText = '暂无可选项',
}: {
  options: ToolItem[]
  selected: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  emptyText?: string
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  // 内部维护选中状态，避免连续点击时基于过期 props
  const [internalSelected, setInternalSelected] = useState<string[]>(selected)
  const containerRef = useRef<HTMLDivElement>(null)

  // 同步外部 prop 变化
  useEffect(() => {
    setInternalSelected(selected)
  }, [selected])

  // 点击外部关闭下拉
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const filtered = options.filter((o) => {
    if (!search) return true
    const s = search.toLowerCase()
    return (
      o.name.toLowerCase().includes(s) ||
      (o.description || '').toLowerCase().includes(s) ||
      (o.title || '').toLowerCase().includes(s)
    )
  })

  const toggle = (name: string) => {
    setInternalSelected((prev) => {
      const next = prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
      onChange(next)
      return next
    })
  }

  const removeTag = (e: React.MouseEvent, name: string) => {
    e.stopPropagation()
    setInternalSelected((prev) => {
      const next = prev.filter((s) => s !== name)
      onChange(next)
      return next
    })
  }

  return (
    <div ref={containerRef} className="relative">
      {/* 触发按钮 */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex min-h-[38px] w-full flex-wrap items-center gap-1 rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-left text-sm focus:border-zinc-500 focus:outline-none',
          open && 'border-zinc-500'
        )}
      >
        {internalSelected.length === 0 ? (
          <span className="flex-1 px-1 text-zinc-400">{placeholder}</span>
        ) : (
          <div className="flex flex-1 flex-wrap items-center gap-1">
            {internalSelected.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700"
              >
                {s}
                <span
                  role="button"
                  aria-label="移除"
                  onClick={(e) => removeTag(e, s)}
                  className="cursor-pointer rounded-sm hover:bg-blue-100"
                >
                  <X className="h-3 w-3" />
                </span>
              </span>
            ))}
          </div>
        )}
        <ChevronDown className={cn('h-4 w-4 text-zinc-400 transition-transform', open && 'rotate-180')} />
      </button>

      {/* 下拉面板 */}
      {open && (
        <div className="absolute left-0 right-0 z-30 mt-1 max-h-72 overflow-hidden rounded-md border border-zinc-200 bg-white shadow-lg">
          {/* 搜索框 */}
          <div className="border-b border-zinc-100 p-2">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索..."
                className="w-full rounded border border-zinc-200 py-1 pl-7 pr-2 text-sm focus:border-zinc-400 focus:outline-none"
                autoFocus
              />
            </div>
          </div>

          {/* 选项列表 */}
          <div className="max-h-56 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-zinc-400">
                {options.length === 0 ? emptyText : '无匹配项'}
              </div>
            ) : (
              filtered.map((opt) => {
                const isSelected = internalSelected.includes(opt.name)
                return (
                  <div
                    key={opt.name}
                    onClick={() => toggle(opt.name)}
                    className={cn(
                      'flex cursor-pointer items-start gap-2 px-3 py-2 text-sm hover:bg-zinc-50',
                      isSelected && 'bg-blue-50'
                    )}
                  >
                    <div
                      className={cn(
                        'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                        isSelected ? 'border-blue-500 bg-blue-500 text-white' : 'border-zinc-300'
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <div className="flex-1 overflow-hidden">
                      <div className="font-medium text-zinc-900">{opt.title || opt.name}</div>
                      {opt.description && (
                        <div className="mt-0.5 line-clamp-2 text-xs text-zinc-500" title={opt.description}>
                          {opt.description}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* 底部操作栏 */}
          {options.length > 0 && (
            <div className="flex items-center justify-between border-t border-zinc-100 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-500">
              <span>已选 {internalSelected.length} / {options.length}</span>
              {internalSelected.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setInternalSelected([])
                    onChange([])
                  }}
                  className="text-zinc-500 hover:text-zinc-700"
                >
                  清空
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AdminAgents() {
  const [agents, setAgents] = useState<AgentConfig[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // 本地编辑状态
  const [editStates, setEditStates] = useState<Record<string, {
    model_id: string
    skills: string[]
    tools: string[]
  }>>({})

  // 可用的 skills 和 tools 列表
  const [availableSkills, setAvailableSkills] = useState<ToolItem[]>([])
  const [availableTools, setAvailableTools] = useState<ToolItem[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [agentData, modelData, toolsData] = await Promise.all([
        fetchAgents().catch(() => [] as AgentConfig[]),
        fetchModels().catch(() => [] as ModelConfig[]),
        fetchTools().catch(() => [] as ToolItem[]),
      ])

      // 分别提取 skills 和 tools
      const skills = toolsData.filter((t) => t.category === 'skill')
      const tools = toolsData.filter((t) => t.category === 'tool')
      setAvailableSkills(skills)
      setAvailableTools(tools)

      let resolvedAgents = agentData
      if (agentData.length === 0) {
        resolvedAgents = DEFAULT_AGENTS.map((d) => ({
          id: d.role,
          role: d.role,
          name: d.name,
          description: d.description,
          model_id: '',
          skills: [],
          tools: [],
          prompt_id: '',
          created_at: '',
          updated_at: '',
        }))
      }

      setAgents(resolvedAgents)
      setModels(modelData)

      const states: Record<string, { model_id: string; skills: string[]; tools: string[] }> = {}
      resolvedAgents.forEach((a) => {
        states[a.id] = {
          model_id: a.model_id || '',
          skills: a.skills || [],
          tools: a.tools || [],
        }
      })
      setEditStates(states)
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSave = useCallback(async (agent: AgentConfig) => {
    const state = editStates[agent.id]
    if (!state) return

    setSaving(agent.id)
    setError(null)
    setSuccessMsg(null)

    try {
      const skills = state.skills
      const tools = state.tools

      const updated = await updateAgent(agent.id, {
        model_id: state.model_id || undefined,
        skills,
        tools,
      })

      setAgents((prev) =>
        prev.map((a) => (a.id === agent.id ? { ...a, ...updated, model_id: state.model_id || a.model_id, skills, tools } : a))
      )
      setSuccessMsg(`${agent.name} 配置已保存`)
      setTimeout(() => setSuccessMsg(null), 2500)
    } catch (e: any) {
      setError(`保存 ${agent.name} 失败: ${e.message}`)
    } finally {
      setSaving(null)
    }
  }, [editStates])

  const handleFieldChange = useCallback((agentId: string, field: 'model_id' | 'skills' | 'tools', value: string | string[]) => {
    setEditStates((prev) => ({
      ...prev,
      [agentId]: {
        ...prev[agentId],
        [field]: value,
      },
    }))
  }, [])

  const getModelName = useCallback((modelId: string) => {
    const model = models.find((m) => m.id === modelId)
    return model ? model.name : ''
  }, [models])

  if (loading) {
    return <Loading className="py-20" text="加载智能体配置..." />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">配置各 AI 智能体的角色、模型关联和可用工具列表</div>
        <Button variant="outline" size="sm" onClick={loadData}>
          <RefreshCcw className="mr-1 h-3.5 w-3.5" />
          刷新
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
          {successMsg}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => {
          const state = editStates[agent.id]
          if (!state) return null

          const agentDefault = DEFAULT_AGENTS.find((d) => d.role === agent.role)
          const colorClass = AGENT_COLORS[agent.role] || 'bg-zinc-100 text-zinc-700 border-zinc-200'
          const badgeColor = AGENT_BADGE_COLORS[agent.role] || 'bg-zinc-100 text-zinc-700'

          return (
            <Card key={agent.id}>
              <div className={cn('rounded-t-lg border-b px-5 py-4', colorClass)}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/80">
                      <User className="h-4 w-4" />
                    </div>
                    <div>
                      <span className={cn('inline-block rounded px-2 py-0.5 text-xs font-semibold', badgeColor)}>
                        {agentDefault?.name || agent.name}
                      </span>
                    </div>
                  </div>
                  <Badge tone={agent.role === 'ceo' ? 'zinc' : agent.role as any}>
                    {agent.role.toUpperCase()}
                  </Badge>
                </div>
                <p className="mt-2 text-xs leading-relaxed opacity-80">
                  {agentDefault?.description || agent.description}
                </p>
              </div>

              <CardBody className="space-y-3">
                <div>
                  <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                    <Cpu className="h-3 w-3" />
                    关联模型
                  </label>
                  <select
                    value={state.model_id}
                    onChange={(e) => handleFieldChange(agent.id, 'model_id', e.target.value)}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
                  >
                    <option value="">未选择</option>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.model_name})
                      </option>
                    ))}
                  </select>
                  {state.model_id && (
                    <p className="mt-1 text-xs text-zinc-400">
                      当前: {getModelName(state.model_id)}
                    </p>
                  )}
                </div>

                <div>
                  <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                    <Wrench className="h-3 w-3" />
                    Skill 列表
                    <span className="text-zinc-400">({state.skills.length}/{availableSkills.length})</span>
                  </label>
                  <MultiSelect
                    options={availableSkills}
                    selected={state.skills}
                    onChange={(v) => handleFieldChange(agent.id, 'skills', v)}
                    placeholder="选择技能..."
                    emptyText="暂无可用技能"
                  />
                </div>

                <div>
                  <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                    <Braces className="h-3 w-3" />
                    工具列表
                    <span className="text-zinc-400">({state.tools.length}/{availableTools.length})</span>
                  </label>
                  <MultiSelect
                    options={availableTools}
                    selected={state.tools}
                    onChange={(v) => handleFieldChange(agent.id, 'tools', v)}
                    placeholder="选择工具..."
                    emptyText="暂无可用工具"
                  />
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-zinc-400">
                    {agent.created_at ? `创建: ${new Date(agent.created_at).toLocaleDateString()}` : ''}
                  </span>
                  <Button
                    size="sm"
                    onClick={() => handleSave(agent)}
                    disabled={saving === agent.id}
                  >
                    <Save className={cn('mr-1 h-3.5 w-3.5', saving === agent.id && 'animate-pulse')} />
                    {saving === agent.id ? '保存中...' : '保存'}
                  </Button>
                </div>
              </CardBody>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

import { useEffect, useRef, useState, useCallback } from 'react'
import { fetchJson } from '@/api/client'
import { Plus, Save, Trash2, GripVertical, X } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/Card'

interface FlowNode {
  id: string
  type: 'start' | 'end' | 'approver' | 'condition' | 'copy'
  label: string
  x: number
  y: number
  approver_name?: string
  condition_field?: string
  condition_operator?: string
  condition_value?: string
}

interface FlowEdge {
  id: string
  source: string
  target: string
  label?: string
}

interface FlowTemplate {
  id: string
  name: string
  description?: string
  status?: 'active' | 'inactive' | 'draft'
  nodes: FlowNode[]
  edges: FlowEdge[]
}

const NODE_TYPES = [
  { type: 'start' as const, label: '开始', color: 'border-green-400 bg-green-50' },
  { type: 'approver' as const, label: '审批节点', color: 'border-blue-400 bg-blue-50' },
  { type: 'condition' as const, label: '条件节点', color: 'border-orange-400 bg-orange-50' },
  { type: 'copy' as const, label: '抄送节点', color: 'border-purple-400 bg-purple-50' },
  { type: 'end' as const, label: '结束', color: 'border-zinc-400 bg-zinc-50' },
]

let nodeCounter = 0

function generateId() {
  nodeCounter++
  return `node_${nodeCounter}_${Date.now()}`
}

function FlowCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  onMoveNode,
  onAddEdge,
  onDeleteNode,
}: {
  nodes: FlowNode[]
  edges: FlowEdge[]
  selectedNodeId: string | null
  onSelectNode: (id: string | null) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onAddEdge: (source: string, target: string) => void
  onDeleteNode: (id: string) => void
}) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null)

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setDraggingId(nodeId)
    setDragOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top })
    onSelectNode(nodeId)
  }

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!draggingId || !canvasRef.current) return
    const canvasRect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - canvasRect.left - dragOffset.x
    const y = e.clientY - canvasRect.top - dragOffset.y
    onMoveNode(draggingId, Math.max(0, x), Math.max(0, y))
  }, [draggingId, dragOffset, onMoveNode])

  const handleMouseUp = useCallback(() => {
    if (connectingFrom) {
      setConnectingFrom(null)
    }
    setDraggingId(null)
  }, [connectingFrom])

  useEffect(() => {
    if (draggingId) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [draggingId, handleMouseMove, handleMouseUp])

  return (
    <div ref={canvasRef} className="relative min-h-[500px] w-full overflow-hidden rounded-lg border-2 border-dashed border-zinc-200 bg-zinc-50/50">
      <svg className="pointer-events-none absolute inset-0 h-full w-full">
        {edges.map(edge => {
          const source = nodes.find(n => n.id === edge.source)
          const target = nodes.find(n => n.id === edge.target)
          if (!source || !target) return null
          const sx = source.x + 75, sy = source.y + 28
          const tx = target.x + 75, ty = target.y
          const cy = (sy + ty) / 2
          return (
            <g key={edge.id}>
              <path d={`M${sx},${sy} C${sx},${cy} ${tx},${cy} ${tx},${ty}`} fill="none" stroke="#d4d4d8" strokeWidth="2" markerEnd="url(#arrowhead)" />
              {edge.label && (
                <text x={(sx + tx) / 2} y={cy - 5} textAnchor="middle" className="fill-zinc-500 text-[11px]">{edge.label}</text>
              )}
            </g>
          )
        })}
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#d4d4d8" />
          </marker>
        </defs>
      </svg>

      <div className="absolute left-3 top-3 z-10 text-xs text-zinc-400">拖拽节点移动 | 悬停显示连接点可连线</div>

      {nodes.map(node => {
        const typeDef = NODE_TYPES.find(t => t.type === node.type)
        const isSelected = selectedNodeId === node.id
        return (
          <div
            key={node.id}
            className={`absolute cursor-grab rounded-lg border-2 px-4 py-2 text-sm shadow-sm transition-shadow hover:shadow-md ${
              typeDef?.color || 'border-zinc-200 bg-white'
            } ${isSelected ? 'ring-2 ring-zinc-900 ring-offset-2' : ''}`}
            style={{ left: node.x, top: node.y, width: 150, zIndex: isSelected ? 10 : 1 }}
            onMouseDown={e => handleMouseDown(e, node.id)}
            onClick={() => onSelectNode(node.id)}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-zinc-700">{node.label}</span>
              <button
                onClick={e => { e.stopPropagation(); onDeleteNode(node.id) }}
                className="rounded p-0.5 text-zinc-400 hover:text-red-500"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            {node.approver_name && <div className="mt-1 text-xs text-zinc-500">审批人: {node.approver_name}</div>}
            {node.condition_field && (
              <div className="mt-1 text-xs text-zinc-500">
                {node.condition_field} {node.condition_operator} {node.condition_value}
              </div>
            )}
            <div
              className={`absolute -bottom-2 left-1/2 h-4 w-4 -translate-x-1/2 cursor-crosshair rounded-full border-2 border-white ${
                connectingFrom === node.id ? 'bg-green-400' : 'bg-zinc-300'
              }`}
              onMouseDown={e => { e.stopPropagation(); setConnectingFrom(node.id) }}
              onMouseUp={e => {
                e.stopPropagation()
                if (connectingFrom && connectingFrom !== node.id) {
                  onAddEdge(connectingFrom, node.id)
                }
                setConnectingFrom(null)
              }}
              title="拖拽到目标节点创建连线"
            />
          </div>
        )
      })}

      {nodes.length === 0 && (
        <div className="flex h-[500px] items-center justify-center text-sm text-zinc-400">
          点击左侧按钮添加节点，拖拽节点连接创建审批流程
        </div>
      )}
    </div>
  )
}

export default function FlowDesigner() {
  const [templates, setTemplates] = useState<FlowTemplate[]>([])
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [templateName, setTemplateName] = useState('')
  const [templateDesc, setTemplateDesc] = useState('')
  const [showNodeEditor, setShowNodeEditor] = useState(false)
  const [editingNodeType, setEditingNodeType] = useState<FlowNode['type']>('approver')
  const [editingNodeLabel, setEditingNodeLabel] = useState('')
  const [approvalConfig, setApprovalConfig] = useState<{
    default_approver: string
    default_condition_field: string
    default_condition_operator: string
    default_condition_value: string
  } | null>(null)

  useEffect(() => {
    fetchJson<{
      default_approver: string
      default_condition_field: string
      default_condition_operator: string
      default_condition_value: string
    }>('/api/v1/approval/config').then(setApprovalConfig).catch(() => {
      // 保留默认值
    })
  }, [])

  const activeTemplate = templates.find(t => t.id === activeTemplateId)

  const createTemplate = () => {
    const id = `tpl_${Date.now()}`
    const newTpl: FlowTemplate = {
      id,
      name: `新审批流程 ${templates.length + 1}`,
      nodes: [
        { id: `${id}_start`, type: 'start', label: '开始', x: 250, y: 50 },
        { id: `${id}_end`, type: 'end', label: '结束', x: 250, y: 400 },
      ],
      edges: [],
    }
    setTemplates([...templates, newTpl])
    setActiveTemplateId(id)
    setTemplateName(newTpl.name)
    setTemplateDesc('')
  }

  const addNode = () => {
    if (!activeTemplate) return
    const id = generateId()
    const yOff = activeTemplate.nodes.length * 80
    const newNode: FlowNode = {
      id,
      type: editingNodeType,
      label: editingNodeLabel || NODE_TYPES.find(t => t.type === editingNodeType)?.label || '节点',
      x: 200 + Math.random() * 100,
      y: 100 + yOff,
      approver_name: editingNodeType === 'approver' ? (approvalConfig?.default_approver || '审批人') : undefined,
      condition_field: editingNodeType === 'condition' ? (approvalConfig?.default_condition_field || '金额') : undefined,
      condition_operator: editingNodeType === 'condition' ? (approvalConfig?.default_condition_operator || '>') : undefined,
      condition_value: editingNodeType === 'condition' ? (approvalConfig?.default_condition_value || '100000') : undefined,
    }
    setTemplates(templates.map(t => t.id === activeTemplate.id
      ? { ...t, nodes: [...t.nodes, newNode] }
      : t
    ))
    setShowNodeEditor(false)
    setEditingNodeLabel('')
  }

  const updateNodePosition = (nodeId: string, x: number, y: number) => {
    if (!activeTemplate) return
    setTemplates(templates.map(t => t.id === activeTemplate.id
      ? { ...t, nodes: t.nodes.map(n => n.id === nodeId ? { ...n, x, y } : n) }
      : t
    ))
  }

  const deleteNode = (nodeId: string) => {
    if (!activeTemplate) return
    setTemplates(templates.map(t => t.id === activeTemplate.id
      ? { ...t, nodes: t.nodes.filter(n => n.id !== nodeId), edges: t.edges.filter(e => e.source !== nodeId && e.target !== nodeId) }
      : t
    ))
    setSelectedNodeId(null)
  }

  const addEdge = (source: string, target: string) => {
    if (!activeTemplate) return
    if (activeTemplate.edges.find(e => e.source === source && e.target === target)) return
    const edgeId = `edge_${source}_${target}`
    setTemplates(templates.map(t => t.id === activeTemplate.id
      ? { ...t, edges: [...t.edges, { id: edgeId, source, target }] }
      : t
    ))
  }

  const deleteTemplate = (id: string) => {
    setTemplates(templates.filter(t => t.id !== id))
    if (activeTemplateId === id) {
      setActiveTemplateId(null)
      setTemplateName('')
    }
  }

  const toggleStatus = (id: string) => {
    setTemplates(templates.map(t => t.id === id
      ? { ...t, status: t.status === 'active' ? 'inactive' : 'active' } as FlowTemplate
      : t
    ))
  }

  const selectedNode = activeTemplate?.nodes.find(n => n.id === selectedNodeId) || null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900">审批流程设计器</h3>
        <button
          onClick={createTemplate}
          className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
        >
          <Plus className="h-3.5 w-3.5" /> 新建流程
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="space-y-2 lg:col-span-1">
          {templates.map(tpl => (
            <div key={tpl.id} className={`cursor-pointer rounded-lg border p-3 transition ${activeTemplateId === tpl.id ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-200 hover:border-zinc-400'}`}>
              <div className="flex items-center justify-between" onClick={() => { setActiveTemplateId(tpl.id); setTemplateName(tpl.name); setTemplateDesc(tpl.description || '') }}>
                <div>
                  <div className="text-sm font-medium text-zinc-900">{tpl.name}</div>
                  <div className="text-xs text-zinc-500">{tpl.nodes.length} 个节点 / {tpl.edges.length} 条连线</div>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs ${tpl.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                  {tpl.status === 'active' ? '已启用' : '草稿'}
                </span>
              </div>
              <div className="mt-2 flex gap-1">
                <button onClick={() => toggleStatus(tpl.id)} className="rounded px-2 py-0.5 text-xs text-zinc-500 hover:bg-zinc-100">
                  {tpl.status === 'active' ? '停用' : '启用'}
                </button>
                <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(tpl, null, 2)) }} className="rounded px-2 py-0.5 text-xs text-zinc-500 hover:bg-zinc-100">复制</button>
                <button onClick={() => deleteTemplate(tpl.id)} className="rounded px-2 py-0.5 text-xs text-red-500 hover:bg-red-50">删除</button>
              </div>
            </div>
          ))}
          {templates.length === 0 && (
            <div className="rounded-lg border border-dashed border-zinc-200 p-6 text-center text-xs text-zinc-400">
              点击"新建流程"创建审批流程模板
            </div>
          )}
        </div>

        <div className="space-y-4 lg:col-span-3">
          {activeTemplate ? (
            <>
              <div className="flex items-center gap-3">
                <input
                  value={templateName}
                  onChange={e => {
                    setTemplateName(e.target.value)
                    setTemplates(templates.map(t => t.id === activeTemplate.id ? { ...t, name: e.target.value } : t))
                  }}
                  className="flex-1 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  placeholder="流程名称"
                />
                <input
                  value={templateDesc}
                  onChange={e => {
                    setTemplateDesc(e.target.value)
                    setTemplates(templates.map(t => t.id === activeTemplate.id ? { ...t, description: e.target.value } : t))
                  }}
                  className="flex-1 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  placeholder="流程描述（可选）"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                {NODE_TYPES.filter(t => t.type !== 'start' && t.type !== 'end').map(typeDef => (
                  <button
                    key={typeDef.type}
                    onClick={() => { setEditingNodeType(typeDef.type); setEditingNodeLabel(typeDef.label); setShowNodeEditor(true) }}
                    className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition hover:shadow-sm ${typeDef.color}`}
                  >
                    <Plus className="h-3 w-3" /> {typeDef.label}
                  </button>
                ))}
              </div>

              <FlowCanvas
                nodes={activeTemplate.nodes}
                edges={activeTemplate.edges}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                onMoveNode={updateNodePosition}
                onAddEdge={addEdge}
                onDeleteNode={deleteNode}
              />

              {showNodeEditor && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowNodeEditor(false)}>
                  <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl" onClick={e => e.stopPropagation()}>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-base font-semibold">添加{NODE_TYPES.find(t => t.type === editingNodeType)?.label}</h3>
                      <button onClick={() => setShowNodeEditor(false)} className="rounded p-1 text-zinc-400 hover:bg-zinc-100"><X className="h-4 w-4" /></button>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-zinc-700 mb-1">节点名称</label>
                        <input value={editingNodeLabel} onChange={e => setEditingNodeLabel(e.target.value)}
                          className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" placeholder="输入节点名称" />
                      </div>
                    </div>
                    <div className="mt-4 flex justify-end gap-2">
                      <button onClick={() => setShowNodeEditor(false)} className="rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50">取消</button>
                      <button onClick={addNode} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">添加</button>
                    </div>
                  </div>
                </div>
              )}

              {selectedNode && (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-zinc-700">节点属性</span>
                    <button onClick={() => setSelectedNodeId(null)} className="rounded p-0.5 text-zinc-400 hover:text-zinc-600"><X className="h-3 w-3" /></button>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div><span className="text-zinc-500">ID:</span> <span className="font-mono text-zinc-700">{selectedNode.id}</span></div>
                    <div><span className="text-zinc-500">类型:</span> <span className="text-zinc-700">{NODE_TYPES.find(t => t.type === selectedNode.type)?.label || selectedNode.type}</span></div>
                    <div><span className="text-zinc-500">标签:</span> <span className="text-zinc-700">{selectedNode.label}</span></div>
                    <div><span className="text-zinc-500">位置:</span> <span className="text-zinc-700">({Math.round(selectedNode.x)}, {Math.round(selectedNode.y)})</span></div>
                    {selectedNode.approver_name && <div className="col-span-2"><span className="text-zinc-500">审批人:</span> <span className="text-zinc-700">{selectedNode.approver_name}</span></div>}
                    {selectedNode.condition_field && (
                      <div className="col-span-2">
                        <span className="text-zinc-500">条件:</span>
                        <span className="text-zinc-700"> {selectedNode.condition_field} {selectedNode.condition_operator} {selectedNode.condition_value}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-[400px] items-center justify-center rounded-lg border border-dashed border-zinc-200">
              <div className="text-center text-sm text-zinc-400">
                <div className="mb-2 text-lg">选择或新建一个审批流程模板</div>
                <div>左侧列表中选择已有模板，或点击"新建流程"</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

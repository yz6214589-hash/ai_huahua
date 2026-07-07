import { useState, useCallback, useEffect } from 'react'
import { Card } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Tabs } from '@/components/Tabs'
import { FileText, Edit3, Clock, RotateCcw, Save } from 'lucide-react'
import type { PromptTemplate, PromptVersion } from '@/api/admin'
import { cn } from '@/lib/utils'

const CATEGORY_TABS = [
  { key: 'system', label: '系统提示词' },
  { key: 'rag_report', label: 'RAG研报提示词' },
  { key: 'zoe_signal', label: 'Zoe信号提示词' },
  { key: 'other', label: '其他模板' },
]

// Mock data
const MOCK_PROMPTS: PromptTemplate[] = [
  { id: '1', category: 'system', name: '系统角色设定', content: '你是一个专业的 AI 投资助手，擅长股票分析、市场研究和投资策略制定。你需要基于提供的工具和数据，为用户提供准确、专业的投资建议。', version: 3, variables: [], created_at: '2026-01-10T08:00:00Z', updated_at: '2026-05-15T10:00:00Z' },
  { id: '2', category: 'system', name: '对话开场白', content: '你好！我是你的 AI 投资助手，可以帮你分析股票、查询行情、制定投资策略。请问有什么可以帮你的？', version: 2, variables: [], created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-20T09:00:00Z' },
  { id: '3', category: 'rag_report', name: '研报摘要提示词', content: '请根据以下研报内容，生成一份结构化的摘要，包括：核心观点、关键数据、投资建议和风险提示。\n\n原始研报内容：\n{content}', version: 2, variables: ['content'], created_at: '2026-02-01T08:00:00Z', updated_at: '2026-05-10T14:00:00Z' },
  { id: '4', category: 'rag_report', name: '公司分析提示词', content: '请基于以下数据对公司 {company_name} 进行全面分析：\n1. 财务概况\n2. 业务竞争力\n3. 行业地位\n4. 估值分析\n5. 风险因素', version: 1, variables: ['company_name'], created_at: '2026-03-01T08:00:00Z', updated_at: '2026-03-01T08:00:00Z' },
  { id: '5', category: 'zoe_signal', name: '信号分析提示词', content: '检测到股票 {stock_code} 出现 {signal_type} 信号，请分析以下方面：\n1. 信号强度评估\n2. 历史回测表现\n3. 当前市场环境\n4. 操作建议', version: 1, variables: ['stock_code', 'signal_type'], created_at: '2026-04-01T08:00:00Z', updated_at: '2026-04-01T08:00:00Z' },
  { id: '6', category: 'zoe_signal', name: '风险预警提示词', content: '系统检测到风险信号：\n- 风险类型：{risk_type}\n- 涉及标的：{target}\n- 风险等级：{level}\n\n请生成风险预警说明和应对建议。', version: 2, variables: ['risk_type', 'target', 'level'], created_at: '2026-04-05T08:00:00Z', updated_at: '2026-05-12T11:00:00Z' },
  { id: '7', category: 'other', name: '数据查询提示词', content: '用户请求查询 {query_type} 数据，请根据以下参数生成 SQL 查询语句：\n{tables}\n{conditions}', version: 1, variables: ['query_type', 'tables', 'conditions'], created_at: '2026-05-01T08:00:00Z', updated_at: '2026-05-01T08:00:00Z' },
]

const MOCK_VERSIONS: Record<string, PromptVersion[]> = {
  '1': [
    { version: 3, content: '你是一个专业的 AI 投资助手...（当前版本 v3）', created_at: '2026-05-15T10:00:00Z' },
    { version: 2, content: '你是一个 AI 投资助手，擅长股票分析和市场研究。', created_at: '2026-03-20T09:00:00Z' },
    { version: 1, content: '你是一个 AI 助手。', created_at: '2026-01-10T08:00:00Z' },
  ],
}

interface PromptEditorModalProps {
  open: boolean
  prompt: PromptTemplate | null
  onClose: () => void
  onSave: (id: string, content: string) => void
}

function PromptEditorModal({ open, prompt, onClose, onSave }: PromptEditorModalProps) {
  const [content, setContent] = useState('')

  useEffect(() => {
    if (open && prompt) {
      setContent(prompt.content)
    }
  }, [open, prompt])

  if (!open || !prompt) return null

  const versions = MOCK_VERSIONS[prompt.id] || []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="flex h-[80vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-3">
          <div>
            <h3 className="text-base font-semibold text-zinc-900">{prompt.name}</h3>
            <p className="text-xs text-zinc-500">
              v{prompt.version} | 变量: {prompt.variables.length > 0 ? prompt.variables.join(', ') : '无'}
            </p>
          </div>
          <button onClick={onClose} className="text-sm text-zinc-400 hover:text-zinc-600">关闭</button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="flex-1 resize-none border-0 px-6 py-4 text-sm font-mono leading-relaxed focus:outline-none"
              spellCheck={false}
            />
          </div>

          {versions.length > 0 && (
            <div className="w-64 border-l border-zinc-200 bg-zinc-50 p-4">
              <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-600">
                <Clock className="h-3.5 w-3.5" />
                版本历史
              </div>
              <div className="mt-3 space-y-2">
                {versions.map((v) => (
                  <div
                    key={v.version}
                    className={cn(
                      'rounded-md border p-2.5 text-xs',
                      v.version === prompt.version
                        ? 'border-blue-200 bg-blue-50'
                        : 'border-zinc-200 bg-white'
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-zinc-700">v{v.version}</span>
                      {v.version === prompt.version && (
                        <Badge tone="blue">当前</Badge>
                      )}
                    </div>
                    <div className="mt-1 text-zinc-500">{v.created_at.slice(0, 10)}</div>
                    {v.version !== prompt.version && (
                      <button
                        onClick={() => {
                          setContent(v.content)
                        }}
                        className="mt-1.5 inline-flex items-center gap-1 text-blue-600 hover:text-blue-700"
                      >
                        <RotateCcw className="h-3 w-3" />
                        回滚到此版本
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-zinc-200 px-6 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button size="sm" onClick={() => onSave(prompt.id, content)}>
            <Save className="mr-1 h-3.5 w-3.5" />
            保存
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AdminPrompts() {
  const [items, setItems] = useState<PromptTemplate[]>(MOCK_PROMPTS)
  const [activeTab, setActiveTab] = useState('system')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null)

  const filteredItems = items.filter((item) => item.category === activeTab)

  const handleEdit = useCallback((prompt: PromptTemplate) => {
    setEditingPrompt(prompt)
    setEditorOpen(true)
  }, [])

  const handleSave = useCallback((id: string, content: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, content, version: item.version + 1, updated_at: new Date().toISOString() }
          : item
      )
    )
    setEditorOpen(false)
    setEditingPrompt(null)
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Tabs value={activeTab} onChange={setActiveTab} items={CATEGORY_TABS} />
        <div className="text-sm text-zinc-500">
          共 {filteredItems.length} 个模板
        </div>
      </div>

      {filteredItems.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center justify-center px-4 py-16 text-zinc-400">
            <FileText className="mb-2 h-8 w-8 text-zinc-300" />
            <span className="text-sm">该分类下暂无提示词模板</span>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((prompt) => (
            <Card key={prompt.id}>
              <div className="px-5 py-4">
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold text-zinc-900">{prompt.name}</h4>
                      <Badge tone="zinc">v{prompt.version}</Badge>
                      {prompt.variables.length > 0 && (
                        <span className="text-xs text-zinc-400">
                          变量: {prompt.variables.join(', ')}
                        </span>
                      )}
                    </div>
                    <div className="mt-2">
                      <pre className="max-h-24 overflow-y-auto whitespace-pre-wrap rounded-md bg-zinc-50 p-3 text-xs text-zinc-600 leading-relaxed">
                        {prompt.content}
                      </pre>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-xs text-zinc-400">
                      <span>更新于 {prompt.updated_at.slice(0, 10)}</span>
                    </div>
                  </div>
                  <div className="ml-4 flex shrink-0 items-start gap-1">
                    <button
                      onClick={() => handleEdit(prompt)}
                      className="inline-flex items-center gap-1 rounded px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      编辑
                    </button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <PromptEditorModal
        open={editorOpen}
        prompt={editingPrompt}
        onClose={() => { setEditorOpen(false); setEditingPrompt(null) }}
        onSave={handleSave}
      />
    </div>
  )
}

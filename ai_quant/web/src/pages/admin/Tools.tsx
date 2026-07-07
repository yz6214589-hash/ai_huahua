import { useState, useCallback, useEffect } from 'react'
import { Card } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Search, Wrench, Settings, ToggleLeft, ToggleRight, BookOpen } from 'lucide-react'
import type { ToolItem, ToolDetail } from '@/api/admin'
import { cn } from '@/lib/utils'

const CATEGORY_LABELS: Record<string, string> = {
  data: '数据工具',
  analysis: '分析工具',
  market: '市场工具',
  communication: '通讯工具',
  system: '系统工具',
}

const CATEGORY_OPTIONS = [
  { key: '', label: '全部分类' },
  { key: 'data', label: '数据工具' },
  { key: 'analysis', label: '分析工具' },
  { key: 'market', label: '市场工具' },
  { key: 'communication', label: '通讯工具' },
  { key: 'system', label: '系统工具' },
]

const TYPE_TONES: Record<string, 'blue' | 'amber' | 'default'> = {
  core: 'blue',
  skill: 'amber',
}

const TYPE_LABELS: Record<string, string> = {
  core: '核心工具',
  skill: '技能',
}

// Mock data
const MOCK_TOOLS: ToolItem[] = [
  { name: 'get_stock_price', category: 'data', type: 'core', enabled: true, description: '获取实时股票价格数据' },
  { name: 'get_financials', category: 'data', type: 'core', enabled: true, description: '获取公司财务数据' },
  { name: 'get_market_news', category: 'market', type: 'core', enabled: true, description: '获取市场新闻和公告' },
  { name: 'technical_analysis', category: 'analysis', type: 'core', enabled: true, description: '执行技术指标分析' },
  { name: 'sentiment_analysis', category: 'analysis', type: 'skill', enabled: true, description: '分析市场情绪和舆情' },
  { name: 'risk_assessment', category: 'analysis', type: 'skill', enabled: true, description: '评估投资组合风险' },
  { name: 'send_message', category: 'communication', type: 'core', enabled: true, description: '发送飞书消息通知' },
  { name: 'data_export', category: 'system', type: 'core', enabled: false, description: '导出数据到外部系统' },
  { name: 'report_generator', category: 'system', type: 'skill', enabled: true, description: '自动生成分析报告' },
  { name: 'portfolio_optimizer', category: 'analysis', type: 'skill', enabled: false, description: '投资组合优化建议' },
]

const MOCK_TOOL_DETAILS: Record<string, ToolDetail> = {
  get_stock_price: { name: 'get_stock_price', category: 'data', type: 'core', enabled: true, description: '获取实时股票价格数据', config: { api_url: 'https://api.example.com/stock', cache_ttl: 60, retry_count: 3 } },
  get_financials: { name: 'get_financials', category: 'data', type: 'core', enabled: true, description: '获取公司财务数据', config: { api_url: 'https://api.example.com/financials', cache_ttl: 3600, retry_count: 2 } },
  technical_analysis: { name: 'technical_analysis', category: 'analysis', type: 'core', enabled: true, description: '执行技术指标分析', config: { indicators: ['ma', 'macd', 'rsi', 'bollinger'], default_period: '1y' } },
  send_message: { name: 'send_message', category: 'communication', type: 'core', enabled: true, description: '发送飞书消息通知', config: { webhook_url: '', default_receivers: [] } },
}

interface ConfigModalProps {
  open: boolean
  tool: ToolDetail | null
  onClose: () => void
  onSave: (name: string, config: Record<string, any>) => void
}

function ToolConfigModal({ open, tool, onClose, onSave }: ConfigModalProps) {
  const [configText, setConfigText] = useState('')

  useEffect(() => {
    if (open && tool) {
      setConfigText(JSON.stringify(tool.config, null, 2))
    }
  }, [open, tool])

  if (!open || !tool) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="w-full max-w-xl rounded-lg bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-1 text-base font-semibold text-zinc-900">{tool.name}</h3>
        <p className="mb-4 text-xs text-zinc-500">{tool.description}</p>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600">配置 (JSON)</label>
            <textarea
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-xs font-mono focus:border-zinc-500 focus:outline-none"
              rows={12}
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button
            size="sm"
            onClick={() => {
              try {
                const parsed = JSON.parse(configText)
                onSave(tool.name, parsed)
              } catch {
                alert('JSON 格式无效，请检查')
              }
            }}
          >
            保存配置
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AdminTools() {
  const [items, setItems] = useState<ToolItem[]>(MOCK_TOOLS)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [configOpen, setConfigOpen] = useState(false)
  const [configTool, setConfigTool] = useState<ToolDetail | null>(null)

  const filteredItems = items.filter((item) => {
    const matchSearch = !search || item.name.toLowerCase().includes(search.toLowerCase()) || item.description.toLowerCase().includes(search.toLowerCase())
    const matchCategory = !category || item.category === category
    return matchSearch && matchCategory
  })

  const handleToggle = useCallback((name: string, currentEnabled: boolean) => {
    setItems((prev) =>
      prev.map((item) =>
        item.name === name ? { ...item, enabled: !currentEnabled } : item
      )
    )
  }, [])

  const handleConfigOpen = useCallback((name: string) => {
    const detail = MOCK_TOOL_DETAILS[name]
    if (detail) {
      setConfigTool(detail)
      setConfigOpen(true)
    } else {
      // Fallback: create basic detail from item
      const item = items.find((t) => t.name === name)
      if (item) {
        setConfigTool({ ...item, config: {} })
        setConfigOpen(true)
      }
    }
  }, [items])

  const handleConfigSave = useCallback((name: string, config: Record<string, any>) => {
    setConfigOpen(false)
    setConfigTool(null)
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索工具名称或描述..."
              className="w-56 rounded-md border border-zinc-300 py-1.5 pl-8 pr-3 text-sm focus:border-zinc-500 focus:outline-none"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-zinc-500 focus:outline-none"
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.key} value={opt.key}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="text-sm text-zinc-500">
          共 {filteredItems.length} 个工具/技能
        </div>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 text-left text-xs font-medium text-zinc-500">
                <th className="px-4 py-3">工具名称</th>
                <th className="px-4 py-3">分类</th>
                <th className="px-4 py-3">类型</th>
                <th className="px-4 py-3">描述</th>
                <th className="px-4 py-3">启用状态</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-zinc-400">
                    <Wrench className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
                    暂无匹配的工具或技能
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const catLabel = CATEGORY_LABELS[item.category] || item.category
                  const typeTone = TYPE_TONES[item.type] || 'default'
                  const typeLabel = TYPE_LABELS[item.type] || item.type
                  return (
                    <tr key={item.name} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-medium text-zinc-900">{item.name}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                          {catLabel}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={typeTone}>{typeLabel}</Badge>
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 text-zinc-600">
                        {item.description}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleToggle(item.name, item.enabled)}
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition',
                            item.enabled
                              ? 'bg-green-50 text-green-700 hover:bg-green-100'
                              : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'
                          )}
                        >
                          {item.enabled ? (
                            <><ToggleRight className="h-3.5 w-3.5" /> 已启用</>
                          ) : (
                            <><ToggleLeft className="h-3.5 w-3.5" /> 已停用</>
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleConfigOpen(item.name)}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
                          title="配置"
                        >
                          <Settings className="h-3.5 w-3.5" />
                          配置
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <ToolConfigModal
        open={configOpen}
        tool={configTool}
        onClose={() => { setConfigOpen(false); setConfigTool(null) }}
        onSave={handleConfigSave}
      />
    </div>
  )
}

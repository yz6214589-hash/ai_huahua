import { useEffect, useState } from 'react'
import { postJson, fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { ArrowRight, Play, CheckCircle, XCircle, Clock, AlertTriangle, TrendingUp, Shield, Bot, User, Zap, FileText, ChevronDown, ChevronUp } from 'lucide-react'

type NodeStatus = 'idle' | 'running' | 'success' | 'fail' | 'pending' | 'approved' | 'rejected'

interface WorkflowNode {
  id: string
  name: string
  role: string
  icon: React.ReactNode
  status: NodeStatus
  output?: Record<string, unknown>
  error?: string
  duration?: string
}

interface WorkflowRun {
  id: string
  stock_code: string
  started_at: string
  ended_at?: string
  status: 'running' | 'completed' | 'failed'
  verdict: string
  verdict_reason?: string
}

interface WorkflowDetail {
  run_id: string
  stock_code: string
  capital: number
  nodes: WorkflowNode[]
  messages: { role: string; time: string; content: string }[]
  final_verdict: string
  final_reason?: string
}

const MOCK_NODES: WorkflowNode[] = [
  { id: 'charles', name: 'Charles', role: '投研分析师', icon: <Bot className="h-5 w-5" />, status: 'idle' },
  { id: 'zoe', name: 'Zoe', role: '量化信号引擎', icon: <TrendingUp className="h-5 w-5" />, status: 'idle' },
  { id: 'kris', name: 'Kris', role: '风控官', icon: <Shield className="h-5 w-5" />, status: 'idle' },
  { id: 'human', name: 'Human', role: '人在回路', icon: <User className="h-5 w-5" />, status: 'idle' },
  { id: 'trader', name: 'Trader', role: '执行交易员', icon: <Zap className="h-5 w-5" />, status: 'idle' },
]

const MOCK_RUNS: WorkflowRun[] = [
  { id: 'run-001', stock_code: '600519.SH', started_at: '2026-01-20 09:32:15', status: 'completed', verdict: 'APPROVE', verdict_reason: '全部规则通过' },
  { id: 'run-002', stock_code: '000858.SZ', started_at: '2026-01-20 10:15:43', status: 'completed', verdict: 'WARN', verdict_reason: '单笔金额偏高，缩量50%执行' },
  { id: 'run-003', stock_code: '300750.SZ', started_at: '2026-01-19 14:22:08', status: 'failed', verdict: 'REJECT', verdict_reason: 'ST黑名单拦截' },
  { id: 'run-004', stock_code: '002415.SZ', started_at: '2026-01-19 11:05:30', status: 'completed', verdict: 'APPROVE', verdict_reason: '全部规则通过' },
  { id: 'run-005', stock_code: '600036.SH', started_at: '2026-01-18 13:40:22', status: 'failed', verdict: 'HALT', verdict_reason: '单日亏损熔断触发' },
]

const MOCK_DETAIL: WorkflowDetail = {
  run_id: 'run-001',
  stock_code: '600519.SH',
  capital: 1000000,
  nodes: [
    { id: 'charles', name: 'Charles', role: '投研分析师', icon: <Bot className="h-5 w-5" />, status: 'success', duration: '3.2s', output: { stance: 'bullish', confidence: 0.82, summary: '茅台基本面稳健，春节旺季动销良好，目标价1850元' } },
    { id: 'zoe', name: 'Zoe', role: '量化信号引擎', icon: <TrendingUp className="h-5 w-5" />, status: 'success', duration: '1.8s', output: { direction: 'buy', quantity: 100, price: 1780, strategy: 'MACD金叉', latest_signal: 'golden_cross', backtest_winrate: 0.68 } },
    { id: 'kris', name: 'Kris', role: '风控官', icon: <Shield className="h-5 w-5" />, status: 'approved', duration: '0.5s', output: { decision: 'APPROVE', reason: '单笔金额20万（2%），符合上限；价格偏离0.3%，在5%阈值内；非ST；ATR仓位1.2%，在1%附近；新闻无利空' } },
    { id: 'human', name: 'Human', role: '人在回路', icon: <User className="h-5 w-5" />, status: 'approved', duration: '—', output: { approved: true, note: '人工确认执行' } },
    { id: 'trader', name: 'Trader', role: '执行交易员', icon: <Zap className="h-5 w-5" />, status: 'success', duration: '2.1s', output: { dry_run: false, order_id: 2026012001, submitted_at: '2026-01-20 09:35:22', note: '市价单成交' } },
  ],
  messages: [
    { role: 'charles', time: '09:32:15', content: '开始分析 600519.SH 贵州茅台' },
    { role: 'charles', time: '09:32:18', content: '投研观点生成：看多，置信度82%，目标价1850元' },
    { role: 'zoe', time: '09:32:18', content: '接收投研观点，生成交易信号：买入100股，限价1780元，MACD金叉策略' },
    { role: 'kris', time: '09:32:20', content: '风控审批通过（APPROVE），建议仓位2%' },
    { role: 'human', time: '09:32:21', content: '人工授权确认' },
    { role: 'trader', time: '09:32:23', content: '订单提交成功，订单号2026012001' },
  ],
  final_verdict: 'APPROVE',
  final_reason: '全部风控规则通过，订单已执行',
}

function statusConfig(s: NodeStatus) {
  switch (s) {
    case 'success': case 'approved': return { label: '通过', tone: 'green' as const, icon: <CheckCircle className="h-3.5 w-3.5" /> }
    case 'fail': case 'rejected': return { label: '否决', tone: 'red' as const, icon: <XCircle className="h-3.5 w-3.5" /> }
    case 'running': return { label: '执行中', tone: 'blue' as const, icon: <Clock className="h-3.5 w-3.5 animate-pulse" /> }
    case 'pending': return { label: '等待', tone: 'zinc' as const, icon: <Clock className="h-3.5 w-3.5" /> }
    default: return { label: '空闲', tone: 'zinc' as const, icon: null }
  }
}

function NodeCard({ node, last }: { node: WorkflowNode; last: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = statusConfig(node.status)

  return (
    <div className="flex items-start">
      <div className={cn('flex flex-col items-center', last ? '' : 'pr-3')}>
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-full border-2 transition', {
          'border-green-400 bg-green-50 text-green-600': node.status === 'success' || node.status === 'approved',
          'border-red-400 bg-red-50 text-red-600': node.status === 'fail' || node.status === 'rejected',
          'border-blue-400 bg-blue-50 text-blue-600 animate-pulse': node.status === 'running',
          'border-zinc-300 bg-zinc-50 text-zinc-400': node.status === 'pending' || node.status === 'idle',
        })}>
          {node.icon}
        </div>
        {!last && (
          <div className="mt-1.5 h-8 w-0.5 bg-zinc-200 last:h-0" />
        )}
      </div>
      <div className={cn('min-w-0 flex-1 pb-5', last ? '' : '')}>
        <div className="flex items-center gap-2">
          <span className="font-medium text-zinc-900">{node.name}</span>
          <span className="text-xs text-zinc-400">{node.role}</span>
          {cfg.icon && (
            <Badge tone={cfg.tone}>
              {cfg.icon} {cfg.label}
            </Badge>
          )}
          {node.duration && (
            <span className="text-xs text-zinc-400">{node.duration}</span>
          )}
        </div>
        {node.output && (
          <button onClick={() => setExpanded(!expanded)} className="mt-1 flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-600">
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {expanded ? '收起详情' : '查看输出'}
          </button>
        )}
        {expanded && node.output && (
          <div className="mt-1.5 rounded-lg border border-zinc-100 bg-zinc-50 p-2.5">
            {Object.entries(node.output).map(([k, v]) => (
              <div key={k} className="flex gap-2 text-xs">
                <span className="w-24 flex-shrink-0 text-zinc-400">{k}</span>
                <span className="font-mono text-zinc-700">{String(v)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const tone = verdict === 'APPROVE' ? 'green' : verdict === 'WARN' ? 'amber' : verdict === 'REJECT' ? 'red' : 'zinc'
  return <Badge tone={tone}>{verdict}</Badge>
}

export default function WorkFlowTeam() {
  const [runs, setRuns] = useState<WorkflowRun[]>(MOCK_RUNS)
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [triggerStock, setTriggerStock] = useState('600519.SH')
  const [triggerCapital, setTriggerCapital] = useState('1000000')
  const [triggerQuestion, setTriggerQuestion] = useState('请分析贵州茅台的投资价值')

  const detail = selectedRun ? MOCK_DETAIL : null

  const trigger = async () => {
    if (!triggerStock.trim()) return
    setLoading(true)
    try {
      const body = { stock_code: triggerStock.trim(), capital: Number(triggerCapital) || 1000000, user_question: triggerQuestion }
      await postJson('/api/v1/workflow/team/trigger', body)
      setSelectedRun(null)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-2">
        <Card>
          <CardHeader title="触发新工作流" />
          <CardBody className="space-y-3 text-sm">
            <label className="block">
              <div className="text-xs text-zinc-500">股票代码</div>
              <input value={triggerStock} onChange={(e) => setTriggerStock(e.target.value)} placeholder="600519.SH" className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">可用资金（元）</div>
              <input value={triggerCapital} onChange={(e) => setTriggerCapital(e.target.value)} placeholder="1000000" className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">投资问题</div>
              <textarea value={triggerQuestion} onChange={(e) => setTriggerQuestion(e.target.value)} rows={2} placeholder="请分析贵州茅台的投资价值" className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400 resize-none" />
            </label>
            <button
              onClick={trigger}
              disabled={loading || !triggerStock.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {loading ? <Clock className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {loading ? '执行中…' : '启动工作流'}
            </button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="运行历史" />
          <CardBody className="space-y-1">
            {runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRun(run.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition',
                  selectedRun === run.id ? 'bg-zinc-100' : 'hover:bg-zinc-50'
                )}
              >
                <span className={cn('h-2 w-2 flex-shrink-0 rounded-full', {
                  'bg-green-500': run.status === 'completed',
                  'bg-red-500': run.status === 'failed',
                  'bg-blue-500 animate-pulse': run.status === 'running',
                })} />
                <span className="min-w-0 flex-1 font-mono text-xs text-zinc-700 truncate">{run.stock_code}</span>
                <span className="text-xs text-zinc-400">{run.started_at.split(' ')[1]}</span>
                <VerdictBadge verdict={run.verdict} />
              </button>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="工作流详情"
            subtitle={detail ? `${detail.stock_code} · 运行ID: ${detail.run_id}` : '选择一条记录查看'}
          />
          <CardBody>
            {detail ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 text-xs text-zinc-500">
                  <span>资金: {detail.capital.toLocaleString()}元</span>
                  <span>|</span>
                  <span>最终裁决: <VerdictBadge verdict={detail.final_verdict} /></span>
                  <span>|</span>
                  <span>{detail.final_reason}</span>
                </div>

                <div className="grid grid-cols-1 gap-0 rounded-xl border border-zinc-200 bg-white">
                  {detail.nodes.map((node, i) => (
                    <NodeCard key={node.id} node={node} last={i === detail.nodes.length - 1} />
                  ))}
                </div>

                <div>
                  <div className="mb-2 text-xs font-medium text-zinc-500">执行日志</div>
                  <div className="space-y-1.5 rounded-lg border border-zinc-100 bg-zinc-50 p-3">
                    {detail.messages.map((msg, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className="flex-shrink-0 rounded bg-zinc-200 px-1.5 py-0.5 font-mono text-zinc-500">{msg.time}</span>
                        <span className="rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">{msg.role}</span>
                        <span className="text-zinc-600">{msg.content}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-zinc-400">
                <FileText className="mb-3 h-12 w-12 text-zinc-300" />
                <p className="text-sm">选择一条运行记录查看详情</p>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

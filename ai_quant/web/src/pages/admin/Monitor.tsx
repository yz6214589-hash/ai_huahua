import { useState, useEffect, useCallback } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { RefreshCcw, Activity, MessageCircle, Radio, BarChart3, Terminal } from 'lucide-react'
import type { MonitorStatus, LogEntry } from '@/api/admin'
import { fetchMonitorStatus, fetchLogs } from '@/api/admin'
import { cn } from '@/lib/utils'

const mockStatus: MonitorStatus = {
  service_status: 'running',
  feishu_status: 'connected',
  today_api_calls: 156,
  today_messages: 89,
}

const mockLogs: LogEntry[] = [
  { time: '2026-06-01 10:23:45', level: 'INFO', module: 'server', message: '服务启动成功' },
  { time: '2026-06-01 10:23:46', level: 'INFO', module: 'feishu', message: '飞书连接已建立' },
  { time: '2026-06-01 10:24:01', level: 'INFO', module: 'task', message: '舆情监控任务开始执行' },
  { time: '2026-06-01 10:24:15', level: 'DEBUG', module: 'crawler', message: '成功获取 12 条新闻数据' },
  { time: '2026-06-01 10:24:20', level: 'INFO', module: 'llm', message: '调用通义千问 API 进行舆情分析' },
  { time: '2026-06-01 10:24:35', level: 'WARNING', module: 'llm', message: 'API 响应时间超过 10s' },
  { time: '2026-06-01 10:24:40', level: 'INFO', module: 'task', message: '舆情监控任务执行完成' },
  { time: '2026-06-01 10:25:00', level: 'INFO', module: 'task', message: '首板突破扫描任务开始执行' },
  { time: '2026-06-01 10:25:30', level: 'ERROR', module: 'crawler', message: '获取股票行情数据失败: 连接超时' },
  { time: '2026-06-01 10:25:35', level: 'INFO', module: 'crawler', message: '重试获取股票行情数据' },
  { time: '2026-06-01 10:25:40', level: 'INFO', module: 'task', message: '首板突破扫描任务执行完成' },
]

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'text-green-400',
  DEBUG: 'text-blue-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  TRACE: 'text-zinc-500',
}

const LEVEL_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'INFO', label: 'INFO' },
  { value: 'DEBUG', label: 'DEBUG' },
  { value: 'WARNING', label: 'WARNING' },
  { value: 'ERROR', label: 'ERROR' },
]

export default function AdminMonitor() {
  const [status, setStatus] = useState<MonitorStatus>(mockStatus)
  const [logs, setLogs] = useState<LogEntry[]>(mockLogs)
  const [total, setTotal] = useState(mockLogs.length)
  const [level, setLevel] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchMonitorStatus()
      setStatus(data)
    } catch {
      // 使用 mock 数据
    }
  }, [])

  const loadLogs = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchLogs(level || undefined, page)
      setLogs(data.items)
      setTotal(data.total)
    } catch {
      setLogs(mockLogs)
      setTotal(mockLogs.length)
    } finally {
      setLoading(false)
    }
  }, [level, page])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  useEffect(() => {
    loadLogs()
  }, [loadLogs])

  const handleRefresh = useCallback(() => {
    loadStatus()
    loadLogs()
  }, [loadStatus, loadLogs])

  const statusCards = [
    {
      label: '服务状态',
      value: status.service_status === 'running' ? '运行中' : '已停止',
      icon: Radio,
      color: status.service_status === 'running' ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50',
    },
    {
      label: '飞书连接状态',
      value: status.feishu_status === 'connected' ? '已连接' : '未连接',
      icon: MessageCircle,
      color: status.feishu_status === 'connected' ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50',
    },
    {
      label: '今日 API 调用',
      value: status.today_api_calls,
      icon: BarChart3,
      color: 'text-blue-600 bg-blue-50',
    },
    {
      label: '今日消息处理',
      value: status.today_messages,
      icon: Activity,
      color: 'text-amber-600 bg-amber-50',
    },
  ]

  const filteredLogs = logs

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {statusCards.map((card) => (
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

      <Card>
        <CardHeader
          title="实时日志"
          subtitle={total > 0 ? `共 ${total} 条日志` : ''}
          right={
            <div className="flex items-center gap-2">
              <select
                value={level}
                onChange={(e) => { setLevel(e.target.value); setPage(1) }}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-zinc-500 focus:outline-none"
              >
                {LEVEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
                <RefreshCcw className={cn('mr-1 h-3.5 w-3.5', loading && 'animate-spin')} />
                刷新
              </Button>
            </div>
          }
        />
        <CardBody className="p-0">
          <div className="bg-zinc-900 p-4 font-mono text-xs leading-relaxed">
            <div className="mb-2 flex items-center gap-2 text-zinc-500">
              <Terminal className="h-3.5 w-3.5" />
              <span>~/logs/system.log (实时流)</span>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {filteredLogs.length === 0 ? (
                <div className="py-4 text-center text-zinc-600">暂无日志记录</div>
              ) : (
                filteredLogs.map((entry, i) => (
                  <div key={i} className="flex gap-2 py-0.5">
                    <span className="shrink-0 text-zinc-600">{entry.time}</span>
                    <span className={cn('shrink-0 font-semibold', LEVEL_COLORS[entry.level] || 'text-zinc-300')}>
                      [{entry.level}]
                    </span>
                    <span className="shrink-0 text-zinc-500">{entry.module}:</span>
                    <span className="text-zinc-300">{entry.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

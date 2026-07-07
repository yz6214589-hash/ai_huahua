import { useState, useEffect, useCallback } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { RefreshCcw, Play, FileText, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import type { ScheduledTask, TaskLog } from '@/api/admin'
import { fetchScheduledTasks, runTaskNow, fetchTaskLogs } from '@/api/admin'
import { cn } from '@/lib/utils'

const mockTasks: ScheduledTask[] = [
  {
    id: '1',
    name: '舆情监控(通义千问)',
    task_type: 'sentiment',
    cron_expr: '0 */2 * * *',
    enabled: true,
    last_run_time: '2026-06-01 10:24:40',
    last_run_status: 'success',
    created_at: '2026-05-01 00:00:00',
  },
  {
    id: '2',
    name: '首板突破股票扫描',
    task_type: 'breakout',
    cron_expr: '30 9 * * 1-5',
    enabled: true,
    last_run_time: '2026-06-01 09:30:00',
    last_run_status: 'success',
    created_at: '2026-05-01 00:00:00',
  },
  {
    id: '3',
    name: '飞书推送-舆情日报',
    task_type: 'feishu_sentiment',
    cron_expr: '0 8 * * *',
    enabled: true,
    last_run_time: '2026-06-01 08:00:00',
    last_run_status: 'success',
    created_at: '2026-05-01 00:00:00',
  },
  {
    id: '4',
    name: '飞书推送-首板机会',
    task_type: 'feishu_breakout',
    cron_expr: '0 17 * * 1-5',
    enabled: false,
    last_run_time: '2026-05-31 17:00:00',
    last_run_status: 'failed',
    created_at: '2026-05-01 00:00:00',
  },
]

const mockTaskLogs: Record<string, TaskLog[]> = {
  '1': [
    { id: 'l1', task_id: '1', status: 'success', started_at: '2026-06-01 10:24:01', finished_at: '2026-06-01 10:24:40', result: '完成', error_message: '' },
    { id: 'l2', task_id: '1', status: 'success', started_at: '2026-06-01 08:24:01', finished_at: '2026-06-01 08:24:38', result: '完成', error_message: '' },
  ],
  '2': [
    { id: 'l3', task_id: '2', status: 'success', started_at: '2026-06-01 09:30:00', finished_at: '2026-06-01 09:30:15', result: '发现 3 只首板股票', error_message: '' },
  ],
  '3': [
    { id: 'l4', task_id: '3', status: 'success', started_at: '2026-06-01 08:00:00', finished_at: '2026-06-01 08:00:05', result: '推送成功', error_message: '' },
  ],
  '4': [
    { id: 'l5', task_id: '4', status: 'failed', started_at: '2026-05-31 17:00:00', finished_at: '2026-05-31 17:00:03', result: '', error_message: '飞书消息推送失败: token 过期' },
  ],
}

function cronToHuman(expr: string): string {
  const parts = expr.split(' ')
  if (parts.length !== 5) return expr
  if (expr === '0 */2 * * *') return '每 2 小时'
  if (expr === '30 9 * * 1-5') return '工作日 09:30'
  if (expr === '0 8 * * *') return '每天 08:00'
  if (expr === '0 17 * * 1-5') return '工作日 17:00'
  return expr
}

export default function AdminScheduledJobs() {
  const [tasks, setTasks] = useState<ScheduledTask[]>(mockTasks)
  const [running, setRunning] = useState<Record<string, boolean>>({})
  const [taskLogs, setTaskLogs] = useState<Record<string, TaskLog[]>>(mockTaskLogs)
  const [logModal, setLogModal] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchScheduledTasks()
      setTasks(data)
    } catch {
      // 使用 mock 数据
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleRunNow = useCallback(async (id: string) => {
    setRunning((prev) => ({ ...prev, [id]: true }))
    try {
      await runTaskNow(id)
    } catch {
      // 忽略
    } finally {
      setRunning((prev) => ({ ...prev, [id]: false }))
    }
  }, [])

  const handleViewLogs = useCallback(async (id: string) => {
    setLogModal(id)
    try {
      const data = await fetchTaskLogs(id)
      setTaskLogs((prev) => ({ ...prev, [id]: data }))
    } catch {
      // 使用 mock 数据
    }
  }, [])

  const statusBadge = (status: string) => {
    if (status === 'success') return <Badge variant="success">成功</Badge>
    if (status === 'failed') return <Badge variant="danger">失败</Badge>
    if (status === 'running') return <Badge variant="info">运行中</Badge>
    return <Badge variant="default">未知</Badge>
  }

  const currentLogs = logModal ? taskLogs[logModal] || [] : []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-900">AI 定时任务</h2>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCcw className="mr-1 h-3.5 w-3.5" />
          刷新
        </Button>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 text-left text-xs font-medium text-zinc-500">
                <th className="px-4 py-3">任务名称</th>
                <th className="px-4 py-3">执行频率</th>
                <th className="px-4 py-3">上次执行</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-zinc-400">
                    <Clock className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
                    暂无定时任务
                  </td>
                </tr>
              ) : (
                tasks.map((task) => (
                  <tr key={task.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-zinc-400" />
                        <span className="font-medium text-zinc-900">{task.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-zinc-600">{cronToHuman(task.cron_expr)}</td>
                    <td className="px-4 py-3 text-zinc-500">{task.last_run_time || '--'}</td>
                    <td className="px-4 py-3">{statusBadge(task.last_run_status)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRunNow(task.id)}
                          disabled={running[task.id]}
                        >
                          {running[task.id] ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          <span className="ml-1">立即执行</span>
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleViewLogs(task.id)}>
                          <FileText className="mr-1 h-3.5 w-3.5" />
                          查看日志
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {logModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setLogModal(null)}
        >
          <div
            className="w-full max-w-2xl rounded-lg bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader
              title="任务执行日志"
              right={
                <Button variant="ghost" size="sm" onClick={() => setLogModal(null)}>
                  <XCircle className="h-4 w-4" />
                </Button>
              }
            />
            <CardBody>
              {currentLogs.length === 0 ? (
                <div className="py-6 text-center text-sm text-zinc-400">暂无执行日志</div>
              ) : (
                <div className="space-y-3">
                  {currentLogs.map((log) => (
                    <div key={log.id} className="rounded-md border border-zinc-200 p-3 text-sm">
                      <div className="mb-2 flex items-center gap-2 text-xs text-zinc-500">
                        <span>{log.started_at}</span>
                        <span>-</span>
                        <span>{log.finished_at}</span>
                        <span className="ml-auto">
                          {log.status === 'success' ? (
                            <CheckCircle2 className="inline h-3.5 w-3.5 text-green-500" />
                          ) : (
                            <XCircle className="inline h-3.5 w-3.5 text-red-500" />
                          )}
                        </span>
                      </div>
                      {log.result && <div className="text-zinc-700">结果: {log.result}</div>}
                      {log.error_message && (
                        <div className="mt-1 text-red-600">错误: {log.error_message}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </div>
        </div>
      )}
    </div>
  )
}

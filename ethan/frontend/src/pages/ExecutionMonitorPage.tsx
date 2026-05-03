import { useEffect, useMemo, useRef, useState } from 'react'
import { apiGet, apiPost, API_BASE } from '../lib/api'

type TaskItem = { id: string; symbol: string; strategy: string; status: string }
type WsMsg = Record<string, unknown> & { type?: string }

export default function ExecutionMonitorPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [taskId, setTaskId] = useState('')
  const [events, setEvents] = useState<WsMsg[]>([])
  const [err, setErr] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  async function refreshTasks() {
    setErr(null)
    try {
      const res = await apiGet<{ items: TaskItem[] }>('/api/executions')
      setTasks(res.items)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    refreshTasks()
  }, [])

  const wsUrl = useMemo(() => {
    if (!taskId.trim()) return null
    const http = API_BASE.replace(/^http/, 'ws')
    return `${http}/ws/executions/${taskId.trim()}`
  }, [taskId])

  function connectWs() {
    setErr(null)
    setEvents([])
    if (!wsUrl) return
    try {
      wsRef.current?.close()
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as WsMsg
          setEvents((prev) => [...prev.slice(-300), msg])
        } catch {
          setEvents((prev) => [...prev.slice(-300), { type: 'raw', data: ev.data }])
        }
      }
      ws.onerror = () => setErr('WebSocket 连接失败')
      ws.onclose = () => {}
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  async function stop() {
    if (!taskId.trim()) return
    setErr(null)
    try {
      await apiPost(`/api/executions/${taskId.trim()}/stop`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm font-semibold">执行监控</div>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
            onClick={refreshTasks}
          >
            刷新任务
          </button>
          <button
            type="button"
            className="rounded-xl bg-[#ff4d6d] px-3 py-2 text-sm font-semibold text-white"
            onClick={stop}
            disabled={!taskId.trim()}
          >
            停止执行
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="text-xs text-[#9fb0d0]">任务ID</div>
            <input
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              placeholder="粘贴任务ID，或从右侧选择"
              className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
            />
          </div>
          <div className="flex items-end gap-2">
            <button
              type="button"
              className="w-full rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
              onClick={connectWs}
              disabled={!taskId.trim()}
            >
              连接 WebSocket
            </button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div className="rounded-xl border border-[#1f2c4d] bg-[#0b1530] p-3 lg:col-span-2">
            <div className="text-xs text-[#9fb0d0]">实时事件</div>
            <div className="mt-2 max-h-[420px] overflow-auto text-xs leading-6">
              {events.length ? (
                events.map((e, idx) => (
                  <div key={idx} className="border-b border-[#1f2c4d] py-1">
                    {JSON.stringify(e, null, 0)}
                  </div>
                ))
              ) : (
                <div className="text-[#9fb0d0]">暂无事件</div>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-[#1f2c4d] bg-[#0b1530] p-3">
            <div className="text-xs text-[#9fb0d0]">任务列表</div>
            <div className="mt-2 max-h-[420px] overflow-auto text-xs">
              {tasks.length ? (
                tasks
                  .slice()
                  .reverse()
                  .map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className="mb-2 w-full rounded-xl border border-[#1f2c4d] px-3 py-2 text-left"
                      onClick={() => setTaskId(t.id)}
                    >
                      <div className="font-semibold">{t.symbol}</div>
                      <div className="mt-1 text-[#9fb0d0]">
                        {t.strategy} / {t.status}
                      </div>
                      <div className="mt-1 truncate text-[#9fb0d0]">{t.id}</div>
                    </button>
                  ))
              ) : (
                <div className="text-[#9fb0d0]">暂无任务</div>
              )}
            </div>
          </div>
        </div>

        {err ? <div className="mt-3 text-xs text-[#ff4d6d]">{err}</div> : null}
      </div>
    </div>
  )
}

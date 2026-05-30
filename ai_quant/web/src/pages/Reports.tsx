/**
 * 智能研报页面组件
 * 提供 AI 研报生成任务的创建、管理和查看功能
 * 支持多股票选择、模型选择、RAG 开关和报告查看
 */

import { fetchJson, fetchText, postJson } from '@/api/client'
import type { ReportModel, ReportTask } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Loading } from '@/components/Loading'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { ExternalLink, Plus, RefreshCcw, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// 格式化日期时间字符串，处理 ISO 格式为可读格式
function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  // 如果字符串超过 10 个字符，提取日期时间部分并替换 T 为空格
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

// 根据任务状态返回中文标签
function statusLabel(s: ReportTask['status']) {
  if (s === 'waiting') return '等待'
  if (s === 'running') return '运行中'
  if (s === 'success') return '完成'
  if (s === 'failed') return '失败'
  return s
}

// 状态徽章组件，根据状态显示不同颜色的标签
function StatusBadge({ status }: { status: ReportTask['status'] }) {
  const tone = status === 'success' ? 'green' : status === 'failed' ? 'red' : status === 'running' ? 'amber' : 'zinc'
  return <Badge tone={tone}>{statusLabel(status)}</Badge>
}

// 智能研报主组件
export default function Reports() {
  // 状态定义
  const [model, setModel] = useState<ReportModel>('qwen-max')      // 选择的 AI 模型
  const [useRag, setUseRag] = useState(true)                       // 是否启用 RAG
  const [q, setQ] = useState('')                                  // 任务列表筛选关键词
  const [selectedStocks, setSelectedStocks] = useState<StockSearchItem[]>([]) // 已选择的股票
  const [tasks, setTasks] = useState<ReportTask[]>([])           // 任务列表
  const [createdStart, setCreatedStart] = useState('')            // 创建时间筛选起始
  const [createdEnd, setCreatedEnd] = useState('')                // 创建时间筛选结束
  const [loading, setLoading] = useState(false)                  // 是否正在加载任务列表
  const [err, setErr] = useState<string | null>(null)            // 错误信息
  const [creating, setCreating] = useState(false)                // 是否正在创建任务
  const [retrying, setRetrying] = useState<string | null>(null)  // 正在重试的任务 ID
  const [toastMsg, setToastMsg] = useState<string | null>(null)  // 提示消息
  const [viewerTask, setViewerTask] = useState<ReportTask | null>(null)   // 当前查看的任务
  const [viewerMd, setViewerMd] = useState('')                    // 报告 Markdown 内容
  const [viewerLoading, setViewerLoading] = useState(false)      // 报告是否正在加载

  // 显示提示消息，自动 2.2 秒后消失
  const showToast = useCallback((msg: string) => {
    setToastMsg(msg)
    window.setTimeout(() => setToastMsg(null), 2200)
  }, [])

  // 加载任务列表
  const loadTasks = useCallback(async (opts?: { silent?: boolean }) => {
    setLoading(true)
    if (!opts?.silent) setErr(null)
    try {
      // 构建查询参数
      const params = new URLSearchParams()
      params.set('limit', '50')
      if (q.trim()) params.set('q', q.trim())
      if (createdStart) params.set('created_start', createdStart)
      if (createdEnd) params.set('created_end', createdEnd)
      // 获取任务列表
      const r = await fetchJson<{ tasks: ReportTask[] }>(`/api/v1/reports/tasks?${params.toString()}`)
      setTasks(r.tasks || [])
    } catch (e) {
      if (!opts?.silent) setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [q, createdStart, createdEnd])

  // 组件挂载时加载任务列表，并设置 3 秒轮询刷新
  useEffect(() => {
    loadTasks()
    const timerId = window.setInterval(() => {
      loadTasks({ silent: true })
    }, 3000)
    return () => window.clearInterval(timerId)
  }, [loadTasks])

  // 创建研报任务
  const createTask = useCallback(async () => {
    if (selectedStocks.length === 0) {
      setErr('请选择至少一只股票')
      return
    }
    setCreating(true)
    setErr(null)
    try {
      await postJson<{ task: ReportTask }>('/api/v1/reports/tasks', {
        model,
        stock_codes: selectedStocks.map((s) => s.code),
        use_rag: useRag,
      })
      setSelectedStocks([])
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }, [selectedStocks, model, useRag, loadTasks])

  // 删除任务
  const delTask = useCallback(async (taskId: string) => {
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/v1/reports/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' })
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }, [loadTasks])

  // 重试失败的任务
  const retryTask = useCallback(async (taskId: string) => {
    setErr(null)
    setRetrying(taskId)
    try {
      await fetchJson<{ ok: boolean }>(`/api/v1/reports/tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' })
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setRetrying(null)
    }
  }, [loadTasks])

  // 查看任务生成的报告
  const viewTask = useCallback(async (t: ReportTask) => {
    // 检查任务状态
    if (t.status === 'failed') {
      showToast(`任务失败：${t.error_message || '未知错误'}`)
      return
    }
    if (t.status !== 'success') {
      showToast('任务仍在运行中，请稍后再试')
      return
    }

    // 打开报告查看器并加载内容
    setViewerTask(t)
    setViewerLoading(true)
    setViewerMd('')
    try {
      const md = await fetchText(`/api/v1/reports/tasks/${encodeURIComponent(t.task_id)}/view`)
      setViewerMd(md || '')
    } catch (e) {
      showToast(e instanceof Error ? e.message : String(e))
      setViewerTask(null)
      setViewerMd('')
    } finally {
      setViewerLoading(false)
    }
  }, [showToast])

  // 页面主布局：左侧任务创建区 + 右侧任务列表
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      {/* 顶部提示消息 */}
      {toastMsg ? (
        <div className="fixed left-1/2 top-4 z-50 -translate-x-1/2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow">
          {toastMsg}
        </div>
      ) : null}

      {/* 左侧：任务创建表单 */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="智能研报" />
          <CardBody>
            {/* 错误提示 */}
            {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            {/* AI 模型选择 */}
            <label className="block">
              <div className="text-xs text-zinc-500">模型</div>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value as ReportModel)}
                className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
              >
                <option value="qwen-max">qwen-max</option>
                <option value="deepseek">deepseek</option>
              </select>
            </label>

            {/* RAG 开关 */}
            <label className="mt-3 inline-flex items-center gap-2 text-sm text-zinc-700">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-300"
              />
              启用 RAG
            </label>

            {/* 股票选择器 */}
            <div className="mt-3">
              <div className="text-xs text-zinc-500">选择股票（多选）</div>
              <StockPicker
                mode="multiple"
                value={selectedStocks}
                onChange={(v) => setSelectedStocks((v as StockSearchItem[]) || [])}
                placeholder="搜索股票代码或名称"
                className="mt-1"
              />
            </div>

            {/* 创建任务按钮 */}
            <button
              type="button"
              disabled={creating}
              onClick={createTask}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              创建研报任务
            </button>
          </CardBody>
        </Card>
      </div>

      {/* 右侧：任务列表 */}
      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="任务列表"
            right={
              <button
                onClick={() => loadTasks()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                刷新
              </button>
            }
          />
          <CardBody>
            {/* 筛选条件 */}
            <div className="flex flex-wrap items-end gap-3">
              <label className="block">
                <div className="text-xs text-zinc-500">创建开始</div>
                <input
                  type="date"
                  value={createdStart}
                  onChange={(e) => setCreatedStart(e.target.value)}
                  className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">创建结束</div>
                <input
                  type="date"
                  value={createdEnd}
                  onChange={(e) => setCreatedEnd(e.target.value)}
                  className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
              <label className="block flex-1">
                <div className="text-xs text-zinc-500">股票公司</div>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="输入代码或公司名筛选"
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
            </div>

            {/* 任务表格 */}
            <div className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">创建时间</th>
                    <th className="px-3 py-2">生成时间</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.length === 0 ? (
                    <tr>
                      <td className="px-3 py-6 text-sm text-zinc-500" colSpan={5}>
                        暂无任务
                      </td>
                    </tr>
                  ) : (
                    tasks.map((t) => {
                      const pairs = t.stock_codes.map((c, i) => `${c} ${t.stock_names?.[i] || ''}`.trim())
                      return (
                        <tr key={t.task_id} className="border-t border-zinc-100">
                          <td className="px-3 py-2 text-sm text-zinc-900">{pairs.join('，')}</td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(t.created_at)}</td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(t.finished_at || null)}</td>
                          <td className="px-3 py-2">
                            <StatusBadge status={t.status} />
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2">
                              {/* 查看按钮 */}
                              <button
                                type="button"
                                onClick={() => viewTask(t)}
                                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                查看
                              </button>
                              {/* 失败任务显示重试按钮 */}
                              {t.status === 'failed' ? (
                                <button
                                  type="button"
                                  disabled={retrying === t.task_id}
                                  onClick={() => retryTask(t.task_id)}
                                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
                                >
                                  <RefreshCcw className="h-3.5 w-3.5" />
                                  {retrying === t.task_id ? '重试中...' : '重试'}
                                </button>
                              ) : null}
                              {/* 删除按钮 */}
                              <button
                                type="button"
                                onClick={() => delTask(t.task_id)}
                                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* 报告查看模态框 */}
      {viewerTask ? (
        <div className="fixed inset-0 z-40 bg-black/30 p-4">
          <div className="mx-auto flex h-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow">
            {/* 模态框头部 */}
            <div className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-zinc-900">研报查看</div>
                <div className="mt-0.5 truncate text-xs text-zinc-500">{(viewerTask.stock_codes || []).join('，')}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setViewerTask(null)
                  setViewerMd('')
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
              >
                <X className="h-3.5 w-3.5" />
                关闭
              </button>
            </div>
            {/* 模态框内容：Markdown 渲染 */}
            <div className="flex-1 overflow-auto px-4 py-4">
              {viewerLoading ? (
                <Loading size="sm" className="py-4" />
              ) : (
                <div className="prose prose-zinc max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{viewerMd || ''}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

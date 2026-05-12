/**
 * AI 对话页面组件
 * 提供与 AI 助手进行交互的聊天界面
 * 支持发送消息、接收回复和复制回复内容
 */

import { Card, CardBody, CardHeader } from '@/components/Card'
import { cn } from '@/lib/utils'
import { useMemo, useState } from 'react'
import { postJson } from '@/api/client'

// 消息类型定义，包含用户和助手两种角色
type Msg = {
  id: string                 // 消息唯一标识
  role: 'user' | 'assistant' // 消息发送者角色
  text: string              // 消息内容
}

function formatAssistantText(input: unknown): string {
  if (typeof input === 'string') return input
  if (!input || typeof input !== 'object') return String(input ?? '—')
  const data = input as Record<string, unknown>
  const candidates = ['answer', 'text', 'content', 'message', 'output']
  for (const key of candidates) {
    const v = data[key]
    if (typeof v === 'string' && v.trim()) return v
  }
  if (Array.isArray(data.messages)) {
    const texts = data.messages
      .map((x) => (typeof x === 'string' ? x : typeof x === 'object' && x && typeof (x as any).content === 'string' ? String((x as any).content) : ''))
      .filter((x) => x.trim())
    if (texts.length > 0) return texts.join('\n')
  }
  return JSON.stringify(input, null, 2)
}

// AI 对话主组件
export default function Chat() {
  const [input, setInput] = useState('')      // 用户输入内容
  const [msgs, setMsgs] = useState<Msg[]>([]) // 消息列表
  const [loading, setLoading] = useState(false) // 是否正在等待回复
  const [err, setErr] = useState<string | null>(null) // 错误信息

  // 计算是否可以发送消息：非加载状态且有有效输入
  const canSend = useMemo(() => !loading && input.trim().length > 0, [loading, input])

  // 发送消息处理函数
  const send = async () => {
    const q = input.trim()
    // 验证输入是否为空
    if (!q) {
      setErr('请输入内容')
      return
    }
    setErr(null)
    setLoading(true)
    setInput('')  // 清空输入框

    // 添加用户消息到列表
    const userMsg: Msg = { id: `${Date.now()}-u`, role: 'user', text: q }
    setMsgs((prev) => [...prev, userMsg])

    try {
      // 调用 AI Agent API 获取回复
      const r = await postJson<{ result: unknown }>('/api/agent/run', { input: q })
      // 处理返回结果，优先展示可读文本
      const text = formatAssistantText(r.result)
      // 添加助手回复消息
      const assistantMsg: Msg = { id: `${Date.now()}-a`, role: 'assistant', text: text || '—' }
      setMsgs((prev) => [...prev, assistantMsg])
    } catch (e) {
      // 捕获并显示错误信息
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  // 复制消息内容到剪贴板
  const copy = async (text: string) => {
    setErr(null)
    try {
      await navigator.clipboard.writeText(text)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader title="AI 对话" />
      <CardBody className="space-y-3">
        {/* 错误提示信息 */}
        {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

        {/* 消息列表区域 */}
        <div className="h-[62vh] overflow-auto rounded-lg border border-zinc-200 bg-white p-3">
          {msgs.length === 0 ? (
            // 空状态提示
            <div className="text-sm text-zinc-500">输入问题后发送</div>
          ) : (
            // 消息列表
            <div className="space-y-3">
              {msgs.map((m) => (
                <div key={m.id} className={cn('rounded-lg border px-3 py-2', m.role === 'user' ? 'border-zinc-200 bg-zinc-50' : 'border-amber-200 bg-amber-50')}>
                  {/* 消息头部：角色标签和复制按钮 */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-zinc-500">{m.role === 'user' ? '你' : '助手'}</div>
                    {m.role === 'assistant' ? (
                      <button
                        type="button"
                        onClick={() => copy(m.text)}
                        className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                      >
                        复制
                      </button>
                    ) : null}
                  </div>
                  {/* 消息内容 */}
                  <pre className="mt-2 whitespace-pre-wrap break-words text-sm text-zinc-800">{m.text}</pre>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 输入区域：文本输入框和发送按钮 */}
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题…"
            rows={3}
            className="w-full resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
          />
          <button
            type="button"
            disabled={!canSend}
            onClick={send}
            className="shrink-0 rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            发送
          </button>
        </div>
      </CardBody>
    </Card>
  )
}

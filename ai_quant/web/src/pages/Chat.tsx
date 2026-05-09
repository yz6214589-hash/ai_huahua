import { Card, CardBody, CardHeader } from '@/components/Card'
import { cn } from '@/lib/utils'
import { useMemo, useState } from 'react'
import { postJson } from '@/api/client'

type Msg = {
  id: string
  role: 'user' | 'assistant'
  text: string
}

export default function Chat() {
  const [input, setInput] = useState('')
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const canSend = useMemo(() => !loading && input.trim().length > 0, [loading, input])

  const send = async () => {
    const q = input.trim()
    if (!q) {
      setErr('请输入内容')
      return
    }
    setErr(null)
    setLoading(true)
    setInput('')
    const userMsg: Msg = { id: `${Date.now()}-u`, role: 'user', text: q }
    setMsgs((prev) => [...prev, userMsg])
    try {
      const r = await postJson<{ result: unknown }>('/api/agent/run', { input: q })
      const text = typeof r.result === 'string' ? r.result : JSON.stringify(r.result, null, 2)
      const assistantMsg: Msg = { id: `${Date.now()}-a`, role: 'assistant', text: text || '—' }
      setMsgs((prev) => [...prev, assistantMsg])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

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
        {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

        <div className="h-[62vh] overflow-auto rounded-lg border border-zinc-200 bg-white p-3">
          {msgs.length === 0 ? (
            <div className="text-sm text-zinc-500">输入问题后发送</div>
          ) : (
            <div className="space-y-3">
              {msgs.map((m) => (
                <div key={m.id} className={cn('rounded-lg border px-3 py-2', m.role === 'user' ? 'border-zinc-200 bg-zinc-50' : 'border-amber-200 bg-amber-50')}>
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
                  <pre className="mt-2 whitespace-pre-wrap break-words text-sm text-zinc-800">{m.text}</pre>
                </div>
              ))}
            </div>
          )}
        </div>

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

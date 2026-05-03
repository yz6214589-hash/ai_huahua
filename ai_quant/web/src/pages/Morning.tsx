import { useState } from 'react'
import { postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'

type AgentRunResp = {
  route: { target: string; reason: string }
  result: Record<string, unknown>
}

export default function Morning() {
  const [result, setResult] = useState<AgentRunResp | null>(null)
  const [loading, setLoading] = useState(false)

  const runMorning = async () => {
    setLoading(true)
    try {
      const r = await postJson<AgentRunResp>('/api/agent/run', { input: '请生成今天晨会简报' })
      setResult(r)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader title="晨会简报" />
      <CardBody className="space-y-4">
        <button
          onClick={runMorning}
          disabled={loading}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800 disabled:opacity-60"
        >
          {loading ? '运行中...' : '运行 LangGraph 晨会工作流'}
        </button>
        <pre className="overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
          {result ? JSON.stringify(result, null, 2) : '点击按钮查看运行结果'}
        </pre>
      </CardBody>
    </Card>
  )
}

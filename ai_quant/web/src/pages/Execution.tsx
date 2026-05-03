import { Card, CardBody, CardHeader } from '@/components/Card'
import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'

type ExecutionStatus = {
  source: string
  status: string
  features: string[]
}

export default function Execution() {
  const [data, setData] = useState<ExecutionStatus | null>(null)

  useEffect(() => {
    fetchJson<ExecutionStatus>('/api/execution/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  return (
    <Card>
      <CardHeader title="执行监控" />
      <CardBody className="space-y-2 text-sm text-zinc-700">
        <div>模块来源：{data?.source || 'ethan'}</div>
        <div>状态：{data?.status || 'loading'}</div>
        <div>能力：{(data?.features || []).join(' / ') || '—'}</div>
      </CardBody>
    </Card>
  )
}

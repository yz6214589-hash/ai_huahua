import { Card, CardBody, CardHeader } from '@/components/Card'
import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'

type StrategyStatus = {
  source: string
  status: string
  features: string[]
}

export default function Strategy() {
  const [data, setData] = useState<StrategyStatus | null>(null)

  useEffect(() => {
    fetchJson<StrategyStatus>('/api/analysis/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  return (
    <Card>
      <CardHeader title="策略分析" />
      <CardBody className="space-y-2 text-sm text-zinc-700">
        <div>模块来源：{data?.source || 'zoe'}</div>
        <div>状态：{data?.status || 'loading'}</div>
        <div>能力：{(data?.features || []).join(' / ') || '—'}</div>
      </CardBody>
    </Card>
  )
}

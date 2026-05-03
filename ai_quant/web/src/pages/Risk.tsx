import { Card, CardBody, CardHeader } from '@/components/Card'
import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'

type RiskStatus = {
  source: string
  status: string
  features: string[]
}

export default function Risk() {
  const [data, setData] = useState<RiskStatus | null>(null)

  useEffect(() => {
    fetchJson<RiskStatus>('/api/risk/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  return (
    <Card>
      <CardHeader title="风控中心" />
      <CardBody className="space-y-2 text-sm text-zinc-700">
        <div>模块来源：{data?.source || 'kris'}</div>
        <div>状态：{data?.status || 'loading'}</div>
        <div>能力：{(data?.features || []).join(' / ') || '—'}</div>
      </CardBody>
    </Card>
  )
}

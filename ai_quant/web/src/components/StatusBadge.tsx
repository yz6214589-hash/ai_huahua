import { Badge } from '@/components/Badge'
import type { DataSource, JobStatus } from '@/api/types'

export function JobStatusBadge({ status }: { status: JobStatus }) {
  if (status === 'success') return <Badge tone="green">成功</Badge>
  if (status === 'partial') return <Badge tone="amber">部分完成</Badge>
  if (status === 'failed') return <Badge tone="red">失败</Badge>
  return <Badge tone="blue">运行中</Badge>
}

export function DataSourceBadge({ source }: { source: DataSource }) {
  if (source === 'qmt') return <Badge tone="blue">qmt</Badge>
  if (source === 'tushare') return <Badge tone="amber">tushare</Badge>
  if (source === 'akshare') return <Badge tone="green">akshare</Badge>
  if (source === 'qwen_search') return <Badge tone="amber">qwen_search</Badge>
  if (source === 'file') return <Badge tone="zinc">file</Badge>
  return <Badge tone="zinc">unknown</Badge>
}


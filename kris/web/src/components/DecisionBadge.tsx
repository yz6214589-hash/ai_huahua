import { Badge } from '@/components/Badge'
import type { Decision } from '@/api/types'

export function DecisionBadge({ decision }: { decision: Decision }) {
  if (decision === 'approve') return <Badge tone="green">approve</Badge>
  if (decision === 'warn') return <Badge tone="amber">warn</Badge>
  if (decision === 'reject') return <Badge tone="red">reject</Badge>
  return <Badge tone="zinc">halt</Badge>
}


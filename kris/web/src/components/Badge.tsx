import { cn } from '@/lib/utils'

export function Badge({
  children,
  tone = 'zinc',
}: {
  children: React.ReactNode
  tone?: 'zinc' | 'green' | 'amber' | 'red' | 'blue'
}) {
  const map: Record<string, string> = {
    zinc: 'bg-zinc-100 text-zinc-700 border-zinc-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
  }

  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium', map[tone] || map.zinc)}>
      {children}
    </span>
  )
}


import { cn } from '@/lib/utils'

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('rounded-xl border border-zinc-200 bg-white', className)}>{children}</div>
}

export function CardHeader({ title, subtitle, right }: { title: string; subtitle?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-zinc-900">{title}</div>
        {subtitle && <div className="text-xs text-zinc-400">{subtitle}</div>}
      </div>
      {right}
    </div>
  )
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('px-4 py-4', className)}>{children}</div>
}


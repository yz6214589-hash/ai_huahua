import { cn } from '@/lib/utils'

export function Tabs({
  value,
  onChange,
  items,
}: {
  value: string
  onChange: (v: string) => void
  items: Array<{ key: string; label: string }>
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-lg border border-zinc-200 bg-white p-1">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          onClick={() => onChange(it.key)}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm transition',
            value === it.key ? 'bg-zinc-900 text-white' : 'text-zinc-700 hover:bg-zinc-50'
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}


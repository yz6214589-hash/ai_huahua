/**
 * 统一股票搜索下拉选择组件
 * 支持单选/多选模式，点击搜索按钮后展示全部匹配结果，下拉列表支持滚动加载更多
 */

import { cn } from '@/lib/utils'
import type { StockSearchItem } from '@/api/types'
import { fetchJson } from '@/api/client'
import { Search, ChevronDown, X, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

export interface StockPickerProps {
  value?: StockSearchItem | StockSearchItem[] | null
  onChange?: (val: StockSearchItem | StockSearchItem[] | null) => void
  mode?: 'single' | 'multiple'
  placeholder?: string
  disabled?: boolean
  className?: string
}

const PAGE_SIZE = 20

async function fetchStocksPage(q: string, offset: number): Promise<StockSearchItem[]> {
  const params = new URLSearchParams()
  params.set('limit', String(PAGE_SIZE))
  params.set('offset', String(offset))
  if (q.trim()) params.set('q', q.trim())
  const r = await fetchJson<{ items: StockSearchItem[] }>(`/api/stocks?${params.toString()}`)
  return r.items || []
}

export function StockPicker({
  value,
  onChange,
  mode = 'single',
  placeholder = '搜索股票代码或名称',
  disabled = false,
  className,
}: StockPickerProps) {
  const isMultiple = mode === 'multiple'

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockSearchItem[]>([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const loadingMoreRef = useRef(false)

  const selectedItems: StockSearchItem[] = isMultiple
    ? (Array.isArray(value) ? value : value ? [value] : [])
    : value
      ? [value as StockSearchItem]
      : []

  const selectedCodes = useMemo(() => new Set(selectedItems.map((it) => it.code)), [selectedItems])

  // 处理点击外部关闭下拉框
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !(containerRef.current as HTMLElement).contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    if (open) document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  useEffect(() => {
    if (!sentinelRef.current || !open) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMoreRef.current && !loading) {
          loadMore()
        }
      },
      { root: listRef.current }
    )
    observer.observe(sentinelRef.current)
    return () => observer.disconnect()
  }, [open, hasMore, loading, page])

  const loadPage = useCallback(async (q: string, pageNum: number) => {
    loadingMoreRef.current = true
    setLoading(true)
    setErr(null)
    try {
      const items = await fetchStocksPage(q, pageNum * PAGE_SIZE)
      if (pageNum === 0) {
        setResults(items)
      } else {
        setResults((prev) => {
          const existingCodes = new Set(prev.map((r) => r.code))
          const newItems = items.filter((r) => !existingCodes.has(r.code))
          return [...prev, ...newItems]
        })
      }
      setHasMore(items.length === PAGE_SIZE)
      setPage(pageNum)
    } catch {
      setErr('加载失败')
    } finally {
      setLoading(false)
      loadingMoreRef.current = false
    }
  }, [])

  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current || loading || !hasMore) return
    loadingMoreRef.current = true
    setLoading(true)
    setErr(null)
    try {
      const nextPage = page + 1
      const items = await fetchStocksPage(query, nextPage * PAGE_SIZE)
      setResults((prev) => {
        const existingCodes = new Set(prev.map((r) => r.code))
        const newItems = items.filter((r) => !existingCodes.has(r.code))
        return [...prev, ...newItems]
      })
      setHasMore(items.length === PAGE_SIZE)
      setPage(nextPage)
    } catch {
      setErr('加载失败')
    } finally {
      setLoading(false)
      loadingMoreRef.current = false
    }
  }, [loading, hasMore, page, query, loadPage])

  const handleToggleOpen = useCallback(() => {
    if (disabled) return
    if (!open) {
      setQuery('')
      setResults([])
      setPage(0)
      setHasMore(true)
      setSearched(false)
      loadPage('', 0)
    }
    setOpen((v) => !v)
  }, [disabled, open, loadPage])

  const handleSearch = useCallback(() => {
    setResults([])
    setPage(0)
    setHasMore(true)
    setSearched(true)
    loadPage(query, 0)
  }, [loadPage, query])

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }, [handleSearch])

  const selectItem = useCallback((item: StockSearchItem) => {
    if (isMultiple) {
      if (selectedCodes.has(item.code)) return
      const next = [...selectedItems, item]
      onChange?.(next)
    } else {
      onChange?.(item)
      setOpen(false)
      setQuery('')
      setResults([])
      setPage(0)
      setHasMore(true)
      setSearched(false)
    }
  }, [isMultiple, selectedCodes, selectedItems])

  const removeItem = useCallback((code: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isMultiple) {
      onChange?.(null)
      return
    }
    const next = selectedItems.filter((it) => it.code !== code)
    onChange?.(next)
  }, [isMultiple, selectedItems, onChange])

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <div
        className={cn(
          'flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 cursor-pointer transition',
          disabled ? 'bg-zinc-50 cursor-not-allowed opacity-60' : 'hover:border-zinc-400',
          open ? 'border-zinc-400 ring-1 ring-zinc-400' : ''
        )}
        onClick={handleToggleOpen}
      >
        {selectedItems.length > 0 ? (
          selectedItems.map((it) => (
            <span
              key={it.code}
              className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs"
            >
              <span className="font-semibold text-zinc-900">{it.code}</span>
              {it.name ? <span className="text-zinc-500">{it.name}</span> : null}
              <button
                type="button"
                onClick={(e) => removeItem(it.code, e)}
                className="ml-0.5 text-zinc-400 hover:text-zinc-700"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))
        ) : (
          <span className="text-sm text-zinc-400">{placeholder}</span>
        )}
        <span className="ml-auto">
          <ChevronDown className={cn('h-4 w-4 text-zinc-400 transition-transform', open ? 'rotate-180' : '')} />
        </span>
      </div>

      {open ? (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-zinc-200 bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-zinc-100 p-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-zinc-400" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleInputKeyDown}
                disabled={disabled}
                placeholder="输入股票代码或名称"
                className="w-full rounded-md border border-zinc-200 bg-white py-1.5 pl-8 pr-2 text-sm outline-none transition focus:border-zinc-400 disabled:bg-zinc-50"
              />
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); handleSearch() }}
              disabled={disabled || loading}
              className="inline-flex items-center gap-1 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Search className="h-3.5 w-3.5" />
              搜索
            </button>
          </div>

          <div ref={listRef} className="max-h-64 overflow-auto p-1.5">
            {loading && results.length === 0 ? (
              <div className="px-2 py-3 text-xs text-zinc-500">加载中…</div>
            ) : err && results.length === 0 ? (
              <div className="px-2 py-3 text-xs text-red-600">{err}</div>
            ) : results.length === 0 ? (
              <div className="px-2 py-3 text-xs text-zinc-500">
                {searched ? '无匹配结果' : '暂无数据'}
              </div>
            ) : (
              <div className="space-y-1">
                {results.map((it) => {
                  const selected = selectedCodes.has(it.code)
                  return (
                    <div
                      key={it.code}
                      className={cn(
                        'flex items-center justify-between gap-2 rounded-md px-2 py-2',
                        selected ? 'bg-zinc-50' : 'hover:bg-zinc-50 cursor-pointer'
                      )}
                      onClick={() => !selected && selectItem(it)}
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-zinc-900">{it.code}</div>
                        <div className="truncate text-xs text-zinc-500">{it.name || '—'}</div>
                      </div>
                      {selected ? (
                        <span className="shrink-0 text-xs text-zinc-400">已选</span>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); selectItem(it) }}
                          className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                        >
                          <Plus className="h-3 w-3" />
                          {isMultiple ? '添加' : '选择'}
                        </button>
                      )}
                    </div>
                  )
                })}
                {hasMore && (
                  <div ref={sentinelRef} className="flex items-center justify-center py-2">
                    {loading ? (
                      <span className="text-xs text-zinc-400">加载更多…</span>
                    ) : (
                      <span className="text-xs text-zinc-400">下拉加载更多</span>
                    )}
                  </div>
                )}
                {!hasMore && results.length > 0 && (
                  <div className="py-2 text-center text-xs text-zinc-400">
                    已加载全部 {results.length} 条
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}

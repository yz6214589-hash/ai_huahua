import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import type { DatasetName, PagedRows } from '@/api/types'
import { DATASETS } from '@/features/data/datasets'
import { DatasetPicker } from '@/features/data/DatasetPicker'
import { FiltersPanel } from '@/features/data/FiltersPanel'
import { RowsTable } from '@/features/data/RowsTable'

export default function Data() {
  const [sp, setSp] = useSearchParams()
  const [dataset, setDataset] = useState<DatasetName>((sp.get('dataset') as DatasetName) || 'trade_stock_daily')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [rows, setRows] = useState<PagedRows<Record<string, unknown>> | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const dsDef = useMemo(() => DATASETS.find((d) => d.key === dataset) || null, [dataset])
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!dsDef) {
      setErr('数据集不存在，请从左侧重新选择')
      setFilterValues({})
      return
    }
    const next: Record<string, string> = {}
    for (const f of dsDef.filters) {
      const v = sp.get(f.key)
      if (v) next[f.key] = v
    }
    const stock = sp.get('stock_code')
    if (stock) next.stock_code = stock
    setFilterValues(next)
  }, [dataset])

  const validateDateFilters = (values: Record<string, string>) => {
    if (!dsDef) return { ok: false, message: '数据集不存在，请从左侧重新选择' } as const
    const dateKeys = new Set(dsDef.filters.filter((f) => (f.placeholder || '').includes('YYYY-MM-DD')).map((f) => f.key))
    const dateRe = /^\d{4}-\d{2}-\d{2}$/
    for (const [k, v0] of Object.entries(values)) {
      if (!dateKeys.has(k)) continue
      const v = (v0 || '').trim()
      if (!v) continue
      if (v.includes(',')) {
        const [a, b] = v.split(',', 2).map((x) => x.trim())
        if ((a && !dateRe.test(a)) || (b && !dateRe.test(b))) return { ok: false, message: '日期格式错误，请使用 YYYY-MM-DD,YYYY-MM-DD' } as const
        continue
      }
      if (!dateRe.test(v)) return { ok: false, message: '日期格式错误，请使用 YYYY-MM-DD' } as const
    }
    return { ok: true } as const
  }

  const load = async () => {
    const check = validateDateFilters(filterValues)
    if (!check.ok) {
      setErr(check.message)
      return
    }
    setLoading(true)
    setErr(null)
    try {
      const qs = new URLSearchParams()
      qs.set('page', String(page))
      qs.set('pageSize', String(pageSize))
      for (const [k, v] of Object.entries(filterValues)) {
        if (v.trim()) qs.set(k, v.trim())
      }
      const res = await fetchJson<PagedRows<Record<string, unknown>>>(`/api/data/${dataset}?${qs.toString()}`)
      setRows(res)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      next.set('dataset', dataset)
      for (const [k, v] of Object.entries(filterValues)) {
        if (v.trim()) next.set(k, v.trim())
      }
      return next
    })
  }, [dataset, filterValues])

  useEffect(() => {
    if (!dsDef) return
    load()
  }, [dataset, page, pageSize])

  const exportData = async (format: 'csv' | 'json') => {
    setErr(null)
    try {
      const check = validateDateFilters(filterValues)
      if (!check.ok) {
        setErr(check.message)
        return
      }
      if (rows && typeof rows.total === 'number' && rows.total > 10000) {
        setErr('数据量较大，请先缩小筛选范围后再导出')
        return
      }
      const body = { dataset, format, filters: filterValues, limit: 5000 }
      if (format === 'json') {
        const res = await postJson<unknown>('/api/export', body)
        const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${dataset}_${Date.now()}.json`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        const apiKey = (import.meta as any)?.env?.VITE_AI_QUANT_API_KEY as string | undefined
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(apiKey ? { 'X-API-Key': String(apiKey) } : {}) },
          body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error(await res.text())
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${dataset}_${Date.now()}.csv`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <DatasetPicker
          dataset={dataset}
          datasets={DATASETS}
          onSelect={(d) => {
            setDataset(d)
            setPage(1)
          }}
        />

        <div className="mt-4">
          {dsDef ? (
            <FiltersPanel
              filters={dsDef.filters}
              values={filterValues}
              onChange={setFilterValues}
              onApply={() => {
                setPage(1)
                load()
              }}
              onClear={() => setFilterValues({})}
            />
          ) : null}
        </div>
      </div>

      <div className="lg:col-span-3">
        <RowsTable
          rows={rows}
          loading={loading}
          error={err}
          page={page}
          pageSize={pageSize}
          hasFilters={Object.values(filterValues).some((v) => (v || '').trim())}
          onPageSize={(n) => {
            setPageSize(n)
            setPage(1)
          }}
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => p + 1)}
          onExportCsv={() => exportData('csv')}
          onExportJson={() => exportData('json')}
        />
      </div>
    </div>
  )
}


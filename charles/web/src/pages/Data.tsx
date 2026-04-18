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
  const [pageSize, setPageSize] = useState(50)
  const [rows, setRows] = useState<PagedRows<Record<string, unknown>> | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const dsDef = useMemo(() => DATASETS.find((d) => d.key === dataset)!, [dataset])
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const f of dsDef.filters) {
      const v = sp.get(f.key)
      if (v) next[f.key] = v
    }
    const stock = sp.get('stock_code')
    if (stock) next.stock_code = stock
    setFilterValues(next)
  }, [dataset])

  const load = async () => {
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
    load()
  }, [dataset, page, pageSize])

  const exportData = async (format: 'csv' | 'json') => {
    setErr(null)
    try {
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
        const res = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
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
        </div>
      </div>

      <div className="lg:col-span-3">
        <RowsTable
          rows={rows}
          loading={loading}
          error={err}
          page={page}
          pageSize={pageSize}
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


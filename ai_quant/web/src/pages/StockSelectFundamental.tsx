import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback, useRef } from 'react'
import { postJson, fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Search, Clock, Database, TrendingUp, RefreshCw, Filter, ChevronDown, Plus, Edit3, Trash2, X, Check, Save } from 'lucide-react'
import { useDataStatus } from '@/context/DataStatusContext'

interface StockResult {
  code: string
  name: string
  sector_level1: string
  sector_level2: string
  pe: number
  pb: number
  roe: number
  gross_margin: number
  net_margin: number
  revenue_growth: number
  profit_growth: number
  debt_ratio: number
  org_id?: string
}

interface ExcludedStock {
  code: string
  name: string
  sector_level1: string
  missing_indicators: string[]
  reason: string
}

const SW_INDUSTRIES = [
  '农林牧渔', '基础化工', '钢铁', '有色金属', '电子', '家用电器',
  '食品饮料', '纺织服饰', '轻工制造', '医药生物', '公用事业',
  '交通运输', '房地产', '商贸零售', '社会服务', '银行',
  '非银金融', '综合', '建筑材料', '建筑装饰', '电力设备',
  '机械设备', '国防军工', '计算机', '传媒', '通信',
  '煤炭', '石油石化', '环保', '美容护理', '汽车',
]

const FILTER_CONFIG = [
  { key: 'pe', label: 'PE（市盈率）', unit: '', sliderMin: 0, sliderMax: 500, step: 1, defaultMin: 0, defaultMax: 500 },
  { key: 'pb', label: 'PB（市净率）', unit: '', sliderMin: 0, sliderMax: 20, step: 0.1, defaultMin: 0, defaultMax: 20 },
  { key: 'roe', label: 'ROE', unit: '%', sliderMin: -20, sliderMax: 40, step: 0.5, defaultMin: -20, defaultMax: 40 },
  { key: 'gross_margin', label: '毛利率', unit: '%', sliderMin: -10, sliderMax: 80, step: 0.5, defaultMin: -10, defaultMax: 80 },
  { key: 'net_margin', label: '净利率', unit: '%', sliderMin: -50, sliderMax: 50, step: 0.5, defaultMin: -50, defaultMax: 50 },
  { key: 'revenue_growth', label: '营收增速', unit: '%', sliderMin: -100, sliderMax: 500, step: 1, defaultMin: -100, defaultMax: 500 },
  { key: 'profit_growth', label: '利润增速', unit: '%', sliderMin: -500, sliderMax: 1000, step: 1, defaultMin: -500, defaultMax: 1000 },
  { key: 'debt_ratio', label: '资产负债率', unit: '%', sliderMin: 0, sliderMax: 100, step: 0.5, defaultMin: 0, defaultMax: 100 },
]

const EXCLUDE_TYPE_OPTIONS = [
  { value: 'kcb', label: '科创板' },
  { value: 'cyb', label: '创业板' },
  { value: 'st', label: 'ST股' },
]

/**
 * 将后端返回的原始数据库列名映射为前端 StockResult 格式
 * 后端SQL返回如 stock_code, stock_name, pe_ttm, revenue_growth_yoy 等列名
 * 前端接口期望 code, name, pe, revenue_growth 等简化字段名
 */
function mapRow(row: Record<string, any>): StockResult {
  return {
    code: row.stock_code || '',
    name: row.stock_name || '',
    sector_level1: row.sector_level1 || '',
    sector_level2: row.sector_level2 || '',
    pe: Number(row.pe_ttm) || 0,
    pb: Number(row.pb) || 0,
    roe: Number(row.roe) || 0,
    gross_margin: Number(row.gross_margin) || 0,
    net_margin: Number(row.net_margin) || 0,
    revenue_growth: Number(row.revenue_growth_yoy) || 0,
    profit_growth: Number(row.profit_growth_yoy) || 0,
    debt_ratio: Number(row.debt_ratio) || 0,
    org_id: row.org_id || undefined,
  }
}

function getCninfoUrl(code: string, orgId?: string): string {
  const parts = code.split('.')
  if (parts.length !== 2) return ''
  const stockCode = parts[0]
  const orgParam = orgId ? `orgId=${orgId}&` : ''
  return `https://www.cninfo.com.cn/new/disclosure/stock?${orgParam}stockCode=${stockCode}#financialStatements`
}

interface PresetData {
  id: number
  name: string
  filters: Record<string, { min: number; max: number }>
  disabled_filters: string[]
  disabled_boundaries: Record<string, { min: boolean; max: boolean }>
  exclude_types: string[]
  industries: string[]
  created_at: string
  updated_at: string
}

interface PresetManagerProps {
  filterValues: Record<string, { min: number; max: number }>
  disabledFilters: Set<string>
  disabledBoundaries: Record<string, { min: boolean; max: boolean }>
  excludeTypes: string[]
  selectedIndustries: string[]
  onLoadPreset: (data: PresetData) => void
}

function PresetManager({
  filterValues, disabledFilters, disabledBoundaries, excludeTypes, selectedIndustries, onLoadPreset,
}: PresetManagerProps) {
  const [presets, setPresets] = useState<PresetData[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [showManageModal, setShowManageModal] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const fetchPresets = async () => {
    try {
      const data = await fetchJson<PresetData[]>('/api/v1/stock-select/presets')
      setPresets(data)
    } catch {
      //
    }
  }

  const toggleDropdown = () => {
    if (!showDropdown) {
      fetchPresets()
    }
    setShowDropdown(!showDropdown)
  }

  const openSaveModal = () => {
    const nextNum = presets.length + 1
    setSaveName('预设 ' + nextNum)
    setShowSaveModal(true)
    setShowDropdown(false)
  }

  const handleSave = async () => {
    const name = saveName.trim()
    if (!name || saving) return
    setSaving(true)
    try {
      const filters: Record<string, { min: number; max: number }> = {}
      FILTER_CONFIG.forEach(fc => {
        filters[fc.key] = {
          min: filterValues[fc.key]?.min ?? fc.defaultMin,
          max: filterValues[fc.key]?.max ?? fc.defaultMax,
        }
      })
      await postJson('/api/v1/stock-select/presets', {
        name,
        filters,
        disabled_filters: Array.from(disabledFilters),
        disabled_boundaries: disabledBoundaries,
        exclude_types: excludeTypes,
        industries: selectedIndustries,
      })
      setShowSaveModal(false)
      setSaveName('')
      fetchPresets()
    } catch {
      //
    } finally {
      setSaving(false)
    }
  }

  const handleLoad = (preset: PresetData) => {
    onLoadPreset(preset)
    setShowDropdown(false)
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('确认删除该条件？')) return
    try {
      await fetchJson(`/api/v1/stock-select/presets/${id}`, { method: 'DELETE' } as any)
      fetchPresets()
    } catch {
      //
    }
  }

  const handleUpdateName = async (id: number) => {
    const name = editingName.trim()
    if (!name) return
    try {
      await fetchJson(`/api/v1/stock-select/presets/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ name }),
      } as any)
      setEditingId(null)
      fetchPresets()
    } catch {
      //
    }
  }

  const openManage = () => {
    setShowManageModal(true)
    setShowDropdown(false)
    fetchPresets()
  }

  return (
    <>
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={toggleDropdown}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-medium text-zinc-700 shadow-sm transition-all hover:bg-zinc-50 hover:shadow"
        >
          <Save className="h-3.5 w-3.5" />
          条件管理
          <ChevronDown className={`h-3 w-3 transition-transform ${showDropdown ? 'rotate-180' : ''}`} />
        </button>

        {showDropdown && (
          <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-zinc-200 bg-white py-1 shadow-lg">
            <button
              onClick={openSaveModal}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50"
            >
              <Plus className="h-3.5 w-3.5 text-green-500" />
              保存当前条件
            </button>

            {presets.length > 0 && <div className="my-1 border-t border-zinc-100" />}

            {presets.map(p => (
              <button
                key={p.id}
                onClick={() => handleLoad(p)}
                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
                {p.name}
              </button>
            ))}

            <div className="my-1 border-t border-zinc-100" />

            <button
              onClick={openManage}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-zinc-500 hover:bg-zinc-50"
            >
              <Edit3 className="h-3.5 w-3.5" />
              管理条件
            </button>
          </div>
        )}
      </div>

      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowSaveModal(false)}>
          <div className="w-80 rounded-xl bg-white p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-4 text-sm font-medium text-zinc-800">保存筛选条件</div>
            <input
              type="text"
              value={saveName}
              onChange={e => setSaveName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
              placeholder="输入条件名称"
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-800 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900"
              autoFocus
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowSaveModal(false)}
                className="rounded-lg border border-zinc-200 px-4 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !saveName.trim()}
                className="rounded-lg bg-black px-4 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showManageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowManageModal(false)}>
          <div className="w-96 rounded-xl bg-white p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-800">管理筛选条件</span>
              <button onClick={() => setShowManageModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="h-4 w-4" />
              </button>
            </div>
            {presets.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-400">暂无保存的条件</div>
            ) : (
              <div className="space-y-2">
                {presets.map(p => (
                  <div key={p.id} className="flex items-center gap-2 rounded-lg border border-zinc-100 px-3 py-2.5">
                    {editingId === p.id ? (
                      <>
                        <input
                          type="text"
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleUpdateName(p.id)}
                          className="flex-1 rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-800 focus:border-zinc-900 focus:outline-none"
                          autoFocus
                        />
                        <button onClick={() => handleUpdateName(p.id)} className="text-green-600 hover:text-green-700">
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-zinc-400 hover:text-zinc-600">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="flex-1 text-xs text-zinc-700">{p.name}</span>
                        <button
                          onClick={() => {
                            setEditingId(p.id)
                            setEditingName(p.name)
                          }}
                          className="text-zinc-400 hover:text-blue-500"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => handleDelete(p.id)} className="text-zinc-400 hover:text-red-500">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

function RangeSlider({
  min, max, step,
  valueMin, valueMax,
  onChangeMin, onChangeMax,
  unit = '',
  minDisabled = false,
  maxDisabled = false,
  mode = 'full',
}: {
  min: number; max: number; step: number
  valueMin: number; valueMax: number
  onChangeMin: (v: number) => void
  onChangeMax: (v: number) => void
  unit?: string
  minDisabled?: boolean
  maxDisabled?: boolean
  mode?: 'full' | 'track' | 'input'
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState<'min' | 'max' | null>(null)
  const [inputMin, setInputMin] = useState(String(valueMin))
  const [inputMax, setInputMax] = useState(String(valueMax))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setInputMin(String(valueMin)) }, [valueMin])
  useEffect(() => { setInputMax(String(valueMax)) }, [valueMax])

  const snap = (v: number) => {
    const s = Math.round((v - min) / step)
    return Math.min(max, Math.max(min, min + s * step))
  }

  const pctMin = max === min || minDisabled ? 0 : ((valueMin - min) / (max - min)) * 100
  const pctMax = max === min || maxDisabled ? 100 : ((valueMax - min) / (max - min)) * 100

  useEffect(() => {
    if (!dragging) return
    if ((dragging === 'min' && minDisabled) || (dragging === 'max' && maxDisabled)) {
      setDragging(null)
      return
    }
    const handleMove = (e: MouseEvent) => {
      if (!trackRef.current) return
      const rect = trackRef.current.getBoundingClientRect()
      const pct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
      const val = snap(min + (pct / 100) * (max - min))
      if (dragging === 'min') {
        onChangeMin(Math.min(val, valueMax))
      } else {
        onChangeMax(Math.max(val, valueMin))
      }
    }
    const handleUp = () => setDragging(null)
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [dragging, min, max, step, valueMin, valueMax, onChangeMin, onChangeMax, minDisabled, maxDisabled])

  const handleTrackClick = (e: React.MouseEvent) => {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const pct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
    const val = snap(min + (pct / 100) * (max - min))
    if (minDisabled && maxDisabled) return
    if (minDisabled) {
      onChangeMax(Math.max(val, valueMin))
      return
    }
    if (maxDisabled) {
      onChangeMin(Math.min(val, valueMax))
      return
    }
    const distMin = Math.abs(val - valueMin)
    const distMax = Math.abs(val - valueMax)
    if (distMin <= distMax) {
      onChangeMin(Math.min(val, valueMax))
    } else {
      onChangeMax(Math.max(val, valueMin))
    }
  }

  const validateAndCommit = (raw: string, field: 'min' | 'max') => {
    setError(null)
    const trimmed = raw.trim()
    if (trimmed === '' || trimmed === '-') return
    const num = Number(trimmed)
    if (isNaN(num)) { setError(field === 'min' ? '下限请输入有效数字' : '上限请输入有效数字'); return }
    if (num < min || num > max) { setError(`数值范围: ${min} ~ ${max}`); return }
    if (field === 'min') {
      if (num > valueMax) { setError('下限不能大于上限'); return }
      onChangeMin(snap(num))
    } else {
      if (num < valueMin) { setError('上限不能小于下限'); return }
      onChangeMax(snap(num))
    }
  }

  const handleInputBlur = (field: 'min' | 'max') => {
    if (field === 'min') {
      validateAndCommit(inputMin, 'min')
      setInputMin(String(valueMin))
    } else {
      validateAndCommit(inputMax, 'max')
      setInputMax(String(valueMax))
    }
  }

  const handleInputKeyDown = (e: React.KeyboardEvent, field: 'min' | 'max') => {
    if (e.key === 'Enter') {
      if (field === 'min') { validateAndCommit(inputMin, 'min'); setInputMin(String(valueMin)) }
      else { validateAndCommit(inputMax, 'max'); setInputMax(String(valueMax)) }
    }
  }

  const inputCls = "w-full rounded border border-zinc-200 px-2 py-1 text-xs text-right text-zinc-800 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900"

  return (
    <div className={mode === 'input' ? '' : 'flex-1'}>
      {mode !== 'input' && (
        <div
          ref={trackRef}
          className="relative h-6 cursor-pointer select-none"
          onMouseDown={handleTrackClick}
        >
          <div className="absolute top-1/2 left-0 right-0 h-1.5 -translate-y-1/2 rounded-full bg-zinc-200" />
          {(!minDisabled || !maxDisabled) && (
            <div
              className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-zinc-900"
              style={{ left: `${pctMin}%`, right: `${100 - pctMax}%` }}
            />
          )}
          {!minDisabled && (
            <div
              className="absolute top-1/2 z-10 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-grab rounded-full border-2 border-zinc-900 bg-white shadow-sm active:cursor-grabbing"
              style={{ left: `${pctMin}%` }}
              onMouseDown={(e) => { e.stopPropagation(); setDragging('min') }}
            />
          )}
          {!maxDisabled && (
            <div
              className="absolute top-1/2 z-10 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-grab rounded-full border-2 border-zinc-900 bg-white shadow-sm active:cursor-grabbing"
              style={{ left: `${pctMax}%` }}
              onMouseDown={(e) => { e.stopPropagation(); setDragging('max') }}
            />
          )}
        </div>
      )}
      {mode !== 'track' && (
        <>
          <div className="flex items-center justify-center gap-4 text-xs mt-1.5">
            <div className="flex items-center gap-1">
              <span className="text-zinc-400">下限</span>
              <div className="w-14">
                <input
                  type="text"
                  value={inputMin}
                  onChange={(e) => setInputMin(e.target.value)}
                  onFocus={() => setError(null)}
                  onBlur={() => handleInputBlur('min')}
                  onKeyDown={(e) => handleInputKeyDown(e, 'min')}
                  disabled={minDisabled}
                  className={inputCls + (minDisabled ? ' opacity-40 cursor-not-allowed' : '')}
                />
              </div>
              {unit && <span className="text-zinc-400">{unit}</span>}
            </div>
            <span className="text-zinc-300 select-none">—</span>
            <div className="flex items-center gap-1">
              <span className="text-zinc-400">上限</span>
              <div className="w-14">
                <input
                  type="text"
                  value={inputMax}
                  onChange={(e) => setInputMax(e.target.value)}
                  onFocus={() => setError(null)}
                  onBlur={() => handleInputBlur('max')}
                  onKeyDown={(e) => handleInputKeyDown(e, 'max')}
                  disabled={maxDisabled}
                  className={inputCls + (maxDisabled ? ' opacity-40 cursor-not-allowed' : '')}
                />
              </div>
              {unit && <span className="text-zinc-400">{unit}</span>}
            </div>
          </div>
          {error && <div className="text-[10px] text-red-500 text-center mt-1">{error}</div>}
        </>
      )}
    </div>
  )
}

export default function StockSelectFundamental() {
  const [results, setResults] = useState<StockResult[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [excludedStocks, setExcludedStocks] = useState<ExcludedStock[]>([])
  const [showExcluded, setShowExcluded] = useState(false)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [hasQueried, setHasQueried] = useState(false)
  const [showFilters, setShowFilters] = useState(true)

  // 使用全局数据状态上下文
  const { dataStatus, loading: statusLoading, refresh: refreshDataStatus } = useDataStatus()

  const [selectedIndustries, setSelectedIndustries] = useState<string[]>([])
  const [excludeTypes, setExcludeTypes] = useState<string[]>(['st'])
  const DEFAULT_DISABLED = new Set(['pe', 'pb', 'profit_growth'])
  const [disabledFilters, setDisabledFilters] = useState<Set<string>>(DEFAULT_DISABLED)
  const [disabledBoundaries, setDisabledBoundaries] = useState<Record<string, { min: boolean; max: boolean }>>({})
  const PAGE_SIZE = 50
  const [filterValues, setFilterValues] = useState<Record<string, { min: number; max: number }>>(() => {
    const init: Record<string, { min: number; max: number }> = {}
    FILTER_CONFIG.forEach(fc => {
      if (fc.key === 'roe') {
        init[fc.key] = { min: 15, max: fc.defaultMax }
      } else if (fc.key === 'gross_margin') {
        init[fc.key] = { min: 30, max: fc.defaultMax }
      } else if (fc.key === 'net_margin') {
        init[fc.key] = { min: 10, max: fc.defaultMax }
      } else if (fc.key === 'revenue_growth') {
        init[fc.key] = { min: 10, max: fc.defaultMax }
      } else if (fc.key === 'debt_ratio') {
        init[fc.key] = { min: fc.defaultMin, max: 60 }
      } else {
        init[fc.key] = { min: fc.defaultMin, max: fc.defaultMax }
      }
    })
    return init
  })

  const doQuery = useCallback(async (targetPage?: number) => {
    setLoading(true)
    setHasQueried(true)
    try {
      const currentPage = targetPage ?? page
      const params: Record<string, any> = { page: currentPage, page_size: PAGE_SIZE, include_excluded: true }
      if (selectedIndustries.length > 0) {
        params.industries = selectedIndustries
      }
      if (excludeTypes.length > 0) {
        params.exclude_types = excludeTypes
      }
      for (const [key, val] of Object.entries(filterValues)) {
        if (disabledFilters.has(key)) continue
        const cfg = FILTER_CONFIG.find(fc => fc.key === key)
        if (!cfg) continue
        const boundaries = disabledBoundaries[key] || { min: false, max: false }
        if (val.min !== cfg.defaultMin && !boundaries.min) params[key + '_min'] = val.min
        if (val.max !== cfg.defaultMax && !boundaries.max) params[key + '_max'] = val.max
      }
      const data = await postJson<{ items: Record<string, any>[]; total: number; excluded?: { total: number; items: Record<string, any>[] } }>('/api/v1/stock-select/query', params)
      setResults((data.items || []).map(mapRow))
      setTotalCount(data.total || 0)
      // 解析被剔除的股票数据
      if (data.excluded && data.excluded.items) {
        setExcludedStocks(data.excluded.items.map((row: Record<string, any>) => ({
          code: row.stock_code || '',
          name: row.stock_name || '',
          sector_level1: row.sector_level1 || '',
          missing_indicators: row.missing_indicators || [],
          reason: row.reason || '',
        })))
      } else {
        setExcludedStocks([])
      }
    } catch {
      setResults([])
      setTotalCount(0)
      setExcludedStocks([])
    } finally {
      setLoading(false)
    }
  }, [selectedIndustries, excludeTypes, filterValues, disabledFilters, disabledBoundaries, page])

  const doQueryRef = useRef(doQuery)
  doQueryRef.current = doQuery

  const handleUpdateData = async () => {
    setUpdating(true)
    try {
      await postJson('/api/v1/jobs/run', { domain: 'stock_daily', mode: 'full' })
      await postJson('/api/v1/jobs/run', { domain: 'stock_financial', mode: 'full' })
      
      await refreshDataStatus()
      
      if (hasQueried) {
        doQueryRef.current(page)
      }
    } catch (error) {
      console.error('更新数据失败:', error)
    } finally {
      setUpdating(false)
    }
  }

  const toggleIndustry = (ind: string) => {
    setSelectedIndustries(prev =>
      prev.includes(ind) ? prev.filter(x => x !== ind) : [...prev, ind]
    )
  }

  const toggleDisabled = (key: string) => {
    setDisabledFilters(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const toggleBoundary = (key: string, boundary: 'min' | 'max') => {
    setDisabledBoundaries(prev => {
      const current = prev[key] || { min: false, max: false }
      return {
        ...prev,
        [key]: { ...current, [boundary]: !current[boundary] },
      }
    })
  }

  const updateFilter = (key: string, field: 'min' | 'max', value: number) => {
    setFilterValues(prev => ({
      ...prev,
      [key]: { ...(prev[key] || { min: 0, max: 0 }), [field]: value },
    }))
  }

  const hasFilters = selectedIndustries.length > 0 || Object.entries(filterValues).some(([key, val]) => {
    if (disabledFilters.has(key)) return false
    const cfg = FILTER_CONFIG.find(fc => fc.key === key)
    if (!cfg) return false
    return val.min !== cfg.sliderMin || val.max !== cfg.sliderMax
  })

  const handleLoadPreset = (preset: PresetData) => {
    const fv: Record<string, { min: number; max: number }> = {}
    FILTER_CONFIG.forEach(fc => {
      const saved = preset.filters[fc.key]
      fv[fc.key] = {
        min: saved?.min ?? fc.defaultMin,
        max: saved?.max ?? fc.defaultMax,
      }
    })
    setFilterValues(fv)
    setDisabledFilters(new Set(preset.disabled_filters || []))
    setDisabledBoundaries(preset.disabled_boundaries || {})
    setExcludeTypes(preset.exclude_types || [])
    setSelectedIndustries(preset.industries || [])
    setPage(1)
    setTimeout(() => doQueryRef.current(1), 0)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '暂无数据'
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="space-y-4">
      <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-500" />
          <span className="text-sm font-medium text-zinc-700">行情数据:</span>
          <span className="text-sm text-zinc-600">
            {statusLoading ? (
              <span className="flex items-center gap-1">
                <RefreshCw className="h-3 w-3 animate-spin" />
                加载中...
              </span>
            ) : (
              <>
                {formatDate(dataStatus?.stock_daily?.latest_date)}
                <span className="ml-1 text-xs text-zinc-400">
                  ({dataStatus?.stock_daily?.stock_count ?? 0} 只)
                </span>
              </>
            )}
          </span>
        </div>
        <div className="h-4 w-px bg-zinc-300" />
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-zinc-700">财务数据:</span>
          <span className="text-sm text-zinc-600">
            {statusLoading ? (
              <span className="flex items-center gap-1">
                <RefreshCw className="h-3 w-3 animate-spin" />
                加载中...
              </span>
            ) : (
              <>
                {formatDate(dataStatus?.stock_financial?.latest_date)}
                <span className="ml-1 text-xs text-zinc-400">
                  ({dataStatus?.stock_financial?.stock_count ?? 0} 只)
                </span>
              </>
            )}
          </span>
        </div>
        <div className="h-4 w-px bg-zinc-300" />
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-zinc-400" />
          <span className="text-xs text-zinc-400">
            {statusLoading ? '加载中...' : `更新于 ${dataStatus?.timestamp ? new Date(dataStatus.timestamp).toLocaleTimeString('zh-CN') : ''}`}
          </span>
        </div>
        <div className="ml-auto">
          <button
            onClick={handleUpdateData}
            disabled={updating}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 shadow-sm transition-all hover:bg-zinc-50 hover:shadow disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${updating ? 'animate-spin' : ''}`} />
            {updating ? '更新中...' : '一键更新数据'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-600">筛选条件</span>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="text-xs text-zinc-500 hover:text-zinc-900"
          >
            {showFilters ? '收起' : '展开'}
          </button>
          {hasFilters && (
            <button
              onClick={() => {
                setSelectedIndustries([])
                setExcludeTypes(['st'])
                setDisabledFilters(DEFAULT_DISABLED)
                setDisabledBoundaries({})
                const init: Record<string, { min: number; max: number }> = {}
                FILTER_CONFIG.forEach(fc => {
                  if (fc.key === 'roe') {
                    init[fc.key] = { min: 15, max: fc.defaultMax }
                  } else if (fc.key === 'gross_margin') {
                    init[fc.key] = { min: 30, max: fc.defaultMax }
                  } else if (fc.key === 'net_margin') {
                    init[fc.key] = { min: 10, max: fc.defaultMax }
                  } else if (fc.key === 'revenue_growth') {
                    init[fc.key] = { min: 10, max: fc.defaultMax }
                  } else if (fc.key === 'debt_ratio') {
                    init[fc.key] = { min: fc.defaultMin, max: 60 }
                  } else {
                    init[fc.key] = { min: fc.defaultMin, max: fc.defaultMax }
                  }
                })
                setFilterValues(init)
              }}
              className="text-xs text-red-500 hover:text-red-600"
            >
              清除筛选
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => doQuery(page)}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-all hover:bg-zinc-800 hover:shadow-lg active:scale-[0.97] disabled:opacity-50"
          >
            <Search className="h-4 w-4" />
            查询
          </button>
          <PresetManager
            filterValues={filterValues}
            disabledFilters={disabledFilters}
            disabledBoundaries={disabledBoundaries}
            excludeTypes={excludeTypes}
            selectedIndustries={selectedIndustries}
            onLoadPreset={handleLoadPreset}
          />
          <span className="text-sm text-zinc-500">结果：<span className="font-semibold text-zinc-900">{totalCount}</span> 只</span>
        </div>
      </div>

      {showFilters && (
        <Card>
          <CardBody>
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-700">
                <Filter className="h-3.5 w-3.5" />
                排查股票类型
              </div>
              <div className="flex flex-wrap gap-4">
                {EXCLUDE_TYPE_OPTIONS.map(opt => {
                  const checked = excludeTypes.includes(opt.value)
                  return (
                    <label key={opt.value} className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setExcludeTypes(prev =>
                            checked ? prev.filter(v => v !== opt.value) : [...prev, opt.value]
                          )
                        }}
                        className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                      />
                      <span className="text-xs text-zinc-600">{opt.label}</span>
                    </label>
                  )
                })}
              </div>
            </div>
            <div className="mb-4">
              <div className="mb-2 text-xs font-medium text-zinc-700">申万一级行业</div>
              <div className="flex flex-wrap gap-1.5">
                {SW_INDUSTRIES.map(ind => {
                  const sel = selectedIndustries.includes(ind)
                  return (
                    <button
                      key={ind}
                      onClick={() => toggleIndustry(ind)}
                      className={`rounded-md border px-2.5 py-1 text-xs transition ${
                        sel
                          ? 'border-zinc-900 bg-zinc-900 text-white'
                          : 'border-zinc-200 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50'
                      }`}
                    >
                      {ind}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {FILTER_CONFIG.map(fc => {
                const disabled = disabledFilters.has(fc.key)
                const boundaries = disabledBoundaries[fc.key] || { min: false, max: false }
                return (
                  <div
                    key={fc.key}
                    onDoubleClick={() => toggleDisabled(fc.key)}
                    className={`rounded-lg border p-3 cursor-pointer select-none transition ${
                      disabled
                        ? 'border-zinc-200 bg-zinc-100 opacity-50'
                        : 'border-zinc-100 bg-zinc-50'
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span className={`text-xs font-medium ${disabled ? 'text-zinc-400' : 'text-zinc-700'}`}>
                        {disabled ? `${fc.label}(已禁用)` : fc.label}
                      </span>
                      {disabled && <span className="text-[10px] text-zinc-400">双击启用</span>}
                    </div>
                    {!disabled && (
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <label className="flex items-center cursor-pointer" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={!boundaries.min}
                              onChange={() => toggleBoundary(fc.key, 'min')}
                              className="h-3.5 w-3.5 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                            />
                          </label>
                          <RangeSlider
                            min={fc.sliderMin}
                            max={fc.sliderMax}
                            step={fc.step}
                            valueMin={filterValues[fc.key]?.min ?? fc.defaultMin}
                            valueMax={filterValues[fc.key]?.max ?? fc.defaultMax}
                            onChangeMin={(v) => updateFilter(fc.key, 'min', v)}
                            onChangeMax={(v) => updateFilter(fc.key, 'max', v)}
                            minDisabled={disabled || boundaries.min}
                            maxDisabled={disabled || boundaries.max}
                            mode="track"
                          />
                          <label className="flex items-center cursor-pointer" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={!boundaries.max}
                              onChange={() => toggleBoundary(fc.key, 'max')}
                              className="h-3.5 w-3.5 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                            />
                          </label>
                        </div>
                        <RangeSlider
                          min={fc.sliderMin}
                          max={fc.sliderMax}
                          step={fc.step}
                          valueMin={filterValues[fc.key]?.min ?? fc.defaultMin}
                          valueMax={filterValues[fc.key]?.max ?? fc.defaultMax}
                          onChangeMin={(v) => updateFilter(fc.key, 'min', v)}
                          onChangeMax={(v) => updateFilter(fc.key, 'max', v)}
                          unit={fc.unit}
                          minDisabled={disabled || boundaries.min}
                          maxDisabled={disabled || boundaries.max}
                          mode="input"
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">
            {hasQueried ? `选股结果（${totalCount} 只）` : '选股结果'}
          </h3>
        </CardHeader>
        <CardBody className="p-0">
          {loading ? (
            <Loading className="py-12" />
          ) : !hasQueried ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">
              请点击「查询」按钮开始筛选
            </div>
          ) : results.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无符合条件的股票，请调整筛选条件</div>
          ) : (
            <>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 z-10 bg-zinc-50 text-xs text-zinc-500 shadow-[0_1px_0_0_rgba(0,0,0,0.05)]">
                    <tr>
                      <th className="px-3 py-2">股票</th>
                      <th className="px-3 py-2">一级行业</th>
                      <th className="px-3 py-2">二级行业</th>
                      <th className="px-3 py-2 text-right">PE（市盈率）</th>
                      <th className="px-3 py-2 text-right">PB（市净率）</th>
                      <th className="px-3 py-2 text-right">ROE(%)</th>
                      <th className="px-3 py-2 text-right">毛利率(%)</th>
                      <th className="px-3 py-2 text-right">净利率(%)</th>
                      <th className="px-3 py-2 text-right">营收增(%)</th>
                      <th className="px-3 py-2 text-right">利润增(%)</th>
                      <th className="px-3 py-2 text-right">资产负债率(%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((s, idx) => {
                      return (
                        <tr key={`${s.code}-${idx}`} className="border-t border-zinc-100 hover:bg-zinc-50">
                          <td className="px-3 py-2">
                            <a
                              href={getCninfoUrl(s.code, s.org_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                            >
                              {s.code}
                            </a>
                            <div className="text-xs text-zinc-500">{s.name}</div>
                          </td>
                          <td className="px-3 py-2"><Badge variant="default">{s.sector_level1 || '--'}</Badge></td>
                          <td className="px-3 py-2"><span className="text-xs text-zinc-500">{s.sector_level2 || '--'}</span></td>
                          <td className="px-3 py-2 text-right text-zinc-700">{s.pe < 0 ? '亏损' : s.pe.toFixed(1)}</td>
                          <td className="px-3 py-2 text-right text-zinc-700">{s.pb.toFixed(2)}</td>
                          <td className={`px-3 py-2 text-right ${s.roe >= 15 ? 'text-green-600 font-medium' : 'text-zinc-700'}`}>{s.roe.toFixed(1)}</td>
                          <td className="px-3 py-2 text-right text-zinc-700">{s.gross_margin.toFixed(1)}</td>
                          <td className={`px-3 py-2 text-right ${s.net_margin >= 20 ? 'text-green-600 font-medium' : 'text-zinc-700'}`}>{s.net_margin.toFixed(1)}</td>
                          <td className={`px-3 py-2 text-right ${s.revenue_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.revenue_growth > 0 ? '+' : ''}{s.revenue_growth.toFixed(1)}</td>
                          <td className={`px-3 py-2 text-right ${s.profit_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.profit_growth > 0 ? '+' : ''}{s.profit_growth.toFixed(1)}</td>
                          <td className={`px-3 py-2 text-right ${s.debt_ratio > 70 ? 'text-amber-600' : 'text-zinc-700'}`}>{s.debt_ratio.toFixed(1)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
                <span className="text-xs text-zinc-400">
                  第 {page} / {Math.max(1, Math.ceil(totalCount / PAGE_SIZE))} 页（共 {totalCount} 只）
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const next = page - 1
                      setPage(next)
                      doQueryRef.current(next)
                    }}
                    disabled={page <= 1 || loading}
                    className="rounded-md border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => {
                      const next = page + 1
                      setPage(next)
                      doQueryRef.current(next)
                    }}
                    disabled={page >= Math.ceil(totalCount / PAGE_SIZE) || loading}
                    className="rounded-md border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </>
          )}

          {/* 所选指标缺失的股票列表（默认折叠） */}
          {hasQueried && excludedStocks.length > 0 && (
            <div className="border-t border-zinc-200">
              <button
                onClick={() => setShowExcluded(!showExcluded)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-zinc-50 transition-colors"
              >
                <span className="text-sm font-medium text-zinc-600">
                  所选指标缺失的股票列表（{excludedStocks.length} 只）
                </span>
                <svg
                  className={`h-4 w-4 text-zinc-400 transition-transform ${showExcluded ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showExcluded && (
                <div className="overflow-auto border-t border-zinc-100">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-zinc-50 text-xs text-zinc-500">
                      <tr>
                        <th className="px-3 py-2">股票代码</th>
                        <th className="px-3 py-2">股票名称</th>
                        <th className="px-3 py-2">一级行业</th>
                        <th className="px-3 py-2">缺失指标</th>
                        <th className="px-3 py-2">剔除原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {excludedStocks.map((s, idx) => (
                        <tr key={`${s.code}-${idx}`} className="border-t border-zinc-100 hover:bg-zinc-50">
                          <td className="px-3 py-2 text-sm text-zinc-700">{s.code}</td>
                          <td className="px-3 py-2 text-sm text-zinc-700">{s.name || '--'}</td>
                          <td className="px-3 py-2"><span className="text-xs text-zinc-500">{s.sector_level1 || '--'}</span></td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {s.missing_indicators.map((ind, i) => (
                                <span key={i} className="inline-block rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-600 border border-red-200">
                                  {ind}
                                </span>
                              ))}
                              {s.missing_indicators.length === 0 && (
                                <span className="text-xs text-zinc-400">-</span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-xs text-zinc-500">{s.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

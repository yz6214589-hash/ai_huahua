import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody } from '@/components/Card'
import { ChevronDown, ChevronUp, Maximize2, RefreshCcw } from 'lucide-react'

/** 财经热点接口返回数据结构 */
interface FinancialHotData {
  updated_at: string
  events: Array<{
    event_date: string
    event_time: string
    country: string
    category: string
    title: string
    importance: string
    previous_value: string
    forecast_value: string
    actual_value: string
    source: string
    url: string
  }>
  news: Array<{
    stock_code: string
    stock_name: string
    title: string
    source: string
    published_at: string
    url: string
  }>
}

/** 格式化日期字符串 */
function fmtDate(v: string) {
  if (!v || v === '—') return '—'
  const s = String(v)
  return s.length > 16 ? s.slice(0, 16).replace('T', ' ') : s
}

/** 每页显示条数 */
const PAGE_SIZE = 10

/** 内联分页器组件 */
function Pager({
  current,
  total,
  onPrev,
  onNext,
}: {
  current: number
  total: number
  onPrev: () => void
  onNext: () => void
}) {
  return (
    <div className="flex items-center justify-center gap-3 py-2 text-xs text-zinc-500">
      <button
        onClick={onPrev}
        disabled={current <= 1}
        className="rounded border border-zinc-200 px-2 py-1 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        上一页
      </button>
      <span>
        {current} / {total || 1}
      </span>
      <button
        onClick={onNext}
        disabled={current >= total}
        className="rounded border border-zinc-200 px-2 py-1 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        下一页
      </button>
    </div>
  )
}

/** 重要性标签 */
function ImportanceBadge({ importance }: { importance: string }) {
  const tone = importance === '高' ? 'bg-red-100 text-red-700' : importance === '低' ? 'bg-zinc-100 text-zinc-600' : 'bg-amber-100 text-amber-700'
  return <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${tone}`}>{importance}</span>
}

/** 财经热点事件行组件 */
function EventRow({ item }: { item: FinancialHotData['events'][number] }) {
  const handleDoubleClick = () => {
    if (item.url) window.open(item.url, '_blank')
  }

  return (
    <div
      className="flex items-center justify-between gap-3 px-4 py-2.5 cursor-default"
      onDoubleClick={handleDoubleClick}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <ImportanceBadge importance={item.importance} />
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 cursor-pointer truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {item.title}
            </a>
          ) : (
            <span className="text-zinc-900 truncate">{item.title}</span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <span>{item.event_date}</span>
          {item.event_time && <span>{item.event_time}</span>}
          <span>{item.country}</span>
          {item.previous_value && <span>前值: {item.previous_value}</span>}
          {item.forecast_value && <span>预期: {item.forecast_value}</span>}
          {item.actual_value && <span>实际: {item.actual_value}</span>}
          {item.source && item.source !== '—' && <span>{item.source}</span>}
        </div>
      </div>
      <button
        onClick={() => { if (item.url) window.open(item.url, '_blank') }}
        disabled={!item.url}
        className="shrink-0 rounded border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-30"
      >
        查看
      </button>
    </div>
  )
}

/** 自选股新闻行组件 */
function NewsRow({ item }: { item: FinancialHotData['news'][number] }) {
  const handleDoubleClick = () => {
    if (item.url) window.open(item.url, '_blank')
  }

  return (
    <div
      className="flex items-center justify-between gap-3 px-4 py-2.5 cursor-default"
      onDoubleClick={handleDoubleClick}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 cursor-pointer"
              onClick={(e) => e.stopPropagation()}
            >
              {item.title}
            </a>
          ) : (
            <span className="text-zinc-900">{item.title}</span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          {item.stock_code && <span className="font-medium text-zinc-700">{item.stock_code}</span>}
          {item.stock_name && <span>{item.stock_name}</span>}
          {item.source && <span>{item.source}</span>}
          <span>{fmtDate(item.published_at)}</span>
        </div>
      </div>
      <button
        onClick={() => { if (item.url) window.open(item.url, '_blank') }}
        disabled={!item.url}
        className="shrink-0 rounded border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-30"
      >
        查看
      </button>
    </div>
  )
}

/** 分隔线组件：包含向上箭头、恢复布局按钮、向下箭头 */
function DividerBar({
  topCollapsed,
  bottomCollapsed,
  onCollapseTop,
  onCollapseBottom,
  onRestore,
}: {
  topCollapsed: boolean
  bottomCollapsed: boolean
  onCollapseTop: () => void
  onCollapseBottom: () => void
  onRestore: () => void
}) {
  return (
    <div className="group relative flex items-center justify-center py-1">
      <div className="absolute inset-x-0 top-1/2 h-px bg-zinc-200" />
      <div className="relative z-10 flex items-center gap-1 rounded-full border border-zinc-200 bg-white px-1.5 py-0.5 shadow-sm">
        <button
          onClick={onCollapseTop}
          disabled={topCollapsed}
          title="折叠财经热点"
          className="flex items-center justify-center rounded-full p-1 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onRestore}
          disabled={!topCollapsed && !bottomCollapsed}
          title="恢复初始布局"
          className="flex items-center justify-center rounded-full p-1 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onCollapseBottom}
          disabled={bottomCollapsed}
          title="折叠自选股新闻"
          className="flex items-center justify-center rounded-full p-1 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

export default function FinancialHot() {
  const [data, setData] = useState<FinancialHotData | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  /* 分页状态 */
  const [eventPage, setEventPage] = useState(1)
  const [newsPage, setNewsPage] = useState(1)

  /* 自选股筛选状态 */
  const [newsFilter, setNewsFilter] = useState('全部')

  /* 折叠状态 */
  const [topCollapsed, setTopCollapsed] = useState(false)
  const [bottomCollapsed, setBottomCollapsed] = useState(false)
  const topRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<FinancialHotData>('/api/v1/financial-hot')
      setData(r)
      /* 数据刷新后重置页码 */
      setEventPage(1)
      setNewsPage(1)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  /* 自选股下拉选项：从 news 数据中提取不重复的股票 */
  const stockOptions = useMemo(() => {
    if (!data?.news) return ['全部']
    const seen = new Set<string>()
    const opts: string[] = ['全部']
    for (const n of data.news) {
      const label = n.stock_code && n.stock_name ? `${n.stock_code} ${n.stock_name}` : n.stock_code
      if (label && !seen.has(label)) {
        seen.add(label)
        opts.push(label)
      }
    }
    return opts
  }, [data?.news])

  /* 按自选股筛选后的 news */
  const filteredNews = useMemo(() => {
    if (!data?.news) return []
    if (newsFilter === '全部') return data.news
    const code = newsFilter.split(' ')[0]
    return data.news.filter((n) => n.stock_code === code)
  }, [data?.news, newsFilter])

  /* 计算分页数据切片 */
  const eventTotal = Math.max(1, Math.ceil((data?.events?.length || 0) / PAGE_SIZE))
  const newsTotal = Math.max(1, Math.ceil((filteredNews.length) / PAGE_SIZE))

  const pagedEvents = useMemo(() => {
    if (!data?.events) return []
    const start = (eventPage - 1) * PAGE_SIZE
    return data.events.slice(start, start + PAGE_SIZE)
  }, [data?.events, eventPage])

  const pagedNews = useMemo(() => {
    if (!filteredNews) return []
    const start = (newsPage - 1) * PAGE_SIZE
    return filteredNews.slice(start, start + PAGE_SIZE)
  }, [filteredNews, newsPage])

  return (
    <div className="flex h-[calc(100vh-120px)] flex-col gap-4">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">
          {data?.updated_at ? `最近更新时间：${data.updated_at}` : '财经热点'}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {loading ? '更新中...' : '更新'}
        </button>
      </div>

      {/* 请求失败提示 */}
      {err ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          请求失败：{err}
          <button onClick={load} className="ml-2 text-red-600 underline hover:text-red-800">重试</button>
        </div>
      ) : null}

      {/* 加载中且无数据时显示骨架 */}
      {loading && !data ? (
        <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">正在加载数据...</div>
      ) : !data ? (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-12 text-center text-sm text-zinc-500">暂无热点数据</div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          {/* 今日财经热点 - 市场宏观事件 */}
          <div
            ref={topRef}
            className="transition-all duration-300 ease-in-out"
            style={{
              flex: topCollapsed ? '0 0 0px' : '1 1 0%',
              overflow: 'hidden',
              minHeight: 0,
              opacity: topCollapsed ? 0 : 1,
            }}
          >
            <Card className="flex h-full min-h-0 flex-col">
              <div className="px-4 py-3">
                <span className="text-sm font-semibold text-zinc-800">
                  今日财经热点（{data?.events?.length || 0} 条）
                </span>
              </div>
              <CardBody className="flex min-h-0 flex-1 flex-col p-0">
                {!data?.events || data.events.length === 0 ? (
                  <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">今日暂无财经热点</div>
                ) : (
                  <>
                    <div className="min-h-0 flex-1 divide-y divide-zinc-100 overflow-y-auto">
                      {pagedEvents.map((e, i) => (
                        <EventRow key={i} item={e} />
                      ))}
                    </div>
                    <Pager
                      current={eventPage}
                      total={eventTotal}
                      onPrev={() => setEventPage((p) => Math.max(1, p - 1))}
                      onNext={() => setEventPage((p) => Math.min(eventTotal, p + 1))}
                    />
                  </>
                )}
              </CardBody>
            </Card>
          </div>

          {/* 分隔线 */}
          <DividerBar
            topCollapsed={topCollapsed}
            bottomCollapsed={bottomCollapsed}
            onCollapseTop={() => { setTopCollapsed(true); setBottomCollapsed(false) }}
            onCollapseBottom={() => { setBottomCollapsed(true); setTopCollapsed(false) }}
            onRestore={() => { setTopCollapsed(false); setBottomCollapsed(false) }}
          />

          {/* 近期自选股重要新闻 */}
          <div
            ref={bottomRef}
            className="transition-all duration-300 ease-in-out"
            style={{
              flex: bottomCollapsed ? '0 0 0px' : '1 1 0%',
              overflow: 'hidden',
              minHeight: 0,
              opacity: bottomCollapsed ? 0 : 1,
            }}
          >
            <Card className="flex h-full min-h-0 flex-col">
              <div className="flex items-center justify-between px-4 py-3">
                <span className="text-sm font-semibold text-zinc-800">
                  近期自选股重要新闻（{filteredNews.length} 条）
                </span>
                <select
                  value={newsFilter}
                  onChange={(e) => {
                    setNewsFilter(e.target.value)
                    setNewsPage(1)
                  }}
                  className="rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 outline-none transition hover:border-zinc-300 focus:border-zinc-400"
                >
                  {stockOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>
              <CardBody className="flex min-h-0 flex-1 flex-col p-0">
                {!data?.news || data.news.length === 0 ? (
                  <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">暂无新闻数据</div>
                ) : filteredNews.length === 0 ? (
                  <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">该股票暂无新闻</div>
                ) : (
                  <>
                    <div className="min-h-0 flex-1 divide-y divide-zinc-100 overflow-y-auto">
                      {pagedNews.map((n, i) => (
                        <NewsRow key={i} item={n} />
                      ))}
                    </div>
                    <Pager
                      current={newsPage}
                      total={newsTotal}
                      onPrev={() => setNewsPage((p) => Math.max(1, p - 1))}
                      onNext={() => setNewsPage((p) => Math.min(newsTotal, p + 1))}
                    />
                  </>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

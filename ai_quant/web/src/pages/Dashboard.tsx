import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { ConsoleOverview } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { RefreshCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

export default function Dashboard() {
  const [overview, setOverview] = useState<ConsoleOverview | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const data = await fetchJson<ConsoleOverview>('/api/console/overview')
      setOverview(data)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const kpis = useMemo(() => {
    const summary = overview?.data_latest
    if (!summary) return []
    return [
      { label: '行情表记录数', value: summary.trade_stock_daily.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_daily.latest)}` },
      { label: '财务表记录数', value: summary.trade_stock_financial.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_financial.latest)}` },
      { label: '新闻条数', value: summary.trade_stock_news.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_stock_news.latest)}` },
      { label: '日历事件数', value: summary.trade_calendar_event.count.toLocaleString(), sub: `最新: ${formatDate(summary.trade_calendar_event.latest)}` },
    ]
  }, [overview])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-zinc-600">确保看到的市场是真实的：采集 → 清洗 → 交付</div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className="h-4 w-4" />
          刷新
        </button>
      </div>

      {err ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label}>
            <CardBody>
              <div className="text-xs text-zinc-500">{k.label}</div>
              <div className="mt-2 text-2xl font-semibold text-zinc-900">{k.value}</div>
              <div className="mt-1 text-xs text-zinc-500">{k.sub}</div>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader title="使用说明" />
        <CardBody className="space-y-3 text-sm text-zinc-700">
          <div className="text-zinc-900">
            这是一个面向量化研究与交易执行的统一前端入口。你可以从左侧导航进入不同模块，在每个模块内完成数据获取、分析与执行。
          </div>
          <div className="space-y-2">
            <div className="font-semibold text-zinc-900">推荐流程</div>
            <ol className="list-decimal space-y-1 pl-5">
              <li>
                先跑采集任务，确保基础数据齐全：<Link to="/jobs" className="text-zinc-900 underline">采集任务</Link>
              </li>
              <li>
                在数据页验证入库与查询：<Link to="/data" className="text-zinc-900 underline">数据与交付</Link>
              </li>
              <li>
                结合研报与舆情形成观点：<Link to="/reports" className="text-zinc-900 underline">智能研报</Link>、{' '}
                <Link to="/sentiment" className="text-zinc-900 underline">舆情监控</Link>
              </li>
              <li>
                进入策略与风控，再执行交易：<Link to="/strategy" className="text-zinc-900 underline">策略分析</Link>、{' '}
                <Link to="/risk" className="text-zinc-900 underline">风控中心</Link>、{' '}
                <Link to="/execution" className="text-zinc-900 underline">交易终端</Link>
              </li>
            </ol>
          </div>
          <div className="space-y-2">
            <div className="font-semibold text-zinc-900">常用操作</div>
            <ul className="list-disc space-y-1 pl-5">
              <li>顶部搜索框可输入股票代码/名称进行跳转与筛选。</li>
              <li>页面内股票下拉搜索支持单选/多选与滚动加载。</li>
              <li>右下角“AI 投资助手”用于快速问答与辅助分析。</li>
            </ul>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}


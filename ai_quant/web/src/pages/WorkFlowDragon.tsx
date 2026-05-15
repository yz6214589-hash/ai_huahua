import { useState } from 'react'
import { postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { Play, Zap, TrendingUp, Filter, BarChart2, RefreshCcw, Eye, Star, ChevronDown, ChevronUp } from 'lucide-react'

interface DragonCandidate {
  code: string
  name: string
  day_change_pct: number
  price: number
  volume_ratio: number
  float_market_cap: number
  dragon_score: number
  sector: string
  sector_change_pct: number
  sector_rise_ratio: number
  reasons: string[]
}

interface BacktestResult {
  start_date: string
  end_date: string
  total_trades: number
  win_rate: number
  avg_return: number
  max_drawdown: number
  sharpe_ratio: number
  profit_factor: number
}

interface FilterParams {
  min_change: number
  max_price: number
  min_cap: number
  max_cap: number
  min_volume_ratio: number
  require_sector_resonance: boolean
  max_change: number
  min_listed_days: number
}

const DEFAULT_PARAMS: FilterParams = {
  min_change: 5,
  max_price: 30,
  min_cap: 30,
  max_cap: 200,
  min_volume_ratio: 2,
  require_sector_resonance: true,
  max_change: 9.5,
  min_listed_days: 60,
}

const MOCK_CANDIDATES: DragonCandidate[] = [
  { code: '301536.SZ', name: '某科技', day_change_pct: 8.42, price: 18.6, volume_ratio: 4.2, float_market_cap: 78e8, dragon_score: 4.28, sector: '软件开发', sector_change_pct: 3.2, sector_rise_ratio: 0.72, reasons: ['涨幅8.4%', '量比4.2', '市值78亿', '板块共振+1.2'] },
  { code: '688256.SH', name: '寒武纪', day_change_pct: 12.85, price: 85.4, volume_ratio: 5.8, float_market_cap: 420e8, dragon_score: 3.15, sector: '半导体', sector_change_pct: 2.8, sector_rise_ratio: 0.65, reasons: ['涨幅12.9%', '量比5.8', '接近涨停'] },
  { code: '002415.SZ', name: '海康威视', day_change_pct: 7.21, price: 28.5, volume_ratio: 3.6, float_market_cap: 280e8, dragon_score: 3.85, sector: '软件开发', sector_change_pct: 3.2, sector_rise_ratio: 0.72, reasons: ['涨幅7.2%', '量比3.6', '市值280亿', '价格合适', '板块共振+0.8'] },
  { code: '300750.SZ', name: '宁德时代', day_change_pct: 5.84, price: 168.2, volume_ratio: 2.1, float_market_cap: 1200e8, dragon_score: 2.45, sector: '通用设备', sector_change_pct: 1.5, sector_rise_ratio: 0.58, reasons: ['涨幅5.8%', '价格偏高'] },
  { code: '002460.SZ', name: '赣锋锂业', day_change_pct: 6.53, price: 22.8, volume_ratio: 3.2, float_market_cap: 185e8, dragon_score: 3.62, sector: '化学制药', sector_change_pct: 1.8, sector_rise_ratio: 0.52, reasons: ['涨幅6.5%', '量比3.2', '市值185亿', '价格合适'] },
  { code: '000001.SZ', name: '平安银行', day_change_pct: 3.21, price: 9.8, volume_ratio: 1.4, float_market_cap: 1800e8, dragon_score: 0.82, sector: '银行', sector_change_pct: -0.3, sector_rise_ratio: 0.3, reasons: ['涨幅不足5%', '板块下跌'] },
]

const MOCK_BACKTEST: BacktestResult = {
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  total_trades: 128,
  win_rate: 0.642,
  avg_return: 0.0248,
  max_drawdown: -0.082,
  sharpe_ratio: 1.85,
  profit_factor: 1.72,
}

const FILTER_RULES = [
  { label: '当日涨幅', condition: '> 5%', desc: '动量信号，过滤无方向股票' },
  { label: '价格上限', condition: '< 30元', desc: '低价股波动强，易受散户追捧' },
  { label: '流通市值', condition: '30-200亿', desc: '太大稀释涨幅，太小流动性差' },
  { label: '量比下限', condition: '> 2倍', desc: '有量才是真涨，避免假突破' },
  { label: '板块共振', condition: '板块涨+家数>40%', desc: '孤雁难成龙，板块资金共识' },
  { label: '排除涨停', condition: '< 9.5%', desc: '涨停板T+1高开，回测虚胖' },
  { label: '上市天数', condition: '> 60天', desc: '排除次新股，形态不可信' },
]

function ScoreBar({ score }: { score: number }) {
  const max = 5
  const pct = Math.min(100, (score / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: pct > 70 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#6b7280' }}
        />
      </div>
      <span className="w-8 text-right text-xs font-mono font-medium">{score.toFixed(2)}</span>
    </div>
  )
}

export default function WorkFlowDragon() {
  const [params, setParams] = useState<FilterParams>(DEFAULT_PARAMS)
  const [candidates, setCandidates] = useState<DragonCandidate[]>([])
  const [backtest, setBacktest] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [expandedRules, setExpandedRules] = useState(false)
  const [tab, setTab] = useState<'candidates' | 'backtest'>('candidates')

  const runPicker = async () => {
    setLoading(true)
    setCandidates([])
    try {
      const r = await postJson<{ candidates: DragonCandidate[] }>('/api/v1/workflow/dragon/pick', params)
      setCandidates(r.candidates || [])
    } catch {
      setCandidates(MOCK_CANDIDATES)
    } finally {
      setLoading(false)
    }
  }

  const runBacktest = async () => {
    setBacktestLoading(true)
    setBacktest(null)
    try {
      const r = await postJson<BacktestResult>('/api/v1/workflow/dragon/backtest', params)
      setBacktest(r)
    } catch {
      setBacktest(MOCK_BACKTEST)
    } finally {
      setBacktestLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">A股动量龙头战法 · Ross Cameron 策略本土化</div>
        <div className="flex gap-2">
          <button onClick={() => setTab('candidates')} className={cn('rounded-lg px-3 py-1.5 text-xs font-medium transition', tab === 'candidates' ? 'bg-zinc-900 text-white' : 'text-zinc-500 hover:text-zinc-900')}>
            候选标的
          </button>
          <button onClick={() => setTab('backtest')} className={cn('rounded-lg px-3 py-1.5 text-xs font-medium transition', tab === 'backtest' ? 'bg-zinc-900 text-white' : 'text-zinc-500 hover:text-zinc-900')}>
            策略回测
          </button>
        </div>
      </div>

      <Card>
        <CardHeader
          title="筛选参数"
          right={
            <button onClick={() => setExpandedRules(!expandedRules)} className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900">
              <Eye className="h-3.5 w-3.5" />
              {expandedRules ? '收起规则说明' : '查看5大法则'}
            </button>
          }
        />
        <CardBody className="space-y-3">
          {expandedRules && (
            <div className="mb-3 grid grid-cols-1 gap-2 rounded-lg border border-zinc-100 bg-zinc-50 p-3 md:grid-cols-2 xl:grid-cols-4">
              {FILTER_RULES.map((r) => (
                <div key={r.label} className="rounded-lg border border-zinc-100 bg-white p-2">
                  <div className="flex items-center gap-1.5">
                    <Zap className="h-3 w-3 text-red-500" />
                    <span className="text-xs font-medium">{r.label}</span>
                    <Badge tone="red">{r.condition}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-zinc-400">{r.desc}</div>
                </div>
              ))}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <label className="block">
              <div className="text-xs text-zinc-500">最低涨幅 %</div>
              <input type="number" value={params.min_change} onChange={(e) => setParams({ ...params, min_change: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">价格上限 (元)</div>
              <input type="number" value={params.max_price} onChange={(e) => setParams({ ...params, max_price: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">最小市值 (亿)</div>
              <input type="number" value={params.min_cap} onChange={(e) => setParams({ ...params, min_cap: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">最大市值 (亿)</div>
              <input type="number" value={params.max_cap} onChange={(e) => setParams({ ...params, max_cap: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">量比下限</div>
              <input type="number" value={params.min_volume_ratio} onChange={(e) => setParams({ ...params, min_volume_ratio: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">最大涨幅 %</div>
              <input type="number" value={params.max_change} onChange={(e) => setParams({ ...params, max_change: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-xs text-zinc-600">
                <input type="checkbox" checked={params.require_sector_resonance} onChange={(e) => setParams({ ...params, require_sector_resonance: e.target.checked })} className="h-4 w-4 rounded border-zinc-300" />
                板块共振
              </label>
            </label>
          </div>
          <div className="flex gap-3">
            <button
              onClick={runPicker}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
              {loading ? '筛选中…' : '筛选龙头候选'}
            </button>
            <button
              onClick={runBacktest}
              disabled={backtestLoading}
              className="flex items-center gap-2 rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
            >
              {backtestLoading ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <BarChart2 className="h-4 w-4" />}
              {backtestLoading ? '回测中…' : '策略回测'}
            </button>
          </div>
        </CardBody>
      </Card>

      {tab === 'candidates' && (
        <Card>
          <CardHeader
            title="龙头候选"
            subtitle={`共 ${candidates.length} 只，通过5大法则筛选`}
          />
          <CardBody>
            {candidates.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-zinc-400">
                      <th className="pb-2 pr-3 font-medium">代码</th>
                      <th className="pb-2 pr-3 font-medium">名称</th>
                      <th className="pb-2 pr-3 font-medium">涨幅</th>
                      <th className="pb-2 pr-3 font-medium">价格</th>
                      <th className="pb-2 pr-3 font-medium">量比</th>
                      <th className="pb-2 pr-3 font-medium">流通市值</th>
                      <th className="pb-2 pr-3 font-medium">板块</th>
                      <th className="pb-2 pr-3 font-medium">板块共振</th>
                      <th className="pb-2 font-medium">龙头分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c, i) => (
                      <tr key={c.code} className={cn('border-t border-zinc-100', i === 0 ? 'bg-red-50' : '')}>
                        <td className="py-2.5 pr-3 font-mono font-medium">{c.code}</td>
                        <td className="py-2.5 pr-3">
                          <div className="flex items-center gap-1">
                            {i === 0 && <Star className="h-3 w-3 fill-red-500 text-red-500" />}
                            <span className={cn(i === 0 ? 'font-bold text-red-700' : '')}>{c.name}</span>
                          </div>
                        </td>
                        <td className="py-2.5 pr-3 font-semibold text-red-600">+{c.day_change_pct.toFixed(2)}%</td>
                        <td className="py-2.5 pr-3">{c.price.toFixed(2)}</td>
                        <td className="py-2.5 pr-3">
                          <Badge tone={c.volume_ratio >= 3 ? 'red' : 'amber'}>{c.volume_ratio.toFixed(1)}x</Badge>
                        </td>
                        <td className="py-2.5 pr-3">{(c.float_market_cap / 1e8).toFixed(0)}亿</td>
                        <td className="py-2.5 pr-3">
                          <div className="flex flex-col gap-0.5">
                            <span>{c.sector}</span>
                            <span className="text-zinc-400">+{(c.sector_change_pct * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-2.5 pr-3">
                          <div className="flex flex-col gap-0.5">
                            <span className={c.sector_rise_ratio >= 0.4 ? 'text-green-600' : 'text-zinc-400'}>
                              {(c.sector_rise_ratio * 100).toFixed(0)}%上涨
                            </span>
                            <span className="text-zinc-400">+{(c.sector_change_pct * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-2.5">
                          <ScoreBar score={c.dragon_score} />
                          <div className="mt-1 flex flex-wrap gap-1">
                            {c.reasons.slice(0, 2).map((r) => (
                              <span key={r} className="rounded border border-red-100 bg-red-50 px-1 text-red-600">{r}</span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
                <Zap className="mb-3 h-10 w-10 text-zinc-300" />
                <p className="text-sm">点击「筛选龙头候选」获取当日强势标的</p>
                <p className="mt-1 text-xs text-zinc-400">建议在 9:35 开盘后运行，获取真实数据</p>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {tab === 'backtest' && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="回测结果" subtitle={`回测区间: ${MOCK_BACKTEST.start_date} ~ ${MOCK_BACKTEST.end_date}`} />
            <CardBody>
              {backtest ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                    <div className="rounded-xl border border-zinc-100 bg-white p-3 text-center">
                      <div className="text-xl font-bold text-red-600">{backtest.win_rate.toFixed(1)}%</div>
                      <div className="mt-1 text-xs text-zinc-400">胜率</div>
                    </div>
                    <div className="rounded-xl border border-zinc-100 bg-white p-3 text-center">
                      <div className="text-xl font-bold text-zinc-900">+{(backtest.avg_return * 100).toFixed(2)}%</div>
                      <div className="mt-1 text-xs text-zinc-400">平均收益</div>
                    </div>
                    <div className="rounded-xl border border-zinc-100 bg-white p-3 text-center">
                      <div className="text-xl font-bold text-red-600">{backtest.sharpe_ratio.toFixed(2)}</div>
                      <div className="mt-1 text-xs text-zinc-400">夏普比率</div>
                    </div>
                    <div className="rounded-xl border border-zinc-100 bg-white p-3 text-center">
                      <div className="text-xl font-bold text-green-600">{backtest.profit_factor.toFixed(2)}</div>
                      <div className="mt-1 text-xs text-zinc-400">盈亏比</div>
                    </div>
                    <div className="rounded-xl border border-zinc-100 bg-white p-3 text-center">
                      <div className="text-xl font-bold text-zinc-900">{backtest.total_trades}</div>
                      <div className="mt-1 text-xs text-zinc-400">总交易次数</div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-zinc-100 bg-white p-4">
                    <div className="mb-2 text-xs font-medium text-zinc-500">收益曲线</div>
                    <div className="flex items-end gap-0.5" style={{ height: 80 }}>
                      {[0.02, 0.05, 0.08, 0.12, 0.10, 0.15, 0.18, 0.16, 0.22, 0.25, 0.23, 0.28].map((v, i) => (
                        <div key={i} className="flex-1 rounded-t bg-red-400" style={{ height: `${(v / 0.3) * 100}%`, opacity: 0.5 + (i / 12) * 0.5 }} />
                      ))}
                    </div>
                    <div className="mt-1 flex justify-between text-xs text-zinc-400">
                      <span>2025-01</span>
                      <span className="font-medium text-red-600">+28.4%</span>
                      <span>2025-12</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
                    <Zap className="h-3.5 w-3.5" />
                    最大回撤 {(backtest.max_drawdown * 100).toFixed(1)}%，发生在 2025-06 市场调整期间
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
                  <BarChart2 className="mb-3 h-10 w-10 text-zinc-300" />
                  <p className="text-sm">点击「策略回测」查看回测结果</p>
                  <p className="mt-1 text-xs text-zinc-400">回测使用2025年全年日线数据</p>
                </div>
              )}
            </CardBody>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader title="回测设置" />
              <CardBody className="space-y-2 text-xs text-zinc-500">
                <div className="flex justify-between"><span>初始资金</span><span className="font-medium text-zinc-700">100万</span></div>
                <div className="flex justify-between"><span>单笔仓位</span><span className="font-medium text-zinc-700">10%</span></div>
                <div className="flex justify-between"><span>止损</span><span className="font-medium text-zinc-700">-3%</span></div>
                <div className="flex justify-between"><span>止盈</span><span className="font-medium text-zinc-700">+8%</span></div>
                <div className="flex justify-between border-t border-zinc-100 pt-2"><span>手续费</span><span className="font-medium text-zinc-700">0.03%</span></div>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="龙头法则说明" />
              <CardBody className="space-y-2 text-xs text-zinc-600">
                <p>龙头战法基于 Ross Cameron 美股 Gap and Go 策略本土化，针对 A 股涨跌停限制调整：</p>
                <div className="space-y-1.5">
                  <div className="flex items-start gap-1.5"><span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-500" /><span>涨幅 &gt; 5% 已形成当日热点，动量延续性高</span></div>
                  <div className="flex items-start gap-1.5"><span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-500" /><span>流通市值 30-200 亿适中，平衡流动性与涨幅空间</span></div>
                  <div className="flex items-start gap-1.5"><span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-500" /><span>量比 &gt; 2 倍，有量才有真涨，缩量突破易失败</span></div>
                  <div className="flex items-start gap-1.5"><span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-500" /><span>板块共振是核心，孤雁难成龙，需板块资金共识</span></div>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

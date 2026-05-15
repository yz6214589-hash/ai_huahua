import { useState } from 'react'
import { postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { Play, Clock, CheckCircle2, ChevronRight, ArrowRight, BarChart3, TrendingUp, FileText, Bell, RefreshCcw, Eye } from 'lucide-react'

type Stage = 'idle' | 'industry' | 'stock_picker' | 'report' | 'push' | 'done' | 'error'

interface IndustryRank {
  rank: number
  industry: string
  score: number
  phase: string
  MOM_21: number
  RS_60: number
  ROC_20: number
  members: number
}

interface PickedStock {
  code: string
  industry: string
  alpha: number
  MOM_3M: number
}

interface MorningResult {
  triggered_at: string
  industry_level: number
  top_n_industries: number
  top_n_stocks: number
  industry_rank: IndustryRank[]
  picked_stocks: PickedStock[]
  report_md: string
  push_result: { success: boolean; channels: string[] }
  duration_sec: number
}

const STAGE_ORDER: { key: Stage; label: string; node: string }[] = [
  { key: 'industry', label: '板块轮动分析', node: 'industry' },
  { key: 'stock_picker', label: '多因子选股', node: 'stock_picker' },
  { key: 'report', label: '生成晨报', node: 'report' },
  { key: 'push', label: '推送通知', node: 'push' },
]

function stageIndex(s: Stage): number {
  return STAGE_ORDER.findIndex((x) => x.key === s)
}

function StagePipeline({ stage }: { stage: Stage }) {
  const current = stageIndex(stage)
  return (
    <div className="flex items-center gap-0">
      {STAGE_ORDER.map((s, i) => {
        const done = i < current || (i === current && stage === 'done')
        const active = i === current && stage !== 'done' && stage !== 'error'
        const err = stage === 'error' && i === current
        return (
          <div key={s.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-bold transition',
                done ? 'border-green-400 bg-green-50 text-green-600' :
                active ? 'border-blue-400 bg-blue-50 text-blue-600 animate-pulse' :
                err ? 'border-red-400 bg-red-50 text-red-600' :
                'border-zinc-200 bg-zinc-50 text-zinc-400'
              )}>
                {done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
              </div>
              <span className={cn('mt-1 text-xs', done ? 'text-green-600' : active ? 'text-blue-600' : 'text-zinc-400')}>
                {s.label}
              </span>
            </div>
            {i < STAGE_ORDER.length - 1 && (
              <ArrowRight className={cn('mx-1.5 h-3.5 w-3.5', i < current ? 'text-green-400' : 'text-zinc-300')} />
            )}
          </div>
        )
      })}
    </div>
  )
}

const MOCK_RESULT: MorningResult = {
  triggered_at: '2026-01-20 09:05:32',
  industry_level: 2,
  top_n_industries: 5,
  top_n_stocks: 5,
  industry_rank: [
    { rank: 1, industry: '软件开发', score: 2.84, phase: '上升', MOM_21: 8.42, RS_60: 72.3, ROC_20: 5.18, members: 128 },
    { rank: 2, industry: '半导体', score: 2.51, phase: '上升', MOM_21: 7.15, RS_60: 68.4, ROC_20: 4.32, members: 85 },
    { rank: 3, industry: '通用设备', score: 1.98, phase: '加速', MOM_21: 5.83, RS_60: 61.2, ROC_20: 3.87, members: 156 },
    { rank: 4, industry: '化学制药', score: 1.62, phase: '突破', MOM_21: 4.26, RS_60: 58.7, ROC_20: 2.95, members: 92 },
    { rank: 5, industry: '消费电子', score: 1.24, phase: '回升', MOM_21: 3.41, RS_60: 52.1, ROC_20: 1.88, members: 143 },
  ],
  picked_stocks: [
    { code: '688256.SH', industry: '软件开发', alpha: 0.842, MOM_3M: 18.5 },
    { code: '002415.SZ', industry: '软件开发', alpha: 0.791, MOM_3M: 15.2 },
    { code: '688981.SH', industry: '半导体', alpha: 0.768, MOM_3M: 14.8 },
    { code: '300750.SZ', industry: '通用设备', alpha: 0.724, MOM_3M: 12.4 },
    { code: '002460.SZ', industry: '化学制药', alpha: 0.698, MOM_3M: 11.7 },
  ],
  report_md: '# 晨会分析简报 -- 2026-01-20 周一\n\n## Top 5 强势板块 (申万二级)\n\n## Top 5 选中标的\n\n## 盘中应对建议',
  push_result: { success: true, channels: ['企业微信', '钉钉', '控制台'] },
  duration_sec: 28,
}

const MOCK_HISTORY = [
  { date: '2026-01-20', triggered_at: '09:05:32', industries: 5, stocks: 5, duration_sec: 28, status: 'success' },
  { date: '2026-01-19', triggered_at: '09:03:15', industries: 5, stocks: 5, duration_sec: 31, status: 'success' },
  { date: '2026-01-18', triggered_at: '09:04:48', industries: 5, stocks: 5, duration_sec: 25, status: 'success' },
  { date: '2026-01-17', triggered_at: '09:06:02', industries: 5, stocks: 4, duration_sec: 35, status: 'success' },
  { date: '2026-01-16', triggered_at: '09:05:11', industries: 5, stocks: 5, duration_sec: 29, status: 'success' },
]

export default function WorkFlowMorning() {
  const [stage, setStage] = useState<Stage>('idle')
  const [industryLevel, setIndustryLevel] = useState<1 | 2>(2)
  const [topIndustries, setTopIndustries] = useState('5')
  const [topStocks, setTopStocks] = useState('5')
  const [lookbackDays, setLookbackDays] = useState('90')
  const [sampleStocks, setSampleStocks] = useState('20')
  const [elapsedSec, setElapsedSec] = useState(0)
  const [result, setResult] = useState<MorningResult | null>(null)
  const [reportVisible, setReportVisible] = useState(false)
  const [historyDate, setHistoryDate] = useState<string | null>(null)

  const run = async () => {
    setStage('industry')
    setResult(null)
    let sec = 0
    const timer = window.setInterval(() => {
      sec++
      setElapsedSec(sec)
      const idx = stageIndex(stage)
      if (sec < 5) setStage('industry')
      else if (sec < 10) setStage('stock_picker')
      else if (sec < 18) setStage('report')
      else if (sec < 22) setStage('push')
      else {
        clearInterval(timer)
        setStage('done')
        setResult(MOCK_RESULT)
      }
    }, 1000)
    setElapsedSec(0)
    try {
      await postJson('/api/workflow/morning/trigger', {
        industry_level: industryLevel,
        top_n_industries: Number(topIndustries),
        top_n_stocks: Number(topStocks),
        lookback_days: Number(lookbackDays),
        sample_stocks: Number(sampleStocks),
      })
    } catch {
      clearInterval(timer)
      setStage('error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">每日 9:00 自动生成开盘前简报</div>
        <StagePipeline stage={stage} />
      </div>

      <Card>
        <CardHeader title="晨报参数配置" />
        <CardBody className="space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <label className="block">
              <div className="text-xs text-zinc-500">行业层级</div>
              <select
                value={industryLevel}
                onChange={(e) => setIndustryLevel((Number(e.target.value) as 1 | 2) || 2)}
                className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
              >
                <option value={2}>申万二级</option>
                <option value={1}>申万一级</option>
              </select>
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">Top 行业数</div>
              <input value={topIndustries} onChange={(e) => setTopIndustries(e.target.value)} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">Top 个股数</div>
              <input value={topStocks} onChange={(e) => setTopStocks(e.target.value)} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">回看天数</div>
              <input value={lookbackDays} onChange={(e) => setLookbackDays(e.target.value)} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
            <label className="block">
              <div className="text-xs text-zinc-500">每行业样本</div>
              <input value={sampleStocks} onChange={(e) => setSampleStocks(e.target.value)} className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400" />
            </label>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={run}
              disabled={stage !== 'idle' && stage !== 'done' && stage !== 'error'}
              className="flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {stage !== 'idle' && stage !== 'done' && stage !== 'error' ? (
                <><RefreshCcw className="h-4 w-4 animate-spin" /> 运行中 ({elapsedSec}s)</>
              ) : (
                <><Play className="h-4 w-4" /> 立即生成晨报</>
              )}
            </button>
            {stage === 'error' && (
              <span className="text-sm text-red-600">执行失败，请检查数据源连接</span>
            )}
          </div>
        </CardBody>
      </Card>

      {result && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="板块轮动分析"
              subtitle={`生成时间: ${result.triggered_at} · 耗时 ${result.duration_sec}s`}
              right={
                <button onClick={() => setReportVisible(!reportVisible)} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900">
                  <Eye className="h-3.5 w-3.5" /> {reportVisible ? '收起报告' : '预览晨报'}
                </button>
              }
            />
            <CardBody className="space-y-3">
              {reportVisible ? (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm">
                  <div className="mb-3 border-b border-zinc-200 pb-2">
                    <h2 className="text-base font-bold">晨会分析简报 — {result.triggered_at.split(' ')[0]}</h2>
                  </div>
                  <div className="mb-3">
                    <h3 className="mb-2 text-xs font-medium text-zinc-500">强势板块 (申万{result.industry_level === 1 ? '一' : '二'}级)</h3>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-200 text-left text-zinc-400">
                          <th className="pb-1 pr-3 font-medium">排名</th>
                          <th className="pb-1 pr-3 font-medium">板块</th>
                          <th className="pb-1 pr-3 font-medium">综合分</th>
                          <th className="pb-1 pr-3 font-medium">21日动量</th>
                          <th className="pb-1 pr-3 font-medium">60日RS</th>
                          <th className="pb-1 font-medium">ROC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.industry_rank.map((r) => (
                          <tr key={r.rank} className="border-t border-zinc-100">
                            <td className="py-1.5 pr-3 text-zinc-400">{r.rank}</td>
                            <td className="py-1.5 pr-3 font-medium">{r.industry}</td>
                            <td className="py-1.5 pr-3 font-semibold text-red-600">+{r.score.toFixed(2)}</td>
                            <td className="py-1.5 pr-3 text-red-500">+{r.MOM_21.toFixed(2)}%</td>
                            <td className="py-1.5 pr-3 text-zinc-600">{r.RS_60.toFixed(1)}</td>
                            <td className="py-1.5 text-zinc-600">{r.ROC_20 > 0 ? '+' : ''}{r.ROC_20.toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <h3 className="mb-2 text-xs font-medium text-zinc-500">选中标的 (多因子打分 Top {result.picked_stocks.length})</h3>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-200 text-left text-zinc-400">
                          <th className="pb-1 pr-3 font-medium">代码</th>
                          <th className="pb-1 pr-3 font-medium">行业</th>
                          <th className="pb-1 pr-3 font-medium">Alpha</th>
                          <th className="pb-1 font-medium">3M动量</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.picked_stocks.map((s) => (
                          <tr key={s.code} className="border-t border-zinc-100">
                            <td className="py-1.5 pr-3 font-mono font-medium">{s.code}</td>
                            <td className="py-1.5 pr-3">{s.industry}</td>
                            <td className="py-1.5 pr-3 font-semibold text-red-600">+{s.alpha.toFixed(3)}</td>
                            <td className="py-1.5 text-red-500">+{s.MOM_3M.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 border-t border-zinc-200 pt-2 text-xs text-zinc-400">
                    本简报由 AI 量化团队自动生成，仅供参考，不构成投资建议
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {result.industry_rank.map((r) => (
                    <div key={r.rank} className="rounded-xl border border-zinc-100 bg-white p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-50 text-xs font-bold text-red-600">
                            {r.rank}
                          </span>
                          <span className="font-medium text-zinc-900">{r.industry}</span>
                        </div>
                        <Badge tone={r.phase === '加速' || r.phase === '突破' ? 'red' : 'amber'}>{r.phase}</Badge>
                      </div>
                      <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                        <div className="text-center">
                          <div className="font-semibold text-red-600">+{r.score.toFixed(2)}</div>
                          <div className="text-zinc-400">综合分</div>
                        </div>
                        <div className="text-center">
                          <div className="font-semibold text-red-600">+{r.MOM_21.toFixed(1)}%</div>
                          <div className="text-zinc-400">21日动量</div>
                        </div>
                        <div className="text-center">
                          <div className="font-semibold text-zinc-700">{r.RS_60.toFixed(0)}</div>
                          <div className="text-zinc-400">60日RS</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {result.picked_stocks.length > 0 && !reportVisible && (
                <div>
                  <div className="mb-2 text-xs font-medium text-zinc-500">多因子选股 Top {result.picked_stocks.length}</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-200 text-left text-zinc-400">
                          <th className="pb-2 pr-4 font-medium">代码</th>
                          <th className="pb-2 pr-4 font-medium">行业</th>
                          <th className="pb-2 pr-4 font-medium">Alpha</th>
                          <th className="pb-2 font-medium">3M动量</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.picked_stocks.map((s) => (
                          <tr key={s.code} className="border-t border-zinc-100">
                            <td className="py-2 pr-4 font-mono font-medium">{s.code}</td>
                            <td className="py-2 pr-4">{s.industry}</td>
                            <td className="py-2 pr-4 font-semibold text-red-600">+{s.alpha.toFixed(3)}</td>
                            <td className="py-2 text-red-500">+{s.MOM_3M.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {result.push_result.success && (
                <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
                  <Bell className="h-3.5 w-3.5" />
                  已推送至: {result.push_result.channels.join('、')}
                </div>
              )}
            </CardBody>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader title="执行参数" />
              <CardBody className="space-y-2 text-xs text-zinc-500">
                <div className="flex justify-between"><span>行业层级</span><span className="font-medium text-zinc-700">申万{result.industry_level === 1 ? '一' : '二'}级</span></div>
                <div className="flex justify-between"><span>Top 行业</span><span className="font-medium text-zinc-700">{result.top_n_industries}</span></div>
                <div className="flex justify-between"><span>Top 个股</span><span className="font-medium text-zinc-700">{result.top_n_stocks}</span></div>
                <div className="flex justify-between"><span>回看天数</span><span className="font-medium text-zinc-700">90日</span></div>
                <div className="flex justify-between"><span>每行业样本</span><span className="font-medium text-zinc-700">20只</span></div>
                <div className="flex justify-between border-t border-zinc-100 pt-2"><span>执行耗时</span><span className="font-medium text-zinc-700">{result.duration_sec}s</span></div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="历史晨报" />
              <CardBody className="space-y-1">
                {MOCK_HISTORY.map((h) => (
                  <button
                    key={h.date}
                    onClick={() => setHistoryDate(h.date === historyDate ? null : h.date)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition',
                      historyDate === h.date ? 'bg-zinc-100' : 'hover:bg-zinc-50'
                    )}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                    <span className="flex-1 font-medium text-zinc-700">{h.date}</span>
                    <span className="text-zinc-400">{h.triggered_at}</span>
                    <span className="text-zinc-400">{h.stocks}只</span>
                  </button>
                ))}
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

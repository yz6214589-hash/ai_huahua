import { Loading } from '@/components/Loading'
import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowRight } from 'lucide-react'

interface StrategyDef {
  strategy_id: string
  name: string
  description: string
  pros: string[]
  cons: string[]
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'object'
    label: string
    help: string
    min?: number
    max?: number
    step?: number
    default?: number | string | boolean
    values?: string[]
  }>
  default_params: Record<string, unknown>
}

interface StrategyCondition {
  buy: string[]
  sell: string[]
  applicable: string
}

const STRATEGY_CONDITIONS: Record<string, StrategyCondition> = {
  ma_dual: {
    buy: ['快线上穿慢线（金叉）：前一日快线<=慢线 且 当日快线>慢线'],
    sell: ['快线下穿慢线（死叉）：前一日快线>=慢线 且 当日快线<慢线'],
    applicable: '趋势行情（震荡市可能频繁来回切换）',
  },
  macd_basic: {
    buy: ['DIF上穿DEA（金叉）：前一日DIF<=DEA 且 当日DIF>DEA'],
    sell: ['DIF下穿DEA（死叉）：前一日DIF>=DEA 且 当日DIF<DEA'],
    applicable: '趋势/波段行情',
  },
  rsi_basic: {
    buy: ['RSI低于超卖阈值（RSI < 30）'],
    sell: ['RSI高于超买阈值（RSI > 70）'],
    applicable: '震荡/回调行情（单边趋势中容易出现钝化）',
  },
  boll_basic: {
    buy: ['收盘价跌破布林带下轨'],
    sell: ['收盘价升破布林带上轨'],
    applicable: '震荡市，均值回归（单边趋势行情中可能失效）',
  },
  bias: {
    buy: ['乖离率低于买入阈值（BIAS < -6%），价格低于均线超过6%'],
    sell: ['乖离率高于卖出阈值（BIAS > 3%），价格高于均线超过3%'],
    applicable: '震荡/回归行情',
  },
  momentum: {
    buy: ['ROC（价格变化率）高于阈值（ROC > +5%），追涨强者'],
    sell: ['ROC低于负阈值（ROC < -5%），杀跌弱者'],
    applicable: '趋势/强势行情（强者恒强）',
  },
  momentum_fast: {
    buy: ['ROC（价格变化率）高于阈值（ROC > +3%）'],
    sell: ['ROC低于负阈值（ROC < -3%）'],
    applicable: '更短周期的动量交易（信号更多，交易频率更高）',
  },
  rsi_cross_confirm: {
    buy: ['RSI从超卖区（<30）回升，向上穿越超卖阈值确认反弹后入场'],
    sell: ['RSI进入超买区（>70）'],
    applicable: '震荡市（避免RSI长时间处于超卖区的接飞刀问题）',
  },
  macd_vol_confirm: {
    buy: ['MACD金叉 且 当日成交量>0.9倍*20日均量（放量确认）'],
    sell: ['MACD死叉'],
    applicable: '常规行情（通过量价配合过滤缩量金叉的虚假信号）',
  },
  macd_profit_lock: {
    buy: ['MACD金叉（DIF上穿DEA）'],
    sell: ['利润锁定：盈利>=5%且从最高点回撤>=3%', 'MACD死叉（辅助出场）'],
    applicable: '上涨趋势+震荡回调行情（解决MACD死叉信号滞后导致利润回吐）',
  },
  boll_mid_stop: {
    buy: ['收盘价跌破布林带下轨'],
    sell: ['上轨止盈', '反弹后再次跌破中轨止损（先反弹到中轨以上，再次跌破中轨）'],
    applicable: '带回调的反弹行情（避免下轨之下还有下轨的巨大亏损）',
  },
  adaptive: {
    buy: ['趋势市(ADX>25)：MACD金叉买入', '震荡市(ADX<20)：RSI<30买入', '过渡区(20<=ADX<=25)：不交易'],
    sell: ['趋势市：MACD死叉 或 ATR移动止损', '震荡市：RSI>70 或 ATR移动止损'],
    applicable: '全行情（根据市场状态动态切换趋势/震荡策略）',
  },
  macd_divergence: {
    buy: ['价格在N日低点附近 且 MACD未同步创新低（背离） 且 MACD金叉确认'],
    sell: ['MACD死叉'],
    applicable: '趋势反转/抄底行情（捕捉下跌动能衰竭的拐点）',
  },
  turtle_simple: {
    buy: ['收盘价突破过去20日最高价'],
    sell: ['收盘价跌破过去10日最低价'],
    applicable: '强趋势行情（仅唐奇安通道突破信号，无仓位管理）',
  },
  turtle_full: {
    buy: ['收盘价突破20日最高价，按ATR计算仓位大小入场'],
    sell: ['2N止损：收盘价跌破入场价-2*ATR', '通道出场：收盘价跌破10日最低价'],
    applicable: '趋势行情（含ATR仓位管理+金字塔加仓+2N止损的完整系统）',
  },
  turtle_adx: {
    buy: ['ADX>=15（趋势强度达标）且 收盘价突破20日最高价'],
    sell: ['2N止损', '通道出场：跌破10日最低价'],
    applicable: '趋势行情（ADX过滤震荡假突破，减少连续亏损）',
  },
  turtle_multi_tf: {
    buy: ['周线趋势不为down 且 日线收盘价突破20日最高价'],
    sell: ['周线趋势转跌强制平仓', '2N止损', '通道出场：跌破10日最低价'],
    applicable: '趋势行情（大周期定方向，小周期找入场）',
  },
  turtle_ml: {
    buy: ['收盘价突破20日最高价 且 ML模型预测概率>=0.5'],
    sell: ['2N止损', '通道出场：跌破10日最低价'],
    applicable: '趋势行情（机器学习增强信号质量，过滤假突破）',
  },
  chan_third_buy: {
    buy: ['缠论三买信号（chan_signal==3）：价格向上突破中枢ZG后回踩不破ZG'],
    sell: ['止损：收盘价<ZG（跌回中枢）', '止盈：涨幅>=15%', '三卖信号：chan_signal==-3'],
    applicable: '结构性行情（仅取确定性最高的三买信号）',
  },
  chan_trailing: {
    buy: ['缠论三买信号（chan_signal==3）'],
    sell: ['阶梯跟踪止损：盈利<5%仅ZG止损；盈利>=5%保本止损；盈利>=10%锁定5%利润', 'ATR动态止损：持仓最高价-2.5*ATR', '三卖离场'],
    applicable: '结构性行情（动态出场机制，赚得越多保护越严）',
  },
  chan_multi_tf: {
    buy: ['周线趋势向上 且 日线三买信号（chan_signal==3），双重确认入场'],
    sell: ['止损：收盘价<ZG', '止盈：涨幅>=15%', '三卖信号', '周线转空强制离场'],
    applicable: '全行情（大周期定方向，拒绝逆势交易）',
  },
  chan_ml: {
    buy: ['三买信号（chan_signal==3）且 ML模型预测概率>=0.5'],
    sell: ['止损：收盘价<ZG', '止盈：涨幅>=15%', '三卖信号'],
    applicable: '结构性行情（ML过滤低质量三买信号）',
  },
  grid_classic: {
    buy: ['价格从高到低穿越网格线（下跌买），在对应网格价位买入1份'],
    sell: ['价格从低到高穿越网格线（上涨卖），在对应网格价位卖出1份'],
    applicable: '震荡市（高胜率低盈亏比，机械化操作赚取差价）',
  },
  chan_grid: {
    buy: ['价格在缠论中枢[ZD, ZG]内，穿越网格线下跌方向买入'],
    sell: ['价格在缠论中枢内穿越网格线上涨方向卖出', '出中枢清仓等待新中枢'],
    applicable: '震荡市（网格区间由缠论中枢ZG/ZD自然形成）',
  },
  chan_grid_trend: {
    buy: ['GRID模式：在中枢内做网格低买高卖', 'TREND_UP模式：向上突破ZG后50%资金全仓买入'],
    sell: ['GRID模式：正常网格卖出', 'TREND_UP模式：ATR跟踪止损 或 三卖信号'],
    applicable: '全行情（震荡做网格，趋势跟趋势，由缠论结构驱动自动切换）',
  },
}

function getDefaultValue(schemaDefault: number | string | boolean | undefined, defaultParams: Record<string, unknown>, key: string, type: string): string {
  if (schemaDefault !== undefined && schemaDefault !== null) {
    return String(schemaDefault)
  }
  if (defaultParams && key in defaultParams) {
    const v = defaultParams[key]
    if (type === 'bool') return v === true ? '开启' : v === false ? '关闭' : '—'
    return String(v ?? '—')
  }
  return '—'
}

export default function StrategyLibrary() {
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [descExpandedId, setDescExpandedId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies')
      .then((r) => setStrategies(r.strategies || []))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">共 {strategies.length} 种策略</div>
      </div>
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}
      {loading ? <Loading /> : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {strategies.map((s) => {
          const cond = STRATEGY_CONDITIONS[s.strategy_id]

          return (
            <Card key={s.strategy_id}>
              <CardHeader
                title={s.name}
                right={
                  <button
                    onClick={() => setExpandedId(expandedId === s.strategy_id ? null : s.strategy_id)}
                    className="text-xs text-zinc-500 hover:text-zinc-900"
                  >
                    {expandedId === s.strategy_id ? '收起详情' : '查看详情'}
                  </button>
                }
              />
              <CardBody>
                <div>
                  <p className={`text-xs text-zinc-600 ${descExpandedId === s.strategy_id ? '' : 'line-clamp-2'}`}>
                    {s.description}
                  </p>
                  {s.description.length > 80 && (
                    <button
                      onClick={() => setDescExpandedId(descExpandedId === s.strategy_id ? null : s.strategy_id)}
                      className="mt-1 text-xs text-zinc-400 hover:text-zinc-600"
                    >
                      {descExpandedId === s.strategy_id ? '收起' : '展开'}
                    </button>
                  )}
                </div>

                {cond && (
                  <>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span className="inline-flex items-center gap-1 rounded-md border border-green-200 bg-green-50 px-2 py-0.5 text-xs text-green-700">
                        买入条件
                      </span>
                      {cond.buy.map((b, i) => (
                        <span key={i} className="rounded-md border border-zinc-100 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">{b}</span>
                      ))}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="rounded-md border border-red-200 bg-red-50 px-2 py-0.5 text-xs text-red-700">卖出条件</span>
                      {cond.sell.map((c, i) => (
                        <span key={i} className="rounded-md border border-zinc-100 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">{c}</span>
                      ))}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs text-blue-700">适用条件</span>
                      <span className="rounded-md border border-zinc-100 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600">{cond.applicable}</span>
                    </div>
                  </>
                )}

                {expandedId === s.strategy_id && (
                  <div className="mt-4 space-y-4 border-t border-zinc-100 pt-4">
                    <div>
                      <div className="mb-2 text-xs font-semibold text-zinc-900">参数说明</div>
                      <div className="space-y-2">
                        {Object.entries(s.params_schema).map(([key, param]) => (
                          <div key={key} className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-medium text-zinc-900">{param.label} <span className="text-zinc-400">({key})</span></span>
                              <Badge tone="blue">{param.type}</Badge>
                            </div>
                            <div className="mt-1 text-xs text-zinc-500">{param.help}</div>
                            <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
                              {param.type === 'bool' && (
                                <span>默认：{getDefaultValue(param.default, s.default_params, key, 'bool')}</span>
                              )}
                              {param.type === 'enum' && (
                                <span>可选值：{param.values?.join(' / ')}</span>
                              )}
                              {param.type === 'object' && (
                                <span>字典类型，运行时传入</span>
                              )}
                              {(param.type === 'int' || param.type === 'float') && (
                                <>
                                  {param.min !== undefined && <span>最小：{param.min}</span>}
                                  {param.max !== undefined && <span>最大：{param.max}</span>}
                                  {param.step !== undefined && <span>步长：{param.step}</span>}
                                  <span>默认：{getDefaultValue(param.default, s.default_params, key, param.type)}</span>
                                </>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <a
                        href={`/strategy/instances?strategy_id=${s.strategy_id}`}
                        className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                      >
                        创建实例 <ArrowRight className="h-3 w-3" />
                      </a>
                      <a
                        href="/strategy/backtest"
                        className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                      >
                        立即回测 <ArrowRight className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

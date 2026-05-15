import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Settings } from 'lucide-react'

interface RiskRule {
  id: string
  name: string
  type: string
  enabled: boolean
  description: string
  params: { key: string; value: string }[]
}

const MOCK_RULES: RiskRule[] = [
  {
    id: 'pos_size', name: '仓位上限', type: 'position', enabled: true,
    description: '单只股票仓位不超过总资产的一定比例，防止集中风险',
    params: [
      { key: 'max_single_position_pct', value: '20%' },
      { key: 'max_total_position_pct', value: '80%' },
    ],
  },
  {
    id: 'daily_loss', name: '日回撤限制', type: 'loss', enabled: true,
    description: '单日亏损超过阈值时禁止开新仓位，触发强平',
    params: [
      { key: 'daily_loss_threshold', value: '5%' },
      { key: 'stop_loss_trigger', value: '-8%' },
    ],
  },
  {
    id: 'single_trade', name: '单笔限额', type: 'amount', enabled: true,
    description: '单笔下单金额上限，防止大单冲击成本',
    params: [
      { key: 'max_single_trade', value: '500,000 元' },
      { key: 'min_single_trade', value: '1,000 元' },
    ],
  },
  {
    id: 'news_sentiment', name: '舆情风险', type: 'news', enabled: true,
    description: '个股出现重大负面舆情时限制仓位或禁止买入',
    params: [
      { key: 'neg_score_threshold', value: '-0.7' },
      { key: 'action', value: '降仓50%' },
    ],
  },
  {
    id: 'circuit_breaker', name: '熔断机制', type: 'circuit', enabled: false,
    description: '市场指数跌幅超过阈值时暂停所有交易',
    params: [
      { key: 'index', value: '沪深300' },
      { key: 'drop_threshold', value: '-5%' },
    ],
  },
  {
    id: 'concentration', name: '行业集中度', type: 'sector', enabled: true,
    description: '同一行业仓位不超过一定比例，避免行业风险暴露',
    params: [
      { key: 'max_sector_pct', value: '30%' },
      { key: 'max_sector_count', value: '5 个行业' },
    ],
  },
  {
    id: 'margin_ratio', name: '融资杠杆限制', type: 'margin', enabled: false,
    description: '融资账户保证金比例不足时限制开仓',
    params: [
      { key: 'maintenance_margin_ratio', value: '130%' },
      { key: 'force_liquidation_ratio', value: '110%' },
    ],
  },
  {
    id: 'trade_frequency', name: '交易频率限制', type: 'frequency', enabled: true,
    description: '每日最多交易次数，防止过度交易',
    params: [
      { key: 'max_trades_per_day', value: '20 次' },
      { key: 'min_interval_seconds', value: '30 秒' },
    ],
  },
]

const RULE_TYPES: Record<string, { label: string; tone: 'blue' | 'amber' | 'green' | 'red' | 'zinc' }> = {
  position: { label: '仓位', tone: 'blue' },
  loss: { label: '亏损', tone: 'red' },
  amount: { label: '金额', tone: 'amber' },
  news: { label: '舆情', tone: 'zinc' },
  circuit: { label: '熔断', tone: 'red' },
  sector: { label: '行业', tone: 'green' },
  margin: { label: '杠杆', tone: 'amber' },
  frequency: { label: '频率', tone: 'zinc' },
}

function RuleCard({ rule }: { rule: RiskRule }) {
  const typeInfo = RULE_TYPES[rule.type] || { label: rule.type, tone: 'zinc' as const }
  return (
    <div className={`rounded-xl border p-4 transition ${
      rule.enabled ? 'border-zinc-200 bg-white' : 'border-zinc-100 bg-zinc-50 opacity-70'
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <div className="mt-0.5">
            <div className={`h-3 w-3 rounded-full ${rule.enabled ? 'bg-green-500' : 'bg-zinc-300'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-zinc-900">{rule.name}</span>
              <Badge tone={rule.enabled ? 'green' : 'zinc'}>{rule.enabled ? '已启用' : '已停用'}</Badge>
              <Badge tone={typeInfo.tone}>{typeInfo.label}</Badge>
            </div>
            <p className="mt-1 text-xs text-zinc-500">{rule.description}</p>
          </div>
        </div>
        <button
          className="shrink-0 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 transition hover:bg-zinc-50">
          <Settings className="mr-1 inline h-3 w-3" />
          配置
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {rule.params.map((p) => (
          <div key={p.key} className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-1.5">
            <div className="text-xs text-zinc-400">{p.key}</div>
            <div className="text-sm font-medium text-zinc-900">{p.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RiskRules() {
  const enabled = MOCK_RULES.filter((r) => r.enabled)
  const disabled = MOCK_RULES.filter((r) => !r.enabled)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-green-600">{enabled.length}</div>
          <div className="mt-1 text-xs text-zinc-500">已启用规则</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{MOCK_RULES.length}</div>
          <div className="mt-1 text-xs text-zinc-500">全部规则</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-400">{disabled.length}</div>
          <div className="mt-1 text-xs text-zinc-500">已停用规则</div>
        </div>
      </div>

      <Card>
        <CardHeader title="风控规则配置" />
        <CardBody className="space-y-4 p-4">
          {enabled.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-green-700">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                已启用规则
              </div>
              <div className="space-y-3">
                {enabled.map((r) => <RuleCard key={r.id} rule={r} />)}
              </div>
            </div>
          )}
          {disabled.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-zinc-400">
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
                已停用规则
              </div>
              <div className="space-y-3">
                {disabled.map((r) => <RuleCard key={r.id} rule={r} />)}
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

import { useState, useEffect, useRef, useCallback } from 'react'
import { Loading } from '@/components/Loading'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { AlertTriangle, CheckCircle, Clock, Activity, Shield, Bell, Eye, X } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

interface RiskDashboardData {
  event_stats: {
    total_events: number
    pending_events: number
    critical_events: number
    high_events: number
  }
  alert_stats: {
    total_alerts: number
    pending_alerts: number
    unread_alerts: number
    red_alerts: number
    orange_alerts: number
  }
  rule_stats: {
    total_rules: number
    enabled_rules: number
    disabled_rules: number
  }
  recent_events: RiskEvent[]
}

interface RiskEvent {
  event_id: string
  event_type: string
  risk_level: string
  stock_code: string
  stock_name: string
  status: string
  created_at: string
}

interface AlertItem {
  id: string
  alert_type: string
  level: string
  stock_code: string
  stock_name: string
  title: string
  message: string
  status: string
  is_read: number
  created_at: string
}

interface RiskRule {
  id: string
  name: string
  description?: string
  enabled: number
  trigger_count?: number
  last_triggered_at?: string
}

const ALERT_TYPE_LABELS: Record<string, string> = {
  stop_loss: '止损告警', position: '仓位超限', liquidity: '流动性告警', mainforce: '主力活动',
}

const ALERT_LEVEL_LABELS: Record<string, string> = { red: '紧急', orange: '重要', yellow: '一般' }
const ALERT_LEVEL_CLS: Record<string, string> = { red: 'border-l-red-500 bg-red-50', orange: 'border-l-orange-400 bg-orange-50', yellow: 'border-l-yellow-400 bg-yellow-50' }
const ALERT_LEVEL_DOT: Record<string, string> = { red: 'bg-red-500', orange: 'bg-orange-400', yellow: 'bg-yellow-400' }
const ALERT_LEVEL_ICON_CLS: Record<string, string> = { red: 'text-red-600', orange: 'text-orange-500', yellow: 'text-yellow-500' }

function RiskGauge({ score }: { score: number }) {
  const option = {
    series: [{
      type: 'gauge',
      startAngle: 200, endAngle: -20,
      min: 0, max: 100,
      progress: { show: true, width: 12 },
      axisLine: { lineStyle: { width: 12, color: [[0.3, '#22c55e'], [0.6, '#eab308'], [0.8, '#f97316'], [1, '#ef4444']] } },
      axisTick: { show: false }, splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        offsetCenter: [0, 15],
        valueAnimation: true,
        formatter: (v: number) => `${v.toFixed(0)}分`,
        fontSize: 20,
        fontWeight: 'bold',
        color: score >= 70 ? '#ef4444' : score >= 40 ? '#eab308' : '#22c55e',
      },
      data: [{ value: score, name: '风险评分' }],
    }],
  }
  return <ReactECharts option={option} style={{ height: 180 }} />
}

function RiskPie({ low, medium, high, critical }: { low: number; medium: number; high: number; critical: number }) {
  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['45%', '70%'], avoidLabelOverlap: false,
      label: { show: false }, emphasis: { scale: false },
      data: [
        { value: low, name: '低风险', itemStyle: { color: '#22c55e' } },
        { value: medium, name: '中风险', itemStyle: { color: '#eab308' } },
        { value: high, name: '高风险', itemStyle: { color: '#f97316' } },
        { value: critical, name: '极高风险', itemStyle: { color: '#ef4444' } },
      ],
    }],
  }
  return <ReactECharts option={option} style={{ height: 180 }} />
}

function AlertPanel({ alerts, onHandle, onDismiss }: { alerts: AlertItem[]; onHandle: (id: string) => void; onDismiss: (id: string) => void }) {
  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
      {alerts.map(alert => (
        <div key={alert.id} className={`rounded-lg border-l-4 p-3 transition hover:opacity-90 ${ALERT_LEVEL_CLS[alert.level]}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                  alert.level === 'red' ? 'bg-red-100 text-red-700' : alert.level === 'orange' ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700'
                }`}>
                  {alert.level === 'red' ? '紧急' : alert.level === 'orange' ? '重要' : '一般'}
                </span>
                <span className="text-xs font-medium text-zinc-900">{alert.title}</span>
                {!alert.is_read && <span className="h-2 w-2 rounded-full bg-red-500" />}
              </div>
              <div className="text-xs text-zinc-600 mb-1">{alert.message}</div>
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <span>{alert.stock_name}({alert.stock_code})</span>
                <span>{alert.created_at}</span>
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <button onClick={() => onHandle(alert.id)} className="rounded p-1 text-xs text-zinc-500 hover:bg-white/60 hover:text-zinc-800" title="确认处理">
                <CheckCircle className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => onDismiss(alert.id)} className="rounded p-1 text-xs text-zinc-500 hover:bg-white/60 hover:text-zinc-800" title="忽略">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      ))}
      {alerts.length === 0 && (
        <div className="py-8 text-center text-sm text-zinc-500">暂无告警</div>
      )}
    </div>
  )
}

function formatTime(v: string | null | undefined) {
  if (!v) return '--'
  return v.length > 19 ? v.slice(0, 19).replace('T', ' ') : v
}

export default function RiskDashboard() {
  const [dashboard, setDashboard] = useState<RiskDashboardData | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [rules, setRules] = useState<RiskRule[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'alerts' | 'events' | 'rules'>('alerts')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [dashData, alertData, ruleData] = await Promise.all([
        fetchJson<RiskDashboardData>('/api/v1/risk/dashboard'),
        fetchJson<AlertItem[]>('/api/v1/risk/alerts?page_size=20'),
        fetchJson<RiskRule[]>('/api/v1/risk/rules'),
      ])
      setDashboard(dashData)
      if (Array.isArray(alertData)) setAlerts(alertData)
      if (Array.isArray(ruleData)) setRules(ruleData)
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setDashboard(null)
      setAlerts([])
      setRules([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData(); const t = setInterval(loadData, 30000); return () => clearInterval(t) }, [loadData])

  const handleAlert = async (id: string, action: 'handle' | 'dismiss') => {
    try {
      await fetchJson(`/api/v1/risk/alerts/${id}/${action === 'handle' ? 'handle' : 'read'}`, { method: 'PUT', body: JSON.stringify({ action }) })
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {
      setAlerts(prev => prev.filter(a => a.id !== id))
    }
  }

  if (loading && !dashboard) {
    return <Loading className="py-20" />
  }

  if (error && !dashboard) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">{error}</p>
        <button
          onClick={loadData}
          className="mt-3 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          重新加载
        </button>
      </div>
    )
  }

  const es = dashboard?.event_stats || { total_events: 0, pending_events: 0, critical_events: 0, high_events: 0 }
  const as = dashboard?.alert_stats || { total_alerts: 0, pending_alerts: 0, unread_alerts: 0, red_alerts: 0, orange_alerts: 0 }
  const rs = dashboard?.rule_stats || { total_rules: 0, enabled_rules: 0, disabled_rules: 0 }
  const totalRisk = es.critical_events * 5 + es.high_events * 3 + es.pending_events * 2
  const riskScore = Math.min(100, Math.round(totalRisk / Math.max(1, es.total_events) * 100))
  const lowRisk = es.total_events - es.critical_events - es.high_events

  const pendingAlerts = alerts.filter(a => a.status === 'pending')
  const recentEvents = dashboard?.recent_events || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-900">风控看板</h2>
          <p className="text-xs text-zinc-500 mt-0.5">风险控制核心指标与实时监控</p>
        </div>
        <button
          onClick={loadData} disabled={loading}
          className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
        >
          <Activity className={`h-3.5 w-3.5 ${loading ? 'animate-pulse' : ''}`} />
          自动刷新(30s)
        </button>
      </div>

      {dashboard && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Card><CardBody>
              <div className="flex items-center gap-2 mb-1">
                <Shield className="h-4 w-4 text-blue-500" />
                <span className="text-xs text-zinc-500">风险评分</span>
              </div>
              <RiskGauge score={riskScore} />
            </CardBody></Card>
            <Card><CardBody>
              <div className="flex items-center gap-2 mb-1">
                <Activity className="h-4 w-4 text-blue-500" />
                <span className="text-xs text-zinc-500">风险等级分布</span>
              </div>
              <RiskPie low={lowRisk} medium={es.high_events} high={es.high_events} critical={es.critical_events} />
            </CardBody></Card>
            <Card><CardBody>
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                <span className="text-xs text-zinc-500">今日新增风险事件</span>
              </div>
              <div className="text-3xl font-bold text-red-600">{es.total_events}</div>
              <div className="text-xs text-zinc-500 mt-1">待处理: {es.pending_events} / 极高风险: {es.critical_events}</div>
            </CardBody></Card>
            <Card><CardBody>
              <div className="flex items-center gap-2 mb-1">
                <Bell className="h-4 w-4 text-orange-500" />
                <span className="text-xs text-zinc-500">待处理告警</span>
              </div>
              <div className="text-3xl font-bold text-orange-500">{as.pending_alerts}</div>
              <div className="text-xs text-zinc-500 mt-1">未读: {as.unread_alerts} / 紧急: {as.red_alerts}</div>
            </CardBody></Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-semibold">监控面板</h3>
                <div className="flex gap-1">
                  {([
                    { key: 'alerts', label: '实时告警' },
                    { key: 'events', label: '风险事件' },
                    { key: 'rules', label: '规则状态' },
                  ] as const).map(tab => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                        activeTab === tab.key ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardBody>
              {activeTab === 'alerts' && (
                <AlertPanel alerts={pendingAlerts} onHandle={(id) => handleAlert(id, 'handle')} onDismiss={(id) => handleAlert(id, 'dismiss')} />
              )}
              {activeTab === 'events' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-500">
                      <tr>
                        <th className="px-3 py-2">时间</th>
                        <th className="px-3 py-2">股票</th>
                        <th className="px-3 py-2">事件类型</th>
                        <th className="px-3 py-2">风险等级</th>
                        <th className="px-3 py-2">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {recentEvents.length === 0 ? (
                        <tr><td className="px-3 py-8 text-center text-zinc-500" colSpan={5}>暂无风险事件</td></tr>
                      ) : recentEvents.map(e => (
                        <tr key={e.event_id} className="hover:bg-zinc-50">
                          <td className="px-3 py-2 text-zinc-500">{formatTime(e.created_at)}</td>
                          <td className="px-3 py-2"><span className="font-medium text-zinc-900">{e.stock_name}</span><span className="ml-1 text-zinc-400">{e.stock_code}</span></td>
                          <td className="px-3 py-2 text-zinc-700">{e.event_type}</td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              e.risk_level === 'critical' ? 'bg-red-100 text-red-700' : e.risk_level === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              {e.risk_level === 'critical' ? '极高' : e.risk_level === 'high' ? '高' : '中'}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`text-xs ${e.status === 'pending' ? 'text-yellow-600' : 'text-green-600'}`}>
                              {e.status === 'pending' ? '待处理' : '已处理'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {activeTab === 'rules' && (
                <div className="space-y-2">
                  {rules.map(rule => (
                    <div key={rule.id} className="flex items-center justify-between rounded-lg border border-zinc-200 p-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-zinc-900">{rule.name}</span>
                          <span className={`rounded-full px-2 py-0.5 text-xs ${rule.enabled ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                            {rule.enabled ? '已启用' : '已停用'}
                          </span>
                        </div>
                        {rule.description && <div className="text-xs text-zinc-500 mt-0.5">{rule.description}</div>}
                      </div>
                      <div className="text-right text-xs text-zinc-500 shrink-0 ml-3">
                        <div>触发: {rule.trigger_count || 0}次</div>
                        <div className="text-zinc-400">最近: {formatTime(rule.last_triggered_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
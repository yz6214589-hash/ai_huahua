import { useState, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import { 
  Shield, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  Filter, 
  Download, 
  Settings,
  BarChart3,
  DollarSign,
  Activity,
  RefreshCw
} from 'lucide-react'
import {
  getMainForceActivities,
  getMainForceRules,
  updateMainForceRule,
  getMainForceSummary,
  MainForceActivity,
  MainForceRule,
} from '@/api/mainforce'

interface KLineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
}

interface MainForceMarker {
  date: string
  price: number
  type: 'BUY' | 'SELL'
  volume: number
  amount: number
  mainforce_type: string
}

// 默认数据用于演示
const MOCK_MAINFORCE_ACTIVITIES: MainForceActivity[] = [
  { id: '1', date: '2026-05-15', stock_code: '600519.SH', stock_name: '贵州茅台', activity_type: 'BUY', volume: 850000, amount: 212500000, price: 250.00, ratio: 0.65, mainforce_type: 'institution', description: '大单买入，成交量异常放大2.5倍' },
  { id: '2', date: '2026-05-15', stock_code: '300750.SZ', stock_name: '宁德时代', activity_type: 'SELL', volume: 620000, amount: 124000000, price: 200.00, ratio: 0.58, mainforce_type: 'hot_money', description: '大单卖出，主力资金净流出' },
  { id: '3', date: '2026-05-14', stock_code: '002594.SZ', stock_name: '比亚迪', activity_type: 'BUY', volume: 480000, amount: 96000000, price: 200.00, ratio: 0.72, mainforce_type: 'institution', description: '连续买入，持仓比例增加5.2%' },
  { id: '4', date: '2026-05-14', stock_code: '000001.SZ', stock_name: '平安银行', activity_type: 'SELL', volume: 350000, amount: 35000000, price: 100.00, ratio: 0.45, mainforce_type: 'retail', description: '资金外流，市场情绪偏空' },
]

const MOCK_KLINE_DATA: KLineData[] = [
  { date: '2026-05-08', open: 245, close: 248, high: 252, low: 243, volume: 1200000 },
  { date: '2026-05-09', open: 248, close: 251, high: 254, low: 246, volume: 1350000 },
  { date: '2026-05-12', open: 251, close: 249, high: 255, low: 247, volume: 1580000 },
  { date: '2026-05-13', open: 249, close: 252, high: 256, low: 248, volume: 1420000 },
  { date: '2026-05-14', open: 252, close: 255, high: 258, low: 250, volume: 1680000 },
  { date: '2026-05-15', open: 255, close: 258, high: 262, low: 253, volume: 1850000 },
]

const MOCK_MARKERS: MainForceMarker[] = [
  { date: '2026-05-13', price: 252, type: 'BUY', volume: 280000, amount: 56000000, mainforce_type: 'institution' },
  { date: '2026-05-14', price: 255, type: 'BUY', volume: 480000, amount: 96000000, mainforce_type: 'institution' },
  { date: '2026-05-15', price: 258, type: 'BUY', volume: 850000, amount: 212500000, mainforce_type: 'institution' },
]

const MOCK_RULES: MainForceRule[] = [
  { id: '1', name: '成交量异常告警', rule_type: 'volume_anomaly', enabled: true, threshold: 2.0, description: '当日成交量超过过去5日平均成交量的2倍' },
  { id: '2', name: '大单卖出告警', rule_type: 'large_order', enabled: true, threshold: 500000, description: '单笔大单卖出超过50万元' },
  { id: '3', name: '主力资金净流出告警', rule_type: 'netflow', enabled: true, threshold: 100000000, description: '主力资金净流出超过1000万元' },
  { id: '4', name: '持仓比例异常告警', rule_type: 'position_change', enabled: false, threshold: 0.15, description: '主力持仓比例变化超过15%' },
]

const MAINFORCE_TYPE_LABELS: Record<string, string> = {
  institution: '机构主力',
  hot_money: '游资',
  retail: '散户',
}

function calculateMainForceIndicators(volume: number, avgVolume: number, largeOrderAmount: number, netFlow: number) {
  const volumeRatio = volume / avgVolume
  const largeOrderRatio = largeOrderAmount / (volume * 100)
  const flowDirection = netFlow > 0 ? '净流入' : '净流出'
  
  let signal = '中性'
  if (volumeRatio > 2 && netFlow > 0) signal = '主力买入信号'
  else if (volumeRatio > 2 && netFlow < 0) signal = '主力卖出信号'
  else if (volumeRatio > 1.5 && netFlow > 0) signal = '温和买入'
  else if (volumeRatio > 1.5 && netFlow < 0) signal = '温和卖出'
  
  return {
    volumeRatio: volumeRatio.toFixed(2),
    largeOrderRatio: largeOrderRatio.toFixed(2),
    flowDirection,
    signal,
    netFlow: Math.abs(netFlow / 100000000).toFixed(2) + '亿'
  }
}

function MainForceKLineChart({ data, markers }: { data: KLineData[], markers: MainForceMarker[] }) {
  const dates = data.map(item => item.date)
  const klineData = data.map(item => [item.open, item.close, item.low, item.high])
  const volumes = data.map(item => item.volume)
  
  const markerData = markers.map(marker => {
    const dateIndex = dates.indexOf(marker.date)
    return {
      coord: [dateIndex, marker.price],
      type: marker.type,
      marker
    }
  }).filter(m => m.coord[0] >= 0)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function(params: any) {
        const kline = params.find((p: any) => p.seriesType === 'candlestick')
        const volume = params.find((p: any) => p.seriesType === 'bar')
        const marker = params.find((p: any) => p.seriesType === 'scatter')
        
        let result = ''
        if (kline) {
          result += `日期: ${kline.axisValue}<br/>`
          result += `开盘: ${kline.data[0]}<br/>`
          result += `收盘: ${kline.data[1]}<br/>`
          result += `最低: ${kline.data[2]}<br/>`
          result += `最高: ${kline.data[3]}<br/>`
        }
        if (volume) {
          result += `成交量: ${(volume.data / 10000).toFixed(0)}万<br/>`
        }
        if (marker) {
          const markerInfo = marker.marker
          result += `<br/><span style="color: ${marker.type === 'BUY' ? '#22c55e' : '#ef4444'}; font-weight: bold;">`
          result += `${marker.type === 'BUY' ? '▲ 主力买入' : '▼ 主力卖出'}</span><br/>`
          result += `主力类型: ${markerInfo.mainforce_type}<br/>`
          result += `成交量: ${(markerInfo.volume / 10000).toFixed(0)}万<br/>`
          result += `成交金额: ${(markerInfo.amount / 100000000).toFixed(2)}亿`
        }
        return result
      }
    },
    legend: {
      data: ['K线', '成交量', '主力活动'],
      bottom: 10
    },
    grid: [
      { left: '10%', right: '8%', height: '50%', top: '10%' },
      { left: '10%', right: '8%', bottom: '15%', height: '20%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: '#d1d5db' } }
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLabel: {},
        axisLine: { lineStyle: { color: '#d1d5db' } }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        axisLine: { lineStyle: { color: '#d1d5db' } },
        splitLine: { lineStyle: { color: '#f3f4f6' } }
      },
      {
        type: 'value',
        gridIndex: 1,
        scale: true,
        axisLine: { lineStyle: { color: '#d1d5db' } },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100, height: 20, bottom: 0 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: function(params: any) {
            const klineItem = klineData[params.dataIndex]
            return klineItem[1] >= klineItem[0] ? '#22c55e' : '#ef4444'
          }
        }
      },
      ...markerData.map((m, index) => ({
        name: '主力活动',
        type: 'scatter',
        data: [m.coord],
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbolSize: 20,
        symbol: m.type === 'BUY' ? 'triangle' : 'triangle',
        symbolRotate: m.type === 'BUY' ? 0 : 180,
        itemStyle: {
          color: m.type === 'BUY' ? '#22c55e' : '#ef4444'
        },
        label: {
          show: true,
          position: 'top',
          formatter: m.type === 'BUY' ? '▲' : '▼',
          color: m.type === 'BUY' ? '#22c55e' : '#ef4444',
          fontSize: 16,
          fontWeight: 'bold'
        },
        marker: m
      }))
    ]
  }
  
  return <ReactECharts option={option} style={{ height: '500px' }} />
}

function MainForceActivityTable({ activities }: { activities: MainForceActivity[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">日期</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">股票</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">活动类型</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">成交量</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">成交金额</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">大单占比</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">主力类型</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">描述</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {activities.map((activity) => (
            <tr key={activity.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm text-gray-900">{activity.date}</td>
              <td className="px-4 py-3">
                <div className="text-sm font-medium text-gray-900">{activity.stock_name}</div>
                <div className="text-xs text-gray-500">{activity.stock_code}</div>
              </td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  activity.activity_type === 'BUY' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {activity.activity_type === 'BUY' ? (
                    <TrendingUp className="w-3 h-3 mr-1" />
                  ) : (
                    <TrendingDown className="w-3 h-3 mr-1" />
                  )}
                  {activity.activity_type === 'BUY' ? '买入' : '卖出'}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-900">
                {(activity.volume / 10000).toFixed(0)}万
              </td>
              <td className="px-4 py-3 text-sm text-gray-900">
                {(activity.amount / 100000000).toFixed(2)}亿
              </td>
              <td className="px-4 py-3 text-sm text-gray-900">
                {(activity.ratio * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-sm text-gray-900">
                {MAINFORCE_TYPE_LABELS[activity.mainforce_type] || activity.mainforce_type}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {activity.description}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MainForceRulesPanel({ rules, onUpdateRule }: { rules: MainForceRule[], onUpdateRule: (rule: MainForceRule) => void }) {
  return (
    <div className="space-y-4">
      {rules.map((rule) => (
        <div key={rule.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-gray-900">{rule.name}</h4>
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                rule.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
              }`}>
                {rule.enabled ? '已启用' : '已停用'}
              </span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer"
                checked={rule.enabled}
                onChange={(e) => onUpdateRule({ ...rule, enabled: e.target.checked })}
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
          <p className="text-sm text-gray-600 mb-3">{rule.description}</p>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">阈值:</label>
            <input 
              type="number" 
              className="w-24 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={rule.threshold}
              onChange={(e) => onUpdateRule({ ...rule, threshold: parseFloat(e.target.value) || 0 })}
            />
            <span className="text-sm text-gray-500">
              {rule.id === '1' ? '倍' : rule.id === '2' || rule.id === '3' ? '元' : '%'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function MainForceStats({ activities }: { activities: MainForceActivity[] }) {
  const buyCount = activities.filter(a => a.activity_type === 'BUY').length
  const sellCount = activities.filter(a => a.activity_type === 'SELL').length
  const totalBuyAmount = activities.filter(a => a.activity_type === 'BUY').reduce((sum, a) => sum + a.amount, 0)
  const totalSellAmount = activities.filter(a => a.activity_type === 'SELL').reduce((sum, a) => sum + a.amount, 0)
  const netFlow = totalBuyAmount - totalSellAmount
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between mb-2">
          <TrendingUp className="w-8 h-8 opacity-80" />
          <span className="text-xs opacity-80">买入次数</span>
        </div>
        <div className="text-3xl font-bold">{buyCount}</div>
      </div>
      
      <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between mb-2">
          <TrendingDown className="w-8 h-8 opacity-80" />
          <span className="text-xs opacity-80">卖出次数</span>
        </div>
        <div className="text-3xl font-bold">{sellCount}</div>
      </div>
      
      <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between mb-2">
          <DollarSign className="w-8 h-8 opacity-80" />
          <span className="text-xs opacity-80">净流入</span>
        </div>
        <div className="text-3xl font-bold">
          {netFlow >= 0 ? '+' : ''}{(netFlow / 100000000).toFixed(2)}亿
        </div>
      </div>
      
      <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between mb-2">
          <BarChart3 className="w-8 h-8 opacity-80" />
          <span className="text-xs opacity-80">总交易额</span>
        </div>
        <div className="text-3xl font-bold">
          {((totalBuyAmount + totalSellAmount) / 100000000).toFixed(2)}亿
        </div>
      </div>
    </div>
  )
}

export default function MainForceIdentification() {
  const [activities, setActivities] = useState<MainForceActivity[]>(MOCK_MAINFORCE_ACTIVITIES)
  const [rules, setRules] = useState<MainForceRule[]>(MOCK_RULES)
  const [klineData] = useState<KLineData[]>(MOCK_KLINE_DATA)
  const [markers] = useState<MainForceMarker[]>(MOCK_MARKERS)
  const [filterStock, setFilterStock] = useState('')
  const [filterType, setFilterType] = useState<'ALL' | 'BUY' | 'SELL'>('ALL')
  const [filterDateRange, setFilterDateRange] = useState({ start: '', end: '' })
  const [showRules, setShowRules] = useState(false)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<any>(null)

  // 从API加载数据
  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      // 尝试从API获取数据，如果失败则使用默认数据
      try {
        const [activitiesData, rulesData, summaryData] = await Promise.all([
          getMainForceActivities(),
          getMainForceRules(),
          getMainForceSummary(),
        ])
        
        if (activitiesData.data.length > 0) {
          setActivities(activitiesData.data)
        }
        
        if (rulesData.length > 0) {
          setRules(rulesData)
        }
        
        if (summaryData) {
          setSummary(summaryData)
        }
      } catch (error) {
        console.warn('从API加载数据失败，使用默认数据:', error)
        // 使用默认数据
        setActivities(MOCK_MAINFORCE_ACTIVITIES)
        setRules(MOCK_RULES)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = () => {
    loadData()
  }

  const filteredActivities = activities.filter(activity => {
    if (filterStock && !activity.stock_name.includes(filterStock) && !activity.stock_code.includes(filterStock)) {
      return false
    }
    if (filterType !== 'ALL' && activity.activity_type !== filterType) {
      return false
    }
    if (filterDateRange.start && activity.date < filterDateRange.start) {
      return false
    }
    if (filterDateRange.end && activity.date > filterDateRange.end) {
      return false
    }
    return true
  })

  const handleUpdateRule = async (updatedRule: MainForceRule) => {
    try {
      await updateMainForceRule(updatedRule.id, updatedRule)
      setRules(rules.map(rule => rule.id === updatedRule.id ? updatedRule : rule))
    } catch (error) {
      console.error('更新规则失败:', error)
      alert('更新规则失败，请重试')
    }
  }

  const handleExport = () => {
    const csvContent = [
      ['日期', '股票代码', '股票名称', '活动类型', '成交量', '成交金额', '大单占比', '主力类型', '描述'],
      ...filteredActivities.map(a => [
        a.date,
        a.stock_code,
        a.stock_name,
        a.activity_type === 'BUY' ? '买入' : '卖出',
        a.volume.toString(),
        a.amount.toString(),
        (a.ratio * 100).toFixed(0) + '%',
        a.mainforce_type,
        a.description
      ])
    ].map(row => row.join(',')).join('\n')

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `主力活动报表_${new Date().toISOString().split('T')[0]}.csv`
    link.click()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 头部 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <Shield className="w-8 h-8 text-blue-600" />
                主力识别
                {loading && <span className="text-sm text-gray-500">(加载中...)</span>}
              </h1>
              <p className="text-gray-600 mt-1">识别主力资金动向，辅助风控决策</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                刷新
              </button>
              <button
                onClick={() => setShowRules(!showRules)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Settings className="w-4 h-4" />
                风控规则
              </button>
            </div>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="mb-8">
          {summary ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-4 text-white">
                <div className="flex items-center justify-between mb-2">
                  <TrendingUp className="w-8 h-8 opacity-80" />
                  <span className="text-xs opacity-80">今日买入</span>
                </div>
                <div className="text-3xl font-bold">{summary.today.buy_count}</div>
              </div>
              
              <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-lg p-4 text-white">
                <div className="flex items-center justify-between mb-2">
                  <TrendingDown className="w-8 h-8 opacity-80" />
                  <span className="text-xs opacity-80">今日卖出</span>
                </div>
                <div className="text-3xl font-bold">{summary.today.sell_count}</div>
              </div>
              
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-4 text-white">
                <div className="flex items-center justify-between mb-2">
                  <DollarSign className="w-8 h-8 opacity-80" />
                  <span className="text-xs opacity-80">净流入</span>
                </div>
                <div className="text-3xl font-bold">
                  {summary.today.net_flow >= 0 ? '+' : ''}{(summary.today.net_flow / 100000000).toFixed(2)}亿
                </div>
              </div>
              
              <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-4 text-white">
                <div className="flex items-center justify-between mb-2">
                  <BarChart3 className="w-8 h-8 opacity-80" />
                  <span className="text-xs opacity-80">活跃规则</span>
                </div>
                <div className="text-3xl font-bold">{summary.active_rules}</div>
              </div>
            </div>
          ) : (
            <MainForceStats activities={filteredActivities} />
          )}
        </div>

        {/* 风控规则面板 */}
        {showRules && (
          <div className="mb-8 bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
              主力活动告警规则配置
            </h2>
            <MainForceRulesPanel rules={rules} onUpdateRule={handleUpdateRule} />
          </div>
        )}

        {/* K线图 */}
        <div className="mb-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-600" />
            K线图标注
          </h2>
          <div className="mb-4 flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-green-500 rounded"></span>
              <span>主力买入</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-red-500 rounded"></span>
              <span>主力卖出</span>
            </div>
          </div>
          <MainForceKLineChart data={klineData} markers={markers} />
        </div>

        {/* 主力活动列表 */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-green-600" />
              主力活动列表
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExport}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
              >
                <Download className="w-4 h-4" />
                导出报表
              </button>
            </div>
          </div>

          {/* 筛选器 */}
          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">筛选条件:</span>
            </div>
            <input
              type="text"
              placeholder="搜索股票代码或名称"
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={filterStock}
              onChange={(e) => setFilterStock(e.target.value)}
            />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as 'ALL' | 'BUY' | 'SELL')}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">全部类型</option>
              <option value="BUY">买入</option>
              <option value="SELL">卖出</option>
            </select>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">日期:</span>
              <input
                type="date"
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={filterDateRange.start}
                onChange={(e) => setFilterDateRange({ ...filterDateRange, start: e.target.value })}
              />
              <span className="text-gray-400">至</span>
              <input
                type="date"
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={filterDateRange.end}
                onChange={(e) => setFilterDateRange({ ...filterDateRange, end: e.target.value })}
              />
            </div>
          </div>

          <MainForceActivityTable activities={filteredActivities} />
        </div>

        {/* 算法说明 */}
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">主力识别算法说明</h2>
          <div className="space-y-4 text-sm text-gray-600">
            <div>
              <h3 className="font-medium text-gray-900 mb-2">1. 成交量异常检测</h3>
              <p>当日成交量超过过去5日平均成交量的2倍时，标记为成交量异常。</p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2">2. 大单成交判定</h3>
              <p>单笔成交金额超过50万元视为大单，大单成交占比超过30%时判定为主力活动。</p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2">3. 主力资金流向</h3>
              <p>通过主动买入卖出判断资金流向，主动买入量大于主动卖出量时为净流入，反之为净流出。</p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2">4. 主力类型识别</h3>
              <ul className="list-disc list-inside space-y-1">
                <li><strong>机构主力：</strong>大单持续买入，持仓比例稳定增加</li>
                <li><strong>游资：</strong>短期大额买卖，换手率激增</li>
                <li><strong>散户：</strong>小单零散交易，资金分散</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

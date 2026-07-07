/**
 * 回测图表组件
 * 包含净值曲线、回撤曲线、月度收益热力图
 */
import ReactECharts from 'echarts-for-react'
import { Card, CardBody, CardHeader } from '@/components/Card'

/* ---------- 数据类型 ---------- */

/** 净值日志条目 */
interface NavLogItem {
  date: string
  nav: number
}

/** 基准净值日志条目 */
interface BenchmarkNavLogItem {
  date: string
  nav: number
}

/** 回撤日志条目 */
interface DrawdownLogItem {
  date: string
  nav: number
  peak: number
  drawdown: number
}

/** 月度收益条目 */
interface MonthlyReturnItem {
  month: string
  return: number
}

interface BacktestChartsProps {
  navLog: NavLogItem[]
  benchmarkNavLog?: BenchmarkNavLogItem[]
  drawdownLog?: DrawdownLogItem[]
  monthlyReturns?: MonthlyReturnItem[]
}

/* ---------- 净值曲线图 ---------- */

function NavChart({ navLog, benchmarkNavLog }: { navLog: NavLogItem[]; benchmarkNavLog?: BenchmarkNavLogItem[] }) {
  if (!navLog || navLog.length === 0) return null

  const dates = navLog.map((d) => d.date)
  const navValues = navLog.map((d) => d.nav)

  // 构建基准净值映射，按日期对齐
  const benchmarkMap = new Map<string, number>()
  if (benchmarkNavLog && benchmarkNavLog.length > 0) {
    for (const item of benchmarkNavLog) {
      benchmarkMap.set(item.date, item.nav)
    }
  }
  const hasBenchmark = benchmarkMap.size > 0
  const benchmarkValues = hasBenchmark
    ? dates.map((d) => benchmarkMap.get(d) ?? null)
    : []

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        let html = `<div style="font-size:12px">${params[0].axisValue}</div>`
        for (const p of params) {
          if (p.value != null) {
            html += `<div style="font-size:12px">${p.marker} ${p.seriesName}: ${Number(p.value).toLocaleString()}</div>`
          }
        }
        return html
      },
    },
    legend: {
      data: hasBenchmark ? ['策略净值', '基准净值'] : ['策略净值'],
      top: 0,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: dates,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value' as const,
      scale: true,
      axisLabel: { fontSize: 10 },
    },
    series: [
      {
        name: '策略净值',
        type: 'line',
        data: navValues,
        smooth: true,
        lineStyle: { width: 2 },
        symbol: 'none',
        itemStyle: { color: '#3b82f6' },
      },
      ...(hasBenchmark
        ? [
            {
              name: '基准净值',
              type: 'line' as const,
              data: benchmarkValues,
              smooth: true,
              lineStyle: { width: 2, type: 'dashed' as const },
              symbol: 'none',
              itemStyle: { color: '#f59e0b' },
            },
          ]
        : []),
    ],
  }

  return (
    <Card>
      <CardHeader title="净值曲线" />
      <CardBody>
        <ReactECharts option={option} style={{ height: 360 }} />
      </CardBody>
    </Card>
  )
}

/* ---------- 回撤曲线图 ---------- */

function DrawdownChart({ drawdownLog }: { drawdownLog: DrawdownLogItem[] }) {
  if (!drawdownLog || drawdownLog.length === 0) return null

  const dates = drawdownLog.map((d) => d.date)
  // 回撤值转为百分比（负数）
  const drawdownValues = drawdownLog.map((d) => +(d.drawdown * 100).toFixed(4))

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const p = params[0]
        return `<div style="font-size:12px">${p.axisValue}</div><div style="font-size:12px">${p.marker} 回撤: ${Number(p.value).toFixed(2)}%</div>`
      },
    },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: dates,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { fontSize: 10, formatter: '{value}%' },
    },
    series: [
      {
        name: '回撤',
        type: 'line',
        data: drawdownValues,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#22c55e' },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(34,197,94,0.3)' },
              { offset: 1, color: 'rgba(34,197,94,0.05)' },
            ],
          },
        },
        itemStyle: { color: '#22c55e' },
      },
    ],
  }

  return (
    <Card>
      <CardHeader title="回撤曲线" />
      <CardBody>
        <ReactECharts option={option} style={{ height: 280 }} />
      </CardBody>
    </Card>
  )
}

/* ---------- 月度收益热力图 ---------- */

function MonthlyHeatmap({ monthlyReturns }: { monthlyReturns: MonthlyReturnItem[] }) {
  if (!monthlyReturns || monthlyReturns.length === 0) return null

  // 解析月度数据为年份和月份
  const parsed = monthlyReturns.map((m) => {
    const [yearStr, monthStr] = m.month.split('-')
    return { year: parseInt(yearStr, 10), month: parseInt(monthStr, 10), value: m.return }
  })

  // 提取所有年份（去重排序）
  const years = [...new Set(parsed.map((p) => p.year))].sort()
  // 月份 1-12
  const months = Array.from({ length: 12 }, (_, i) => i + 1)

  // 构建热力图数据 [x_index, y_index, value]
  const data = parsed.map((p) => [p.month - 1, years.indexOf(p.year), +(p.value * 100).toFixed(2)])

  // 计算最大绝对值用于色阶范围
  const maxAbs = Math.max(
    Math.abs(Math.min(...parsed.map((p) => p.value))),
    Math.abs(Math.max(...parsed.map((p) => p.value))),
  ) * 100

  const option = {
    tooltip: {
      formatter: (params: any) => {
        const month = params.data[0] + 1
        const year = years[params.data[1]]
        const val = params.data[2]
        return `${year}年${month}月: ${val > 0 ? '+' : ''}${val.toFixed(2)}%`
      },
    },
    grid: { left: 60, right: 65, top: 10, bottom: 20 },
    xAxis: {
      type: 'category' as const,
      data: months.map((m) => `${m}月`),
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'category' as const,
      data: years.map(String),
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    visualMap: {
      min: -maxAbs || -10,
      max: maxAbs || 10,
      calculable: true,
      orient: 'vertical' as const,
      right: 10,
      bottom: 10,
      itemWidth: 12,
      itemHeight: 140,
      inRange: {
        color: ['#22c55e', '#f0fdf4', '#fef2f2', '#ef4444'],
      },
      textStyle: { fontSize: 10 },
      formatter: (val: number) => `${val.toFixed(1)}%`,
    },
    series: [
      {
        name: '月度收益',
        type: 'heatmap',
        data,
        label: {
          show: true,
          fontSize: 9,
          formatter: (params: any) => {
            const v = params.data[2]
            return v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)
          },
        },
        itemStyle: {
          borderWidth: 1,
          borderColor: '#fff',
        },
      },
    ],
  }

  return (
    <Card>
      <CardHeader title="月度收益热力图" />
      <CardBody>
        <ReactECharts option={option} style={{ height: 320 }} />
      </CardBody>
    </Card>
  )
}

/* ---------- 主组件 ---------- */

export default function BacktestCharts({ navLog, benchmarkNavLog, drawdownLog, monthlyReturns }: BacktestChartsProps) {
  const hasNavLog = navLog && navLog.length > 0
  const hasDrawdown = drawdownLog && drawdownLog.length > 0
  const hasMonthly = monthlyReturns && monthlyReturns.length > 0

  if (!hasNavLog && !hasDrawdown && !hasMonthly) return null

  return (
    <div className="space-y-4">
      {hasNavLog && <NavChart navLog={navLog} benchmarkNavLog={benchmarkNavLog} />}
      {hasDrawdown && <DrawdownChart drawdownLog={drawdownLog} />}
      {hasMonthly && <MonthlyHeatmap monthlyReturns={monthlyReturns} />}
    </div>
  )
}

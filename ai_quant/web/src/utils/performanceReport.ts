/**
 * 绩效报告共享工具函数
 * 供 PerformanceReport 列表页和 PerformanceReportDetail 详情页共用
 */

/** 格式化日期，截取前10位 */
export function formatDate(v: unknown) {
  if (!v) return '--'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 10) : s
}

/** 格式化百分比，保留2位小数，正数带+号 */
export function formatPct(v: number | string | undefined | null) {
  if (v == null) return '--'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/** 格式化数字，指定小数位数 */
export function formatNum(v: number | string | undefined | null, decimals: number = 2) {
  if (v == null) return '--'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(n)) return '--'
  return n.toFixed(decimals)
}

/** 构建累计收益曲线 ECharts 配置 */
export function buildEquityOption(
  equityCurve: Array<{ date: string; nav: number }>,
  benchmarkCurve?: Array<{ date: string; nav: number }>,
  initialCash?: number,
) {
  if (!equityCurve || equityCurve.length === 0) {
    return null
  }

  const baseNav = initialCash || equityCurve[0]?.nav || 1
  const dates = equityCurve.map(d => d.date.length > 10 ? d.date.slice(0, 10) : d.date)
  const strategyValues = equityCurve.map(d => parseFloat(((d.nav / baseNav) * 100).toFixed(4)))

  const series: any[] = [
    {
      name: '策略收益',
      type: 'line',
      data: strategyValues,
      smooth: true,
      lineStyle: { color: '#2563eb', width: 2 },
      areaStyle: { color: 'rgba(37,99,235,0.1)' },
      itemStyle: { color: '#2563eb' },
      symbol: 'none',
    },
  ]

  // 如果有基准数据，绘制基准曲线
  if (benchmarkCurve && benchmarkCurve.length > 0) {
    const benchBaseNav = benchmarkCurve[0]?.nav || 1
    const benchmarkValues = benchmarkCurve.map(d => parseFloat(((d.nav / benchBaseNav) * 100).toFixed(4)))
    series.push({
      name: '基准收益',
      type: 'line',
      data: benchmarkValues,
      smooth: true,
      lineStyle: { color: '#9ca3af', width: 1.5, type: 'dashed' },
      itemStyle: { color: '#9ca3af' },
      symbol: 'none',
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = params[0]?.axisValue + '<br/>'
        for (const p of params) {
          html += `${p.marker} ${p.seriesName}: ${parseFloat(p.value).toFixed(2)}%<br/>`
        }
        return html
      },
    },
    legend: { data: series.map(s => s.name), bottom: 0 },
    grid: { left: '8%', right: '5%', top: '8%', bottom: '18%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => v.toFixed(0) + '%', fontSize: 10 },
    },
    series,
  }
}

/** 构建月度收益热力图 ECharts 配置 */
export function buildMonthlyHeatmapOption(monthlyReturns: Array<{ month: string; return: number }>) {
  if (!monthlyReturns || monthlyReturns.length === 0) {
    return null
  }

  // 解析月度数据，构建 year -> { monthIndex -> return } 映射
  const yearMonthMap: Record<string, Record<number, number>> = {}
  for (const item of monthlyReturns) {
    const parts = item.month.split('-')
    if (parts.length < 2) continue
    const year = parts[0]
    const month = parseInt(parts[1], 10)
    if (!yearMonthMap[year]) yearMonthMap[year] = {}
    yearMonthMap[year][month] = item.return * 100 // 转为百分比
  }

  const years = Object.keys(yearMonthMap).sort()
  const months = Array.from({ length: 12 }, (_, i) => `${i + 1}月`)

  // 构建 ECharts heatmap 数据: [x, y, value]
  const data: Array<[number, number, number | string]> = []
  for (let yi = 0; yi < years.length; yi++) {
    for (let mi = 1; mi <= 12; mi++) {
      const val = yearMonthMap[years[yi]][mi]
      data.push([mi - 1, yi, val != null ? parseFloat(val.toFixed(2)) : '-'])
    }
  }

  // 计算颜色范围
  let minVal = 0
  let maxVal = 0
  for (const item of data) {
    const v = item[2]
    if (typeof v === 'number') {
      if (v < minVal) minVal = v
      if (v > maxVal) maxVal = v
    }
  }
  const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal), 1)

  return {
    tooltip: {
      formatter: (params: any) => {
        const val = params.value[2]
        return `${years[params.value[1]]}年 ${months[params.value[0]]}<br/>收益率: ${typeof val === 'number' ? (val >= 0 ? '+' : '') + val.toFixed(2) + '%' : '--'}`
      },
    },
    grid: { left: '12%', right: '12%', top: '5%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: months,
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: years,
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    visualMap: {
      min: -absMax,
      max: absMax,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#c23531', '#f4e8c1', '#61a0a8'],
      },
      textStyle: { fontSize: 10 },
      formatter: (v: number) => v.toFixed(1) + '%',
    },
    series: [
      {
        type: 'heatmap',
        data: data,
        label: {
          show: true,
          fontSize: 9,
          formatter: (params: any) => {
            const v = params.value[2]
            return typeof v === 'number' ? v.toFixed(1) : ''
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
        },
      },
    ],
  }
}

/** 构建回撤水下图 ECharts 配置 */
export function buildDrawdownOption(drawdownCurve: Array<{ date: string; drawdown: number }>) {
  if (!drawdownCurve || drawdownCurve.length === 0) {
    return null
  }

  const dates = drawdownCurve.map(d => d.date.length > 10 ? d.date.slice(0, 10) : d.date)
  const values = drawdownCurve.map(d => parseFloat((d.drawdown * 100).toFixed(4)))

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        return `${p.axisValue}<br/>回撤: ${parseFloat(p.value).toFixed(2)}%`
      },
    },
    grid: { left: '8%', right: '5%', top: '8%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => v.toFixed(0) + '%', fontSize: 10 },
    },
    series: [
      {
        name: '回撤',
        type: 'line',
        data: values,
        smooth: false,
        lineStyle: { color: '#c23531', width: 1.5 },
        itemStyle: { color: '#c23531' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(194,53,49,0.3)' },
              { offset: 1, color: 'rgba(194,53,49,0.05)' },
            ],
          },
        },
        symbol: 'none',
      },
    ],
  }
}

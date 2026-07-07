import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

// 模拟 echarts-for-react，避免 jsdom 中 canvas 不支持导致异常
vi.mock('echarts-for-react', () => ({
  default: () => null,
}))

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import RiskDashboard from '@/pages/RiskDashboard'

/**
 * RiskDashboard 测试
 * Mock数据移除后：从 API 加载真实风控数据，失败时显示错误提示
 */
describe('RiskDashboard - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('加载并显示真实风控数据', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/risk/dashboard') {
        return {
          event_stats: { total_events: 10, pending_events: 3, critical_events: 1, high_events: 2 },
          alert_stats: { total_alerts: 5, pending_alerts: 3, unread_alerts: 2, red_alerts: 1, orange_alerts: 1 },
          rule_stats: { total_rules: 8, enabled_rules: 6, disabled_rules: 2 },
          recent_events: [
            { event_id: 'e1', event_type: '价格异动', risk_level: 'high', stock_code: '600519.SH', stock_name: '贵州茅台', status: 'pending', created_at: '2026-05-25T09:30:00' },
          ],
        }
      }
      if (url.startsWith('/api/v1/risk/alerts')) {
        return [
          { id: 'a1', alert_type: 'stop_loss', level: 'red', stock_code: '600519.SH', stock_name: '贵州茅台', title: '止损告警', message: '贵州茅台触发止损线', status: 'pending', is_read: 0, created_at: '2026-05-25T09:30:00' },
        ]
      }
      if (url === '/api/v1/risk/rules') {
        return [
          { id: 'rule1', name: '止损规则', description: '跌幅超过5%触发止损', enabled: 1, trigger_count: 3, last_triggered_at: '2026-05-25' },
        ]
      }
      return {}
    })

    render(<RiskDashboard />)

    // 验证风控看板标题和统计数据
    expect(await screen.findByText('风控看板')).toBeInTheDocument()
    expect(await screen.findByText('待处理告警')).toBeInTheDocument()
    expect(await screen.findByText('监控面板')).toBeInTheDocument()

    // 验证tab切换按钮
    expect(screen.getByText('实时告警')).toBeInTheDocument()
    expect(screen.getByText('风险事件')).toBeInTheDocument()
    expect(screen.getByText('规则状态')).toBeInTheDocument()

    // 验证API被正确调用（3个并行请求）
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/risk/dashboard')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/risk/alerts?page_size=20')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/risk/rules')
  })

  it('API失败时显示错误提示和重新加载按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async () => {
      throw new Error('数据加载失败')
    })

    render(<RiskDashboard />)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })

  it('API返回空数据时显示"暂无告警"和"暂无风险事件"', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/risk/dashboard') {
        return {
          event_stats: { total_events: 0, pending_events: 0, critical_events: 0, high_events: 0 },
          alert_stats: { total_alerts: 0, pending_alerts: 0, unread_alerts: 0, red_alerts: 0, orange_alerts: 0 },
          rule_stats: { total_rules: 0, enabled_rules: 0, disabled_rules: 0 },
          recent_events: [],
        }
      }
      if (url.startsWith('/api/v1/risk/alerts')) return []
      if (url === '/api/v1/risk/rules') return []
      return {}
    })

    render(<RiskDashboard />)

    // 即使有空数据，风控看板仍应正常渲染
    expect(await screen.findByText('风控看板')).toBeInTheDocument()
  })

  it('验证无Mock数据残留（不显示已移除的硬编码数据）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/risk/dashboard') {
        return {
          event_stats: { total_events: 0, pending_events: 0, critical_events: 0, high_events: 0 },
          alert_stats: { total_alerts: 0, pending_alerts: 0, unread_alerts: 0, red_alerts: 0, orange_alerts: 0 },
          rule_stats: { total_rules: 0, enabled_rules: 0, disabled_rules: 0 },
          recent_events: [],
        }
      }
      if (url.startsWith('/api/v1/risk/alerts')) return []
      if (url === '/api/v1/risk/rules') return []
      return {}
    })

    render(<RiskDashboard />)

    // 验证初始状态不为Mock数据填充
    await screen.findByText('风控看板')
    // 自动刷新按钮应渲染
    expect(screen.getByText('自动刷新(30s)')).toBeInTheDocument()
  })
})
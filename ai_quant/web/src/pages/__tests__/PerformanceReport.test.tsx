import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import PerformanceReport from '@/pages/PerformanceReport'

/**
 * PerformanceReport 测试
 * Mock数据移除后：从 API 加载真实绩效报告数据，移除 Math.random() 残留
 */
describe('PerformanceReport - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('加载并显示真实绩效报告列表', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/performance/list') {
        return {
          items: [
            { id: 1, report_id: 'rp1', report_type: 'common', account_id: 1, strategy_name: '均线策略', initial_cash: 1000000, total_return: 12.5, annualized_return: 15.3, max_drawdown: -8.2, volatility: 18.5, sharpe_ratio: 1.85, total_trades: 48, winning_trades: 30, losing_trades: 18, win_rate: 62.5, profit_factor: 1.8, avg_profit: 5200, avg_loss: -2800, trading_days: 120, status: 'completed', created_at: '2026-05-25' },
          ],
          total: 1,
        }
      }
      return {}
    })

    render(<PerformanceReport />)

    expect(await screen.findByText('绩效报告')).toBeInTheDocument()
    expect(await screen.findByText('均线策略')).toBeInTheDocument()
    expect(await screen.findByText('已完成')).toBeInTheDocument()
    // 验证统计卡片
    expect(await screen.findByText('报告总数')).toBeInTheDocument()
    expect(await screen.findByText('平均收益率')).toBeInTheDocument()
    expect(await screen.findByText('平均夏普比率')).toBeInTheDocument()
    expect(await screen.findByText('盈利策略数')).toBeInTheDocument()
    // 验证API被正确调用
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/performance/list')
  })

  it('API失败时显示错误提示和重新加载按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async () => {
      throw new Error('数据加载失败')
    })

    render(<PerformanceReport />)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })

  it('API返回空数据时显示"暂无绩效报告"提示', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/performance/list') {
        return { items: [], total: 0 }
      }
      return {}
    })

    render(<PerformanceReport />)

    expect(await screen.findByText('暂无绩效报告，点击"生成报告"创建')).toBeInTheDocument()
  })

  it('验证无Math.random()数据残留', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/performance/list') {
        return {
          items: [
            { id: 1, report_id: 'rp1', report_type: 'plus', account_id: 1, strategy_name: '均线策略', initial_cash: 1000000, total_return: 12.5, annualized_return: 15.3, max_drawdown: -8.2, volatility: 18.5, sharpe_ratio: 1.85, calmar_ratio: 1.52, win_rate: 62.5, profit_factor: 1.8, total_trades: 48, winning_trades: 30, losing_trades: 18, trading_days: 120, avg_profit: 5200, avg_loss: -2800, final_nav: 1.125, status: 'completed', created_at: '2026-05-25' },
          ],
          total: 1,
        }
      }
      return {}
    })

    render(<PerformanceReport />)

    // 验证报告列表正常展示真实数据
    expect(await screen.findByText('均线策略')).toBeInTheDocument()
    // 验证总收益率显示来自API的数据（12.5%）
    const totalReturns = screen.getAllByText('+12.50%')
    expect(totalReturns.length).toBeGreaterThan(0)
  })

  it('验证无Mock数据残留（初始状态为空列表）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/performance/list') {
        return { items: [], total: 0 }
      }
      return {}
    })

    render(<PerformanceReport />)

    // 初始加载完成后应显示空状态，而非硬编码Mock数据
    expect(await screen.findByText('暂无绩效报告，点击"生成报告"创建')).toBeInTheDocument()
    // 生成报告按钮应渲染
    expect(screen.getByText('生成报告')).toBeInTheDocument()
  })
})
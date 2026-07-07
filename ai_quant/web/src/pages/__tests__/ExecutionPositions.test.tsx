import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import ExecutionPositions from '@/pages/ExecutionPositions'

/**
 * ExecutionPositions 测试
 * Mock数据移除后：从 API 加载真实持仓数据，失败时显示错误提示
 */
describe('ExecutionPositions - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('加载并显示真实持仓数据', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/positions') {
        return {
          positions: [
            { code: '600519.SH', name: '贵州茅台', qty: 100, avgCost: 1800, currentPrice: 1850, marketValue: 185000, profitLoss: 5000, profitPct: 2.78, weight: 30, sector: '食品饮料', account: '实盘' },
            { code: '000858.SZ', name: '五粮液', qty: 200, avgCost: 150, currentPrice: 148, marketValue: 29600, profitLoss: -400, profitPct: -1.33, weight: 10, sector: '食品饮料', account: '模拟盘' },
          ],
          total: 2,
        }
      }
      return {}
    })

    render(<ExecutionPositions />)

    expect(await screen.findByText('持仓明细')).toBeInTheDocument()
    expect(await screen.findByText('600519.SH')).toBeInTheDocument()
    expect(await screen.findByText('贵州茅台')).toBeInTheDocument()
    expect(await screen.findByText('实盘')).toBeInTheDocument()
    expect(await screen.findByText('模拟盘')).toBeInTheDocument()
    // 验证API被正确调用
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/execution/positions')
  })

  it('API失败时显示错误提示和重新加载按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async () => {
      throw new Error('数据加载失败')
    })

    render(<ExecutionPositions />)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })

  it('API返回空数据时显示"暂无持仓数据"', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/positions') {
        return { positions: [], total: 0 }
      }
      return {}
    })

    render(<ExecutionPositions />)

    expect(await screen.findByText('暂无持仓数据')).toBeInTheDocument()
  })

  it('验证无Mock数据残留（空数据时不渲染表格内容）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/positions') {
        return { positions: [], total: 0 }
      }
      return {}
    })

    render(<ExecutionPositions />)

    // 空数据时显示"暂无持仓数据"，不显示表格相关元素
    expect(await screen.findByText('暂无持仓数据')).toBeInTheDocument()
    // 使用loading图标验证初始loading状态已结束
    expect(screen.queryByText('加载中...')).toBeNull()
  })
})
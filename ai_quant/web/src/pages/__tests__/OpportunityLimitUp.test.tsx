import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import OpportunityLimitUp from '@/pages/OpportunityLimitUp'

/**
 * OpportunityLimitUp 测试
 * Mock数据移除后：从 intraday API 加载实时涨停数据，失败时显示错误提示
 */
describe('OpportunityLimitUp - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('加载并显示真实涨停数据', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/intraday/limit-up') {
        return {
          items: [
            { code: '600519.SH', name: '贵州茅台', boardTime: '09:25', sealAmount: 1200, sealAmountY: 3.6, consecutiveBoards: 2, floatCap: 2500, sector: '食品饮料', status: 'limit_up', firstBoardTime: '2026-05-24' },
            { code: '000858.SZ', name: '五粮液', boardTime: '09:30', sealAmount: 800, sealAmountY: 2.4, consecutiveBoards: 1, floatCap: 800, sector: '食品饮料', status: 'limit_up', firstBoardTime: '2026-05-25' },
          ],
          total: 2,
        }
      }
      return {}
    })

    render(<OpportunityLimitUp />)

    expect(await screen.findByText('600519.SH')).toBeInTheDocument()
    expect(await screen.findByText('贵州茅台')).toBeInTheDocument()
    expect(await screen.findByText('涨停板（2 只）')).toBeInTheDocument()
    expect(await screen.findByText('2连板')).toBeInTheDocument()
    // 验证API被正确调用
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/intraday/limit-up')
  })

  it('API失败时显示错误提示和重新加载按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async () => {
      throw new Error('数据加载失败')
    })

    render(<OpportunityLimitUp />)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })

  it('API返回空数据时显示"暂无涨停数据"', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/intraday/limit-up') {
        return { items: [], total: 0 }
      }
      return {}
    })

    render(<OpportunityLimitUp />)

    expect(await screen.findByText('暂无涨停数据')).toBeInTheDocument()
  })

  it('验证无Mock数据残留（空数据时只显示空状态）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/intraday/limit-up') {
        return { items: [], total: 0 }
      }
      return {}
    })

    render(<OpportunityLimitUp />)

    // 空数据时显示"暂无涨停数据"，视图按钮不渲染
    expect(await screen.findByText('暂无涨停数据')).toBeInTheDocument()
    // 验证loading状态已结束
    expect(screen.queryByText('加载中...')).toBeNull()
  })

  it('兼容数组格式的API响应', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/intraday/limit-up') {
        return [
          { code: '600519.SH', name: '贵州茅台', boardTime: '09:25', sealAmount: 1200, sealAmountY: 3.6, consecutiveBoards: 1, floatCap: 2500, sector: '食品饮料', status: 'limit_up', firstBoardTime: '2026-05-25' },
        ]
      }
      return {}
    })

    render(<OpportunityLimitUp />)

    expect(await screen.findByText('600519.SH')).toBeInTheDocument()
    // 验证直接返回数组也能正确渲染
    expect(await screen.findByText('涨停板（1 只）')).toBeInTheDocument()
  })
})
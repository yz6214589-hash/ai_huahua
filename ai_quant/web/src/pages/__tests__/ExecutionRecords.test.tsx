import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import ExecutionRecords from '@/pages/ExecutionRecords'

/**
 * ExecutionRecords 测试
 * Mock数据移除后：从 API 加载真实交易记录，失败时显示错误提示
 */
describe('ExecutionRecords - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('加载并显示真实交易记录', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/records') {
        return {
          records: [
            { id: 'r1', timestamp: '2026-05-25T09:30:00', symbol: '600519.SH', name: '贵州茅台', side: 'buy', qty: 100, price: 1850, amount: 185000, strategy: 'twap', status: 'filled', account: '实盘', remark: '开盘买入' },
            { id: 'r2', timestamp: '2026-05-25T10:00:00', symbol: '000858.SZ', name: '五粮液', side: 'sell', qty: 200, price: 148, amount: 29600, strategy: 'vwap', status: 'filled', account: '模拟盘' },
          ],
          total: 2,
        }
      }
      return {}
    })

    render(<ExecutionRecords />)

    expect(await screen.findByText('交易明细')).toBeInTheDocument()
    expect(await screen.findByText('600519.SH')).toBeInTheDocument()
    expect(await screen.findByText('贵州茅台')).toBeInTheDocument()
    expect(await screen.findByText('买入')).toBeInTheDocument()
    expect(await screen.findByText('卖出')).toBeInTheDocument()
    // 验证API被正确调用
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/execution/records')
  })

  it('API失败时显示错误提示和重新加载按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async () => {
      throw new Error('数据加载失败')
    })

    render(<ExecutionRecords />)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })

  it('API返回空数据时显示"暂无交易记录"', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/records') {
        return { records: [], total: 0 }
      }
      return {}
    })

    render(<ExecutionRecords />)

    // 过滤后列表为空，表格内显示"暂无交易记录"
    expect(await screen.findByText('暂无交易记录')).toBeInTheDocument()
  })

  it('验证无Mock数据残留（初始状态不为Mock填充）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/execution/records') {
        return { records: [], total: 0 }
      }
      return {}
    })

    render(<ExecutionRecords />)

    // 初始加载应有loading状态，完成后显示空状态
    expect(await screen.findByText('暂无交易记录')).toBeInTheDocument()
    // 验证筛选按钮正常渲染
    expect(screen.getByText('全部方向')).toBeInTheDocument()
    expect(screen.getByText('仅买入')).toBeInTheDocument()
    expect(screen.getByText('仅卖出')).toBeInTheDocument()
  })
})
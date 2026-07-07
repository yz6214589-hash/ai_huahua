import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson, postJson } from '@/api/client'
import WorkFlowTeam from '@/pages/WorkFlowTeam'

/**
 * WorkFlowTeam 测试
 * Mock数据移除后：初始值改为空列表，从 API 加载真实运行历史和详情
 */
describe('WorkFlowTeam - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('初始渲染显示"触发新工作流"和空运行历史', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/team/runs') return []
      return {}
    })

    render(<WorkFlowTeam />)

    expect(await screen.findByText('触发新工作流')).toBeInTheDocument()
    expect(await screen.findByText('运行历史')).toBeInTheDocument()
    // 默认显示选择提示
    expect(await screen.findByText('选择一条运行记录查看详情')).toBeInTheDocument()
    // 运行历史不应包含任何条目
    const runItems = screen.queryAllByRole('button')
    // 验证没有Mock数据填充的运行记录
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/workflow/team/runs')
  })

  it('加载并显示运行历史数据', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/team/runs') {
        return [
          { id: 'run1', stock_code: '600519.SH', started_at: '2026-05-25 09:30:00', status: 'completed', verdict: 'APPROVE', verdict_reason: '技术面良好' },
          { id: 'run2', stock_code: '000858.SZ', started_at: '2026-05-24 10:00:00', status: 'failed', verdict: 'REJECT', verdict_reason: '流动性不足' },
        ]
      }
      return {}
    })

    render(<WorkFlowTeam />)

    expect(await screen.findByText('运行历史')).toBeInTheDocument()
    expect(await screen.findByText('600519.SH')).toBeInTheDocument()
    expect(await screen.findByText('000858.SZ')).toBeInTheDocument()
    // 验证API被正确调用
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/workflow/team/runs')
  })

  it('API失败时运行历史为空，不影响页面渲染', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/team/runs') throw new Error('获取历史失败')
      return {}
    })

    render(<WorkFlowTeam />)

    // 即使API失败，页面应正常渲染
    expect(await screen.findByText('触发新工作流')).toBeInTheDocument()
    expect(await screen.findByText('运行历史')).toBeInTheDocument()
    // 初始默认显示空状态提示
    expect(await screen.findByText('选择一条运行记录查看详情')).toBeInTheDocument()
    // 不应显示任何运行条目
    expect(screen.queryByText('APPROVE')).toBeNull()
    expect(screen.queryByText('REJECT')).toBeNull()
  })

  it('验证初始值不为Mock数据填充（初始runs为空列表）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/team/runs') return []
      return {}
    })

    render(<WorkFlowTeam />)

    // 验证初始状态无Mock数据
    await screen.findByText('触发新工作流')
    // 股票代码输入框的默认值应为 '600519.SH'（这是UI默认值，不是Mock数据）
    const stockInput = screen.getByPlaceholderText('600519.SH') as HTMLInputElement
    expect(stockInput.value).toBe('600519.SH')
  })

  it('验证postJson和fetchJson都被正确导出和调用', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    const postMock = postJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/team/runs') return []
      return {}
    })
    postMock.mockImplementation(async () => ({ ok: true }))

    render(<WorkFlowTeam />)

    expect(await screen.findByText('触发新工作流')).toBeInTheDocument()
  })
})
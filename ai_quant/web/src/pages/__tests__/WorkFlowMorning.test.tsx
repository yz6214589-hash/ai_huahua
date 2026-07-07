import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson, postJson } from '@/api/client'
import WorkFlowMorning from '@/pages/WorkFlowMorning'

/**
 * WorkFlowMorning 测试
 * Mock数据移除后：晨报工作流使用API返回的真实结果，定时器仅做UI动画
 */
describe('WorkFlowMorning - Mock数据移除后', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('初始渲染显示配置参数和"立即生成晨报"按钮', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/morning/history') return []
      return {}
    })

    render(<WorkFlowMorning />)

    // 验证配置参数区域
    expect(await screen.findByText('晨报参数配置')).toBeInTheDocument()
    expect(await screen.findByText('立即生成晨报')).toBeInTheDocument()
    // 验证阶段流水线
    expect(screen.getByText('板块轮动分析')).toBeInTheDocument()
    expect(screen.getByText('多因子选股')).toBeInTheDocument()
    expect(screen.getByText('生成晨报')).toBeInTheDocument()
    expect(screen.getByText('推送通知')).toBeInTheDocument()
    // 初始渲染时result为null，历史晨报卡片不显示
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/workflow/morning/history')
  })

  it('API返回空历史记录时历史数据为空数组', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/morning/history') return []
      return {}
    })

    render(<WorkFlowMorning />)

    // 验证历史API被调用
    await screen.findByText('晨报参数配置')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/workflow/morning/history')
    // 初始时result为null，历史晨报卡片不渲染
    expect(screen.queryByText('历史晨报')).toBeNull()
  })

  it('验证无Mock数据残留（初始result为null）', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/morning/history') return []
      return {}
    })

    render(<WorkFlowMorning />)

    // 初始状态不应显示晨报结果
    await screen.findByText('每日 9:00 自动生成开盘前简报')
    // 不应显示与Mock数据相关的文本（如推送结果、板块排名等）
    expect(screen.queryByText('强势板块')).toBeNull()
    expect(screen.queryByText('选中标的')).toBeNull()
    expect(screen.queryByText('已推送至')).toBeNull()
  })

  it('历史API失败时不影响页面渲染', async () => {
    const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/v1/workflow/morning/history') throw new Error('获取历史失败')
      return {}
    })

    render(<WorkFlowMorning />)

    // 即使历史API失败，页面仍应正常渲染配置区域
    expect(await screen.findByText('晨报参数配置')).toBeInTheDocument()
    expect(screen.getByText('立即生成晨报')).toBeInTheDocument()
  })
})
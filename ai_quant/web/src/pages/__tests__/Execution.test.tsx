import { render, screen } from '@testing-library/react'
import { act, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson, postJson } from '@/api/client'
import Execution from '@/pages/Execution'

test('Execution 展示失败原因', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/execution/status') return { source: 'ethan', status: 'ready', features: ['tasks'] }
    if (url === '/api/execution/tasks')
      return { items: [{ id: 't1', symbol: '600519.SH', side: 'buy', total_qty: 100, num_steps: 48, strategy: 'twap', adv: 1, impact_eta: 0.1, impact_gamma: 0.05, constraints: {}, status: 'failed', created_at: '', error: '执行失败原因示例' }] }
    return {}
  })

  render(
    <MemoryRouter initialEntries={['/execution']}>
      <Routes>
        <Route path="/execution" element={<Execution />} />
      </Routes>
    </MemoryRouter>
  )

  expect(await screen.findByText('执行失败原因示例')).toBeInTheDocument()
})

test('Execution 创建任务失败时显示错误', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/execution/status') return { source: 'ethan', status: 'ready', features: ['tasks'] }
    if (url === '/api/execution/tasks') return { items: [] }
    return {}
  })

  const postMock = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  postMock.mockImplementation(async () => {
    throw new Error('bad request')
  })

  render(
    <MemoryRouter initialEntries={['/execution']}>
      <Routes>
        <Route path="/execution" element={<Execution />} />
      </Routes>
    </MemoryRouter>
  )

  await screen.findByText('执行监控')
  act(() => {
    fireEvent.change(screen.getByPlaceholderText('例如 600519.SH'), { target: { value: '600519.SH' } })
    fireEvent.click(screen.getByRole('button', { name: '创建任务' }))
  })

  expect(await screen.findByText('bad request')).toBeInTheDocument()
})

test('Execution 股票代码为空时阻止提交', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/execution/status') return { source: 'ethan', status: 'ready', features: ['tasks'] }
    if (url === '/api/execution/tasks') return { items: [] }
    return {}
  })

  const postMock = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  postMock.mockImplementation(async () => ({ ok: true }))

  render(
    <MemoryRouter initialEntries={['/execution']}>
      <Routes>
        <Route path="/execution" element={<Execution />} />
      </Routes>
    </MemoryRouter>
  )

  await screen.findByText('执行监控')
  act(() => {
    fireEvent.click(screen.getByRole('button', { name: '创建任务' }))
  })

  expect(await screen.findByText('请填写股票代码')).toBeInTheDocument()
})

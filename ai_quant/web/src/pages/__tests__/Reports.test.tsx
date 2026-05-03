import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson, postJson } from '@/api/client'
import Reports from '@/pages/Reports'

function setup(fetchImpl: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = fetchJson as unknown as {
    mockImplementation: (fn: (url: string, init?: RequestInit) => Promise<unknown>) => unknown
  }
  const postMock = postJson as unknown as {
    mockImplementation: (fn: (url: string, body: unknown) => Promise<unknown>) => unknown
  }
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => fetchImpl(url, init))
  postMock.mockImplementation(async () => ({ task: { task_id: 't1', model: 'qwen-max', stock_codes: ['600000.SH'], stock_names: ['浦发银行'], status: 'waiting', created_at: '2026-05-02T00:00:00Z' } }))

  return render(
    <MemoryRouter initialEntries={['/reports']}>
      <Routes>
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </MemoryRouter>
  )
}

test('reports 页面可创建任务', async () => {
  setup((url) => {
    if (url.startsWith('/api/reports/tasks')) return { tasks: [] }
    if (url.startsWith('/api/stocks?q=')) return { items: [{ code: '600000.SH', name: '浦发银行' }] }
    return {}
  })

  expect(await screen.findByText('智能研报')).toBeInTheDocument()

  const input = screen.getByPlaceholderText('搜索股票代码/名称')
  await userEvent.type(input, '600')
  expect(await screen.findByText('600000.SH')).toBeInTheDocument()
  await userEvent.click(screen.getByText('添加'))

  await userEvent.click(screen.getByText('创建研报任务'))

  await waitFor(() => expect(postJson).toHaveBeenCalled())
})


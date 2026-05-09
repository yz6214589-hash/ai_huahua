import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
    fetchText: vi.fn(),
  }
})

import { fetchJson, postJson, fetchText } from '@/api/client'
import Reports from '@/pages/Reports'

function setup(fetchImpl: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = fetchJson as unknown as {
    mockImplementation: (fn: (url: string, init?: RequestInit) => Promise<unknown>) => unknown
  }
  const postMock = postJson as unknown as {
    mockImplementation: (fn: (url: string, body: unknown) => Promise<unknown>) => unknown
  }
  const textMock = fetchText as unknown as {
    mockImplementation: (fn: (url: string, init?: RequestInit) => Promise<unknown>) => unknown
  }
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => fetchImpl(url, init))
  postMock.mockImplementation(async () => ({ task: { task_id: 't1', model: 'qwen-max', stock_codes: ['600000.SH'], stock_names: ['浦发银行'], status: 'waiting', created_at: '2026-05-02T00:00:00Z' } }))
  textMock.mockImplementation(async () => '# 标题\n\n内容\n')

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

  const input = screen.getByPlaceholderText('下拉选择 / 搜索股票代码或名称')
  await userEvent.type(input, '600')
  expect(await screen.findByText('600000.SH')).toBeInTheDocument()
  await userEvent.click(screen.getByText('选择'))

  await userEvent.click(screen.getByText('创建研报任务'))

  await waitFor(() => expect(postJson).toHaveBeenCalled())
})

test('reports：失败/运行中任务点击查看用 toast 提示且不打开新页面', async () => {
  const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

  setup((url) => {
    if (url.startsWith('/api/reports/tasks')) {
      return {
        tasks: [
          { task_id: 't_failed', model: 'qwen-max', stock_codes: ['600000.SH'], stock_names: ['浦发银行'], status: 'failed', created_at: '2026-05-02T00:00:00Z', error_message: 'boom' },
          { task_id: 't_running', model: 'qwen-max', stock_codes: ['600000.SH'], stock_names: ['浦发银行'], status: 'running', created_at: '2026-05-02T00:00:00Z' },
        ],
      }
    }
    if (url.startsWith('/api/stocks?q=')) return { items: [] }
    return {}
  })

  expect(await screen.findByText('任务列表')).toBeInTheDocument()

  const viewButtons = await screen.findAllByText('查看')
  await userEvent.click(viewButtons[0])
  expect(await screen.findByText('任务失败：boom')).toBeInTheDocument()

  await userEvent.click(viewButtons[1])
  expect(await screen.findByText('任务仍在运行中，请稍后再试')).toBeInTheDocument()

  expect(openSpy).not.toHaveBeenCalled()
  openSpy.mockRestore()
})

test('reports：成功任务点击查看在页面内渲染 markdown', async () => {
  setup((url) => {
    if (url.startsWith('/api/reports/tasks')) {
      return {
        tasks: [{ task_id: 't_ok', model: 'qwen-max', stock_codes: ['600000.SH'], stock_names: ['浦发银行'], status: 'success', created_at: '2026-05-02T00:00:00Z' }],
      }
    }
    if (url.startsWith('/api/stocks?q=')) return { items: [] }
    return {}
  })

  await userEvent.click(await screen.findByText('查看'))
  expect(await screen.findByText('标题')).toBeInTheDocument()
})

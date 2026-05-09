import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import Strategy from '@/pages/Strategy'

test('Strategy 无信号时显示引导提示', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/analysis/status') return { source: 'zoe', status: 'ready', features: ['signals'] }
    if (url.startsWith('/api/analysis/stocks/sample')) return { codes: ['600519.SH'] }
    if (url.startsWith('/api/analysis/signals')) return { stock_code: '600519.SH', signals: [] }
    if (url.startsWith('/api/stocks')) return { items: [] }
    return {}
  })

  render(
    <MemoryRouter initialEntries={['/strategy']}>
      <Routes>
        <Route path="/strategy" element={<Strategy />} />
      </Routes>
    </MemoryRouter>
  )

  await screen.findByText('信号结果')
  fireEvent.click(screen.getByText('600519.SH'))
  await screen.findByText('当前选择')
  await Promise.resolve()
  await act(async () => {
    fireEvent.click(screen.getByText('生成信号'))
    await Promise.resolve()
  })

  expect(await screen.findByText('暂无信号数据，请先配置数据源')).toBeInTheDocument()
})

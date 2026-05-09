import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import Dashboard from '@/pages/Dashboard'

test('Dashboard 首次访问显示新手引导', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async () => {
    return {
      data_latest: {
        trade_stock_daily: { count: 0, latest: null },
        trade_stock_financial: { count: 0, latest: null },
        trade_stock_news: { count: 0, latest: null },
        trade_calendar_event: { count: 0, latest: null },
      },
      recent_jobs: [],
      execution_status: { status: 'unknown', features: [] },
      risk_status: { status: 'unknown', features: [] },
      morning: { run_count: 0, last_run: null },
    }
  })

  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
      </Routes>
    </MemoryRouter>
  )

  expect(await screen.findByText('新手引导')).toBeInTheDocument()
})


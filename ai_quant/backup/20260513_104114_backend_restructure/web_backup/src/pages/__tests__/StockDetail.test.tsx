import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import StockDetail from '@/pages/StockDetail'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(async (url: string) => {
      if (url.includes('/snapshot')) return { stock_code: '600000.SH', stock_name: '浦发银行', price: 10, change: 0.1, pctChange: 1, asOf: new Date().toISOString(), source: 'db' }
      if (url.includes('/fundamentals')) return { stock_code: '600000.SH', stock_name: '浦发银行', reportDate: '2025-12-31', items: [] }
      if (url.includes('/technical/latest')) return { stock_code: '600000.SH', row: null }
      if (url.includes('/technical/series')) return { stock_code: '600000.SH', rows: [] }
      if (url.includes('/feed')) return { tab: 'news', page: 1, pageSize: 5, total: 0, items: [] }
      return {}
    }),
  }
})

test('stock detail 空数据占位', async () => {
  render(
    <MemoryRouter initialEntries={['/stock/600000.SH']}>
      <Routes>
        <Route path="/stock/:code" element={<StockDetail />} />
      </Routes>
    </MemoryRouter>
  )

  expect((await screen.findAllByText('基本面')).length).toBeGreaterThan(0)
  expect(await screen.findByText('暂无数据')).toBeInTheDocument()
})


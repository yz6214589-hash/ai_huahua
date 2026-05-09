import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson } from '@/api/client'
import Risk from '@/pages/Risk'

test('Risk 空审计记录时显示占位提示', async () => {
  const fetchMock = fetchJson as unknown as { mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown }
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/risk/status') return { source: 'kris', status: 'ready', features: ['approve', 'audit'] }
    if (url.startsWith('/api/risk/audit')) return { items: [] }
    return {}
  })

  render(
    <MemoryRouter initialEntries={['/risk']}>
      <Routes>
        <Route path="/risk" element={<Risk />} />
      </Routes>
    </MemoryRouter>
  )

  expect(await screen.findByText('暂无待审批订单')).toBeInTheDocument()
})


import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Watchlist from '@/pages/Watchlist'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    fetchJson: vi.fn(),
    postJson: vi.fn(),
  }
})

import { fetchJson, postJson } from '@/api/client'

function setup(fetchImpl: (url: string) => unknown) {
  const fetchMock = fetchJson as unknown as {
    mockImplementation: (fn: (url: string) => Promise<unknown>) => unknown
  }
  const postMock = postJson as unknown as {
    mockResolvedValue: (v: unknown) => unknown
  }
  fetchMock.mockImplementation(async (url: string) => fetchImpl(url))
  postMock.mockResolvedValue({ ok: true })
  return render(
    <MemoryRouter initialEntries={['/watchlist']}>
      <Routes>
        <Route path="/watchlist" element={<Watchlist />} />
      </Routes>
    </MemoryRouter>
  )
}

test('watchlist 搜索并添加', async () => {
  setup((url) => {
    if (url === '/api/watchlist') return { items: [], max: 50 }
    if (url.startsWith('/api/stocks?q=')) return { items: [{ code: '600000.SH', name: '浦发银行' }] }
    return {}
  })

  expect(await screen.findByText('暂无自选股')).toBeInTheDocument()

  const input = screen.getByPlaceholderText('按代码/名称搜索，例如 600 或 贵州')
  await userEvent.type(input, '600')

  expect(await screen.findByText('600000.SH')).toBeInTheDocument()
  await userEvent.click(screen.getByText('添加'))

  await waitFor(() => expect(postJson).toHaveBeenCalledWith('/api/watchlist', { stock_code: '600000.SH' }))
})


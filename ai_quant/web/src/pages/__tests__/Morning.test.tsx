import { render, screen } from '@testing-library/react'
import { act, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    postJson: vi.fn(),
  }
})

import { postJson } from '@/api/client'
import Morning from '@/pages/Morning'

test('Morning 运行中显示进度与耗时', async () => {
  vi.useFakeTimers()

  let resolveReq: ((v: unknown) => void) | null = null
  const pending = new Promise((r) => {
    resolveReq = r
  })
  const post = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  post.mockImplementation(async () => pending)

  render(
    <MemoryRouter initialEntries={['/morning']}>
      <Routes>
        <Route path="/morning" element={<Morning />} />
      </Routes>
    </MemoryRouter>
  )

  act(() => {
    fireEvent.click(screen.getByText('生成晨会简报'))
  })
  expect(screen.getByText('运行中...')).toBeInTheDocument()

  act(() => {
    vi.advanceTimersByTime(1500)
  })
  await Promise.resolve()
  expect(screen.getByText(/已运行/)).toBeInTheDocument()

  await act(async () => {
    resolveReq?.({ ok: true, workflow: 'ai_quant.morning_brief', result: { report_md: '', report_html: '', messages: [], picked_stocks: [], industry_rank: [] } })
    await Promise.resolve()
  })
  vi.useRealTimers()
})

import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/api/client', () => {
  return {
    postJson: vi.fn(),
  }
})

import { postJson } from '@/api/client'
import Chat from '@/pages/Chat'

test('Chat 后端异常时显示友好错误', async () => {
  const post = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  post.mockImplementation(async () => {
    throw new Error('server down')
  })

  render(
    <MemoryRouter initialEntries={['/chat']}>
      <Routes>
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </MemoryRouter>
  )

  act(() => {
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '你好' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))
  })

  expect(await screen.findByText('server down')).toBeInTheDocument()
})

test('Chat 支持一键复制回答', async () => {
  const writeText = vi.fn(async () => {})
  ;(globalThis as any).navigator = { clipboard: { writeText } }

  const post = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  post.mockImplementation(async () => ({ run_id: 'r1', route: { target: 'assistant' }, result: 'hello world' }))

  render(
    <MemoryRouter initialEntries={['/chat']}>
      <Routes>
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </MemoryRouter>
  )

  act(() => {
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))
  })

  await screen.findByText('hello world')
  act(() => {
    fireEvent.click(screen.getByRole('button', { name: '复制' }))
  })
  expect(writeText).toHaveBeenCalledWith('hello world')
})

test('Chat 对对象结果显示友好文本', async () => {
  const post = postJson as unknown as { mockImplementation: (fn: () => Promise<unknown>) => unknown }
  post.mockImplementation(async () => ({
    run_id: 'r2',
    route: { target: 'assistant' },
    result: { answer: '这是格式化后的回答', metadata: { model: 'qwen' } },
  }))

  render(
    <MemoryRouter initialEntries={['/chat']}>
      <Routes>
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </MemoryRouter>
  )

  act(() => {
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '请回答' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))
  })

  expect(await screen.findByText('这是格式化后的回答')).toBeInTheDocument()
})

import { describe, expect, it, vi } from 'vitest'
import { fetchJson } from '../client'

describe('api/client', () => {
  it('当响应为 ok:false 时抛出错误', async () => {
    const mockFetch = vi.fn(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: false, message: '股票不存在' }),
      } as any
    })
    vi.stubGlobal('fetch', mockFetch)

    await expect(fetchJson('/api/watchlist')).rejects.toThrow('股票不存在')
  })

  it('当配置 VITE_AI_QUANT_API_KEY 时自动携带 X-API-Key', async () => {
    ;(globalThis as any).VITE_AI_QUANT_API_KEY = 'k1'

    const mockFetch = vi.fn(async (_url: string, init?: RequestInit) => {
      expect((init?.headers as any)?.['X-API-Key']).toBe('k1')
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true }),
      } as any
    })
    vi.stubGlobal('fetch', mockFetch)

    await fetchJson('/api/health')
  })
})

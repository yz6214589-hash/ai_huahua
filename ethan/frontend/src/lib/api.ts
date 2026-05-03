export const API_BASE =
  import.meta.env.VITE_ETHAN_API_BASE ||
  `${window.location.protocol}//${window.location.hostname || '127.0.0.1'}:8001`

type ApiErrorDetail =
  | string
  | {
      code?: string
      message?: string
      hint?: string
    }

function formatDetail(detail: ApiErrorDetail): string {
  if (!detail) return '请求失败'
  if (typeof detail === 'string') return detail
  const parts = [detail.message, detail.hint].filter(Boolean)
  return parts.length ? parts.join('；') : '请求失败'
}

async function parseError(res: Response): Promise<string> {
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    try {
      const data = (await res.json()) as { detail?: ApiErrorDetail; message?: string }
      if (data?.detail) return formatDetail(data.detail)
      if (data?.message) return data.message
      return `请求失败（${res.status}）`
    } catch {
      return `请求失败（${res.status}）`
    }
  }
  try {
    const text = await res.text()
    return text || `请求失败（${res.status}）`
  } catch {
    return `请求失败（${res.status}）`
  }
}

function formatNetworkError(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  if (/Failed to fetch|NetworkError|ERR_FAILED/i.test(msg)) {
    return '后端不可达或被 CORS 阻止；请确认后端已启动且允许当前前端 Origin（可设置 VITE_ETHAN_API_BASE / ETHAN_CORS_ORIGINS）'
  }
  return msg
}

export async function apiGet<T>(path: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`)
    if (!res.ok) throw new Error(await parseError(res))
    return (await res.json()) as T
  } catch (e) {
    throw new Error(formatNetworkError(e))
  }
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await parseError(res))
    return (await res.json()) as T
  } catch (e) {
    throw new Error(formatNetworkError(e))
  }
}

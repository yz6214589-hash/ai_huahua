export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const apiKey = ((import.meta as any)?.env?.VITE_AI_QUANT_API_KEY as string | undefined) || ((globalThis as any).VITE_AI_QUANT_API_KEY as string | undefined)
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': String(apiKey) } : {}),
      ...(init?.headers || {}),
    },
  })

  if (!res.ok) {
    let detail = ''
    try {
      const data = await res.json()
      detail = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data)
    } catch {
      try {
        detail = await res.text()
      } catch {
        detail = ''
      }
    }
    throw new Error(detail || `HTTP ${res.status}`)
  }

  const data = (await res.json()) as any
  if (data && typeof data === 'object' && 'ok' in data && data.ok === false) {
    const msg = typeof data.message === 'string' && data.message.trim() ? data.message : typeof data.detail === 'string' ? data.detail : '操作失败'
    throw new Error(msg)
  }
  return data as T
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function fetchText(url: string, init?: RequestInit): Promise<string> {
  const apiKey = ((import.meta as any)?.env?.VITE_AI_QUANT_API_KEY as string | undefined) || ((globalThis as any).VITE_AI_QUANT_API_KEY as string | undefined)
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(apiKey ? { 'X-API-Key': String(apiKey) } : {}),
      ...(init?.headers || {}),
    },
  })

  if (!res.ok) {
    let detail = ''
    try {
      detail = await res.text()
    } catch {
      detail = ''
    }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.text()
}


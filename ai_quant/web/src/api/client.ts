export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
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

  return (await res.json()) as T
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}


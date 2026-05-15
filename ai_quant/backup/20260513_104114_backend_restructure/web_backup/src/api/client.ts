/**
 * API 请求客户端模块
 * 提供统一的 HTTP 请求方法，支持 JSON 数据的获取和提交
 * 自动处理 API 密钥认证和错误响应解析
 */

// 通用 JSON 请求函数，支持泛型返回类型
// 从环境变量或全局对象中获取 API 密钥，并将其添加到请求头中
// 如果响应状态码不是 2xx，会尝试解析错误详情并抛出异常
export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  // 优先从 Vite 环境变量获取 API 密钥，回退到全局变量
  const apiKey = ((import.meta as any)?.env?.VITE_AI_QUANT_API_KEY as string | undefined) || ((globalThis as any).VITE_AI_QUANT_API_KEY as string | undefined)
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': String(apiKey) } : {}),  // 添加 API 密钥到请求头
      ...(init?.headers || {}),
    },
  })

  // 检查 HTTP 响应状态码，非 2xx 状态码时解析错误信息
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

  // 解析响应 JSON 数据，检查业务层错误状态
  const data = (await res.json()) as any
  if (data && typeof data === 'object' && 'ok' in data && data.ok === false) {
    const msg = typeof data.message === 'string' && data.message.trim() ? data.message : typeof data.detail === 'string' ? data.detail : '操作失败'
    throw new Error(msg)
  }
  return data as T
}

// POST 请求包装函数，将 body 对象序列化为 JSON 后发送
export async function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// 获取纯文本响应的请求函数，适用于 Markdown 等文本内容
// 不设置 Content-Type，因为不发送 JSON body
export async function fetchText(url: string, init?: RequestInit): Promise<string> {
  const apiKey = ((import.meta as any)?.env?.VITE_AI_QUANT_API_KEY as string | undefined) || ((globalThis as any).VITE_AI_QUANT_API_KEY as string | undefined)
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(apiKey ? { 'X-API-Key': String(apiKey) } : {}),
      ...(init?.headers || {}),
    },
  })

  // 检查响应状态，失败时抛出错误
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


import { fetchJson, postJson } from './client'

export interface SimAccount {
  id: number
  account_name: string
  initial_capital: number
  current_capital: number
  total_asset: number
  status: string
  description?: string
  created_at?: string
  updated_at?: string
}

export interface SimPosition {
  id: number
  account_id: number
  stock_code: string
  stock_name: string
  volume: number
  available_volume: number
  cost_price: number
  current_price?: number
  market_value?: number
  profit_loss?: number
  profit_loss_ratio?: number
  created_at?: string
  updated_at?: string
}

export interface SimTrade {
  id: number
  trade_no: string
  account_id: number
  stock_code: string
  stock_name: string
  side: string
  price: number
  volume: number
  amount: number
  commission: number
  trade_time: string
  strategy?: string
}

export interface SimTradeRequest {
  account_id: number
  stock_code: string
  stock_name: string
  side: string
  price: number
  volume: number
  strategy?: string
}

export interface SimAccountListResponse {
  accounts: SimAccount[]
  total: number
}

export interface SimPositionResponse {
  positions: SimPosition[]
  total: number
}

export interface SimTradeResponse {
  trades: SimTrade[]
  total: number
  page: number
  page_size: number
}

export async function getSimAccounts(): Promise<SimAccountListResponse> {
  return fetchJson<SimAccountListResponse>('/api/v1/sim-account/list')
}

export async function getSimAccountDetail(accountId: number): Promise<SimAccount> {
  return fetchJson<SimAccount>(`/api/v1/sim-account/detail/${accountId}`)
}

export async function createSimAccount(data: {
  account_name: string
  initial_capital?: number
  description?: string
}): Promise<any> {
  return postJson('/api/v1/sim-account/create', data)
}

export async function getSimPositions(accountId: number): Promise<SimPositionResponse> {
  return fetchJson<SimPositionResponse>(`/api/v1/sim-account/positions/${accountId}`)
}

export async function getSimTrades(
  accountId: number,
  params?: { page?: number; page_size?: number }
): Promise<SimTradeResponse> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  const qs = searchParams.toString()
  return fetchJson<SimTradeResponse>(`/api/v1/sim-account/trades/${accountId}${qs ? '?' + qs : ''}`)
}

export async function placeSimTrade(request: SimTradeRequest): Promise<any> {
  return postJson('/api/v1/sim-account/trade', request)
}

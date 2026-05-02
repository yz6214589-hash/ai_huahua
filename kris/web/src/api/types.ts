export type Decision = 'approve' | 'warn' | 'reject' | 'halt'

export type Direction = 'buy' | 'sell'

export interface OrderIn {
  stock_code: string
  direction: Direction
  amount: number
  price: number
  quantity?: number
}

export interface PortfolioIn {
  total_asset: number
  prices: Record<string, number>
  atr: Record<string, number>
}

export interface ApproveRequest {
  order: OrderIn
  portfolio: PortfolioIn
  context?: {
    news_text?: string
  }
}

export interface RiskDecisionOut {
  decision: Decision
  reason: string
  rule_name: string
  max_position_pct: number
  suggested_amount: number
  suggested_quantity: number
  timestamp: string
  checks: Array<{
    decision: Decision
    reason: string
    rule_name: string
    max_position_pct: number
    timestamp: string
  }>
}

export interface KirsStatus {
  total: number
  approved: number
  warned: number
  rejected: number
  rejection_rate: number
  circuit_breaker: {
    daily_start_nav: number
    current_nav: number
    daily_pnl_pct: number
    is_halted: boolean
    halt_reason: string
    atr_stops: Record<
      string,
      {
        entry_price: number
        atr: number
        stop_price: number
      }
    >
  }
  macro: {
    vix: number | null
    coefficient: number
    risk_level: string
  }
}

export interface AuditItem {
  time: string
  stock: string
  direction: Direction
  amount: number
  decision: Decision
  rule: string
  reason: string
}


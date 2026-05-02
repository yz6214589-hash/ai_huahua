export type Side = 'buy' | 'sell'
export type StrategyType = 'twap' | 'vwap' | 'rl'

export type ExecutionConstraints = {
  max_participation_rate: number
  max_single_order_qty: number
  cancel_retry: { max_retries: number; wait_seconds: number }
  slippage_alert_bps: number
}

export type ExecutionTaskCreate = {
  symbol: string
  side: Side
  total_qty: number
  num_steps: number
  strategy: StrategyType
  rl_model_path?: string | null
  impact_eta: number
  impact_gamma: number
  adv?: number | null
  constraints: ExecutionConstraints
}


import client from './client'

export interface BacktestRequest {
  strategy_id: number
  start_date: string
  end_date: string
  initial_capital: number
}

export interface BacktestTrade {
  code: string
  name: string
  buy_date: string
  buy_price: number
  sell_date: string
  sell_price: number
  shares: number
  pnl: number
  pnl_pct: number
  hold_days: number
  sell_reason: string
}

export interface BacktestSummary {
  total_return: number
  annual_return: number
  max_drawdown: number
  win_rate: number
  sharpe_ratio: number
  profit_loss_ratio: number
  total_trades: number
  final_value: number
}

export interface BacktestResult {
  id: number
  strategy_id: number
  strategy_name: string
  start_date: string
  end_date: string
  initial_capital: number
  status: string
  error_message?: string
  summary?: BacktestSummary
  daily_values?: { date: string; value: number }[]
  trades?: BacktestTrade[]
  created_at?: string
}

export function runBacktest(data: BacktestRequest) {
  return client.post<BacktestResult>('/backtest/run', data)
}

export function getBacktest(id: number) {
  return client.get<BacktestResult>(`/backtest/${id}`)
}

export function listBacktests() {
  return client.get<BacktestResult[]>('/backtest/list')
}

export function deleteBacktest(id: number) {
  return client.delete(`/backtest/${id}`)
}

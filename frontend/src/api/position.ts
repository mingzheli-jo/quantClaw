import client from './client'

export interface PositionItem {
  id: number
  code: string
  stock_name: string
  buy_date: string
  buy_price: number
  shares: number
  cost_amount: number
  current_price: number
  highest_price: number
  pnl_pct: number
  status: string
  hold_days: number
  stop_loss_price: number
  take_profit_price: number
  executed: boolean
}

export interface CreatePositionPayload {
  code: string
  stock_name: string
  buy_price: number
  shares: number
}

export interface ClosePositionPayload {
  close_price: number
  close_reason: string
}

export interface TradeRecord {
  id: number
  code: string
  stock_name: string
  trade_date: string
  action: string
  price: number
  shares: number
  amount: number
  fee: number
  reason: string
}

export interface PositionStats {
  total_trades: number
  win_count: number
  loss_count: number
  win_rate: number
  total_pnl: number
  avg_pnl_pct: number
  avg_hold_days: number
}

export function fetchPositions() {
  return client.get<PositionItem[]>('/position/list')
}

export function createPosition(data: CreatePositionPayload) {
  return client.post('/position/create', data)
}

export function closePosition(id: number, data: ClosePositionPayload) {
  return client.post(`/position/${id}/close`, data)
}

export function fetchTrades(limit = 50) {
  return client.get<TradeRecord[]>('/position/trades', { params: { limit } })
}

export function fetchStats() {
  return client.get<PositionStats>('/position/stats')
}

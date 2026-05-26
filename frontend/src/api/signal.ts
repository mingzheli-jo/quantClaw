import client from './client'

export interface SignalItem {
  id: number
  code: string
  stock_name: string
  trade_date: string
  direction: string
  score: number
  reason: string
  close_price: number
  suggested_buy_low: number
  suggested_buy_high: number
  stop_loss_price: number
  target_price: number
}

export function fetchTodaySignals() {
  return client.get<SignalItem[]>('/signal/today')
}

export function fetchHistory(days = 30, direction?: string) {
  const params: Record<string, unknown> = { days }
  if (direction) {
    params.direction = direction
  }
  return client.get<SignalItem[]>('/signal/history', { params })
}

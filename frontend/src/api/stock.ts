import client from './client'

export interface KlineItem {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface StockScore {
  code: string
  stock_name: string
  score: number
  tech_score: number
  fund_score: number
  momentum_score: number
  sentiment_score: number
  reason: string
}

export interface StockSignal {
  trade_date: string
  direction: string
  score: number
  reason: string
}

export function fetchKline(code: string, days = 60) {
  return client.get<KlineItem[]>(`/stock/${code}/kline`, { params: { days } })
}

export function fetchScore(code: string) {
  return client.get<StockScore>(`/stock/${code}/score`)
}

export function fetchSignals(code: string) {
  return client.get<StockSignal[]>(`/stock/${code}/signals`)
}

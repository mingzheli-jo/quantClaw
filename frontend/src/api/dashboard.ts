import client from './client'

export interface OverviewData {
  temperature: number
  sh_index_pct: number
  sz_index_pct: number
  cyb_index_pct: number
  limit_up: number
  limit_down: number
  north_net: number
  active_positions: number
  total_pnl: number
  signal_accuracy_7d: number
}

export interface SentimentData {
  up_count: number
  down_count: number
  limit_up: number
  limit_down: number
  temperature: number
}

export function fetchOverview() {
  return client.get<OverviewData>('/dashboard/overview')
}

export function fetchSentiment() {
  return client.get<SentimentData>('/dashboard/sentiment')
}

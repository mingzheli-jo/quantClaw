import client from './client'

export interface RankingItem {
  code: string
  stock_name: string
  score: number
  tech_score: number
  fund_score: number
  momentum_score: number
  sentiment_score: number
  reason: string
  close_price: number
}

export interface RankingResponse {
  total: number
  page: number
  items: RankingItem[]
}

export interface SectorItem {
  sector: string
  change_pct: number
  net_fund_flow: number
}

export interface NorthFlowItem {
  trade_date: string
  net_amount: number
}

export function fetchRanking(page = 1, size = 20) {
  return client.get<RankingResponse>('/scan/ranking', { params: { page, size } })
}

export function fetchSectors() {
  return client.get<SectorItem[]>('/scan/sectors')
}

export function fetchNorthFlow(days = 30) {
  return client.get<NorthFlowItem[]>('/scan/north-flow', { params: { days } })
}

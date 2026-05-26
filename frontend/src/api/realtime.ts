import client from './client'

export interface IndexData {
  code: string
  name: string
  price: number
  change_pct: number
  change_amount: number
  turnover: number
}

export interface NorthFlowData {
  time: string
  net_amount: number
  sh_net: number
  sz_net: number
  timeline: { time: string; net: number }[]
}

export interface SectorData {
  name: string
  change_pct: number
  net_fund_flow: number
  up_count?: number
  down_count?: number
}

export interface PositionLive {
  code: string
  stock_name: string
  buy_price: number
  current_price: number
  change_pct: number
  shares: number
  pnl: number
  pnl_pct: number
  buy_date: string
}

export interface RealtimeSummary {
  indices: IndexData[]
  north_flow: NorthFlowData
  sectors: { gainers: SectorData[]; fund_inflow: SectorData[] }
  is_trading: boolean
  last_refresh: string | null
}

export function fetchRealtimeSummary() {
  return client.get<RealtimeSummary>('/realtime/summary')
}

export function fetchRealtimeIndices() {
  return client.get<IndexData[]>('/realtime/indices')
}

export function fetchRealtimeNorthFlow() {
  return client.get<NorthFlowData>('/realtime/north-flow')
}

export function fetchRealtimeSectors() {
  return client.get<{ gainers: SectorData[]; fund_inflow: SectorData[] }>('/realtime/sectors')
}

export function fetchRealtimePositions() {
  return client.get<PositionLive[]>('/realtime/positions')
}

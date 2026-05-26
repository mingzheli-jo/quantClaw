import client from './client'

export interface LearnItem {
  name: string
  summary: string
  formula: string
  buy_pattern: string
  sell_pattern: string
  trap: string
  weight_in_system: string
}

export function fetchToday() {
  return client.get<LearnItem>('/learn/today')
}

export function fetchArchive() {
  return client.get<LearnItem[]>('/learn/archive')
}

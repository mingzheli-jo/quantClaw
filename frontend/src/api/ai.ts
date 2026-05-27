import client from './client'

export interface AIAnalysisItem {
  code: string
  stock_name: string
  score: number
  summary: string | null
  risk: string | null
  suggestion: string | null
  market_comment: string | null
  llm_provider: string
  created_at: string
}

export interface AIDetail {
  code: string
  trade_date: string
  summary: string | null
  risk: string | null
  suggestion: string | null
  market_comment: string | null
}

export function fetchDailyAnalyses() {
  return client.get<AIAnalysisItem[]>('/ai/daily')
}

export function fetchAnalysis(code: string) {
  return client.get<AIDetail>('/ai/' + code)
}

export function generateAnalysis(code: string) {
  return client.post<AIDetail>('/ai/generate/' + code)
}

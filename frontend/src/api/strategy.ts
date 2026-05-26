import client from './client'

export interface StrategyTemplate {
  id: number
  name: string
  description: string
  filter_config: Record<string, any>
  score_config: Record<string, any>
  signal_config: Record<string, any>
  risk_config: Record<string, any>
  is_active: boolean
  is_builtin: boolean
  created_at?: string
  updated_at?: string
}

export function listStrategies() {
  return client.get<StrategyTemplate[]>('/strategies')
}

export function getStrategy(id: number) {
  return client.get<StrategyTemplate>(`/strategies/${id}`)
}

export function createStrategy(data: Partial<StrategyTemplate>) {
  return client.post<StrategyTemplate>('/strategies', data)
}

export function updateStrategy(id: number, data: Partial<StrategyTemplate>) {
  return client.put<StrategyTemplate>(`/strategies/${id}`, data)
}

export function deleteStrategy(id: number) {
  return client.delete(`/strategies/${id}`)
}

export function activateStrategy(id: number) {
  return client.put<StrategyTemplate>(`/strategies/${id}/activate`)
}

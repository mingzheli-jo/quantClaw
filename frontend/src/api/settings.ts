import client from './client'

export interface StrategyConfig {
  filter: Record<string, number>
  score: Record<string, number>
  position: Record<string, number>
  risk: Record<string, number>
}

export interface NotifyConfig {
  feishu_webhook_url: string
}

export function getStrategy() {
  return client.get<StrategyConfig>('/settings/strategy')
}

export function updateStrategy(data: StrategyConfig) {
  return client.put('/settings/strategy', data)
}

export function getNotify() {
  return client.get<NotifyConfig>('/settings/notify')
}

export function testNotify(message: string) {
  return client.post<{ success: boolean }>('/settings/notify/test', { message })
}

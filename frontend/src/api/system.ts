import client from './client'

export interface HealthLog {
  id: number
  job_name: string
  status: string
  message: string | null
  records_collected: number
  details: string | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
}

export interface HealthSummary {
  last_success: string | null
  today_status: string
  today_jobs: number
}

export function fetchHealth() {
  return client.get<{ logs: HealthLog[] }>('/system/health')
}

export function fetchHealthSummary() {
  return client.get<HealthSummary>('/system/health/summary')
}

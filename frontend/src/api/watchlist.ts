import client from './client'

export interface WatchlistItem {
  code: string
  name: string
  industry: string
  close: number
  change_pct: number
  score: number
  note: string | null
  added_at: string
}

export function fetchWatchlist() {
  return client.get<WatchlistItem[]>('/watchlist')
}

export function addToWatchlist(code: string, note?: string) {
  return client.post('/watchlist', { code, note })
}

export function removeFromWatchlist(code: string) {
  return client.delete(`/watchlist/${code}`)
}

export function fetchWatchlistSignals() {
  return client.get('/watchlist/signals')
}

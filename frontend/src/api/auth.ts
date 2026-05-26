import client from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface MeResponse {
  username: string
}

export function login(username: string, password: string) {
  return client.post<LoginResponse>('/auth/login', { username, password })
}

export function fetchMe() {
  return client.get<MeResponse>('/auth/me')
}

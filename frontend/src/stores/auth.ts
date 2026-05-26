import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref('')
  const isLoggedIn = ref(!!token.value)

  async function login(user: string, password: string) {
    const { data } = await client.post('/auth/login', { username: user, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    isLoggedIn.value = true
    username.value = user
  }

  function logout() {
    token.value = ''
    username.value = ''
    isLoggedIn.value = false
    localStorage.removeItem('token')
  }

  async function fetchMe() {
    try {
      const { data } = await client.get('/auth/me')
      username.value = data.username
      isLoggedIn.value = true
    } catch {
      logout()
    }
  }

  return { token, username, isLoggedIn, login, logout, fetchMe }
})

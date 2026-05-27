import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/scan', name: 'scan', component: () => import('@/views/ScanView.vue') },
    { path: '/stock/:code', name: 'stock', component: () => import('@/views/StockDetailView.vue') },
    { path: '/position', name: 'position', component: () => import('@/views/PositionView.vue') },
    { path: '/realtime', name: 'realtime', component: () => import('@/views/RealtimeView.vue') },
    { path: '/backtest', name: 'backtest', component: () => import('@/views/BacktestView.vue') },
    { path: '/learn', name: 'learn', component: () => import('@/views/LearnView.vue') },
    { path: '/system', name: 'system', component: () => import('@/views/SystemHealthView.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    return { name: 'login' }
  }
})

export default router

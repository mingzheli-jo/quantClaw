<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="18" width="6" height="12" rx="1" fill="var(--color-accent)" opacity="0.5" />
          <rect x="10" y="10" width="6" height="20" rx="1" fill="var(--color-accent)" opacity="0.7" />
          <rect x="18" y="4" width="6" height="26" rx="1" fill="var(--color-accent)" opacity="0.85" />
          <rect x="26" y="2" width="4" height="28" rx="1" fill="var(--color-accent)" />
        </svg>
      </div>
      <span class="brand-text">QuantClaw</span>
    </div>

    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <el-icon :size="20"><component :is="item.icon" /></el-icon>
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="isActive(item.path)" class="nav-indicator" />
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div class="user-block">
        <div class="user-avatar">{{ avatarLetter }}</div>
        <span class="user-name">{{ username }}</span>
      </div>
      <button class="logout-btn" @click="handleLogout" title="退出登录">
        <el-icon :size="18"><SwitchButton /></el-icon>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  DataLine,
  Search,
  Wallet,
  Monitor,
  TrendCharts,
  Reading,
  Setting,
  SwitchButton,
  Star,
  Histogram,
  MagicStick,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const username = computed(() => authStore.username || 'User')
const avatarLetter = computed(() => username.value.charAt(0).toUpperCase())

const navItems = [
  { path: '/', label: '仪表盘', icon: DataLine },
  { path: '/scan', label: '选股扫描', icon: Search },
  { path: '/watchlist', label: '自选股', icon: Star },
  { path: '/compare', label: '个股对比', icon: Histogram },
  { path: '/ai', label: 'AI 洞察', icon: MagicStick },
  { path: '/position', label: '持仓管理', icon: Wallet },
  { path: '/realtime', label: '实时监控', icon: Monitor },
  { path: '/backtest', label: '策略回测', icon: TrendCharts },
  { path: '/learn', label: '学习中心', icon: Reading },
  { path: '/settings', label: '系统设置', icon: Setting },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  width: 220px;
  height: 100vh;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid var(--color-border);
}

.brand-icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--color-text);
}

.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.nav-item.active {
  color: var(--color-accent);
  background: rgba(78, 205, 196, 0.08);
}

.nav-indicator {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-accent);
  border-radius: 3px 0 0 3px;
}

.nav-label {
  white-space: nowrap;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--color-accent), #2a9d8f);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #0f0f23;
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  transition: all 0.2s ease;
}

.logout-btn:hover {
  color: var(--color-danger);
  background: rgba(239, 83, 80, 0.1);
}

@media (max-width: 767px) {
  .sidebar { display: none; }
}
</style>

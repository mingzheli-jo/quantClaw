<template>
  <nav class="bottom-tab-bar">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="tab-item"
      :class="{ active: isActive(tab.path) }"
    >
      <el-icon :size="22"><component :is="tab.icon" /></el-icon>
      <span class="tab-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { DataLine, Search, Star, Wallet, More } from '@element-plus/icons-vue'

const route = useRoute()

const tabs = [
  { path: '/', label: '首页', icon: DataLine },
  { path: '/scan', label: '扫描', icon: Search },
  { path: '/watchlist', label: '自选', icon: Star },
  { path: '/position', label: '持仓', icon: Wallet },
  { path: '/settings', label: '更多', icon: More },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<style scoped>
.bottom-tab-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  z-index: 200;
  justify-content: space-around;
  align-items: center;
  padding-bottom: env(safe-area-inset-bottom, 0);
}

@media (max-width: 767px) {
  .bottom-tab-bar { display: flex; }
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-decoration: none;
  color: var(--color-text-secondary);
  font-size: 11px;
  padding: 4px 12px;
  transition: color 0.2s;
}
.tab-item.active { color: var(--color-accent); }
.tab-label { white-space: nowrap; }
</style>

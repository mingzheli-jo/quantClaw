<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="grid-line" v-for="i in 12" :key="i" :style="{ left: `${(i / 13) * 100}%` }" />
      <div class="grid-line-h" v-for="i in 8" :key="'h' + i" :style="{ top: `${(i / 9) * 100}%` }" />
    </div>

    <div class="login-card">
      <div class="login-brand">
        <div class="brand-icon">
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="22" width="7" height="16" rx="1.5" fill="#4ecdc4" opacity="0.45" />
            <rect x="12" y="12" width="7" height="26" rx="1.5" fill="#4ecdc4" opacity="0.65" />
            <rect x="22" y="5" width="7" height="33" rx="1.5" fill="#4ecdc4" opacity="0.82" />
            <rect x="32" y="2" width="6" height="36" rx="1.5" fill="#4ecdc4" />
          </svg>
        </div>
        <h1 class="brand-title">QuantClaw</h1>
        <p class="brand-subtitle">A-Share Quantitative Signal Dashboard</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <div v-if="errorMsg" class="login-error">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ errorMsg }}</span>
        </div>

        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登录' }}
        </el-button>
      </el-form>

      <div class="login-footer">
        <span>Powered by Multi-Factor Scoring Engine</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { User, Lock, WarningFilled } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    await authStore.login(form.username, form.password)
    router.push('/')
  } catch (err: unknown) {
    if (err instanceof Error) {
      errorMsg.value = '用户名或密码错误'
    } else {
      errorMsg.value = '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--color-border);
  opacity: 0.3;
}

.grid-line-h {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--color-border);
  opacity: 0.3;
}

.login-card {
  width: 400px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 48px 40px 36px;
  position: relative;
  z-index: 1;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.4);
  animation: cardEnter 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cardEnter {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-brand {
  text-align: center;
  margin-bottom: 36px;
}

.brand-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
}

.brand-title {
  font-size: 28px;
  font-weight: 800;
  color: var(--color-text);
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.brand-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  letter-spacing: 0.5px;
}

.login-form {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  box-shadow: none;
  border-radius: 10px;
  padding: 4px 12px;
  transition: border-color 0.2s ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  border-color: var(--color-text-secondary);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(78, 205, 196, 0.12);
}

.login-form :deep(.el-input__inner) {
  color: var(--color-text);
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--color-text-secondary);
}

.login-form :deep(.el-input__prefix .el-icon) {
  color: var(--color-text-secondary);
}

.login-form :deep(.el-form-item__error) {
  color: var(--color-danger);
  font-size: 12px;
}

.login-error {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-danger);
  font-size: 13px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: rgba(239, 83, 80, 0.08);
  border-radius: 8px;
  border: 1px solid rgba(239, 83, 80, 0.2);
}

.login-btn {
  width: 100%;
  height: 44px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #0f0f23;
  transition: all 0.2s ease;
}

.login-btn:hover {
  background: #5de0d7;
  border-color: #5de0d7;
  transform: translateY(-1px);
  box-shadow: 0 6px 24px rgba(78, 205, 196, 0.3);
}

.login-btn:active {
  transform: translateY(0);
}

.login-footer {
  text-align: center;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}

.login-footer span {
  font-size: 11px;
  color: var(--color-text-secondary);
  opacity: 0.6;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
</style>

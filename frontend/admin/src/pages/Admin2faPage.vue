<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../lib/api'
import { setSession } from '../lib/auth'

const route = useRoute()
const router = useRouter()

const challengeId = computed(() => {
  const raw = route.query.challengeId
  return typeof raw === 'string' ? raw : ''
})

const nextPath = computed(() => {
  const raw = route.query.next
  return typeof raw === 'string' && raw ? raw : ''
})

function _defaultHome(): string {
  return '/admin/dashboard'
}

function _safeNextOrHome(next: string): string {
  const n = String(next || '').trim()
  if (!n) return _defaultHome()
  try {
    const resolved = router.resolve(n)
    const p = String(resolved.path || '')
    if (!p || p.startsWith('/login') || p === '/403') return _defaultHome()
    const requiredRole = resolved.meta?.role as string | undefined
    if (requiredRole && requiredRole !== 'ADMIN') return _defaultHome()
    return n
  } catch {
    return _defaultHome()
  }
}

const form = reactive({
  smsCode: '',
})

const sending = ref(false)
const verifying = ref(false)
const sentInfo = ref<{ resendAfterSeconds: number; expiresInSeconds: number } | null>(null)
const remainingSeconds = ref<number | null>(null)
let countdownTimer: ReturnType<typeof setInterval> | null = null

function startCountdown(initialSeconds: number) {
  // 清理之前的定时器
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }

  remainingSeconds.value = initialSeconds

  countdownTimer = setInterval(() => {
    if (remainingSeconds.value !== null && remainingSeconds.value > 0) {
      remainingSeconds.value--
    } else {
      // 倒计时结束，清理定时器
      if (countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
      remainingSeconds.value = null
    }
  }, 1000)
}

async function sendCode() {
  if (!challengeId.value) {
    ElMessage.error('缺少 challengeId')
    return
  }

  sending.value = true
  try {
    const data = await apiRequest<{ sent: boolean; expiresInSeconds: number; resendAfterSeconds: number }>(
      '/admin/auth/2fa/challenge',
      {
        method: 'POST',
        auth: false,
        body: { challengeId: challengeId.value },
      },
    )
    sentInfo.value = { expiresInSeconds: data.expiresInSeconds, resendAfterSeconds: data.resendAfterSeconds }
    // 启动倒计时
    startCountdown(data.expiresInSeconds)
    ElMessage.success(data.sent ? '验证码已发送' : '发送失败')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '发送失败')
  } finally {
    sending.value = false
  }
}

async function verify() {
  if (!challengeId.value) {
    ElMessage.error('缺少 challengeId')
    return
  }

  verifying.value = true
  try {
    const data = await apiRequest<{ token: string; admin: { id: string; username: string } }>(
      '/admin/auth/2fa/verify',
      {
        method: 'POST',
        auth: false,
        body: { challengeId: challengeId.value, smsCode: form.smsCode },
      },
    )

    setSession({ token: data.token, actorType: 'ADMIN', actorUsername: data.admin.username })
    ElMessage.success('登录成功')
    await router.replace(_safeNextOrHome(nextPath.value))
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '验证失败')
  } finally {
    verifying.value = false
  }
}

// 组件卸载时清理定时器
onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
})
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="title">Admin 2FA 验证</div>
      <div class="sub">按规格：先发送短信挑战，再输入验证码完成登录。</div>

      <el-alert v-if="!challengeId" title="challengeId 缺失，无法完成 2FA。" type="error" show-icon :closable="false" />

      <div class="actions">
        <el-button type="primary" :loading="sending" :disabled="!challengeId" @click="sendCode">发送验证码</el-button>
        <span v-if="remainingSeconds !== null && remainingSeconds > 0" class="hint">剩余 {{ remainingSeconds }} 秒</span>
        <span v-else-if="remainingSeconds === 0" class="hint expired">验证码已过期</span>
      </div>

      <el-form label-width="90px" @submit.prevent style="margin-top: 12px">
        <el-form-item label="验证码">
          <el-input v-model="form.smsCode" placeholder="输入短信验证码" />
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="verifying" :disabled="!challengeId" @click="verify">验证并登录</el-button>
          <el-button @click="$router.replace('/login')">返回登录</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.card {
  width: 520px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.sub {
  margin-top: 6px;
  color: rgba(0, 0, 0, 0.55);
  font-size: 13px;
}

.actions {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.55);
}

.hint.expired {
  color: #f56c6c;
}
</style>

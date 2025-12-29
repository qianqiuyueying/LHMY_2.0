<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ApiException, apiRequest } from '../lib/api'
import { setSession, type ActorType } from '../lib/auth'

const route = useRoute()
const router = useRouter()

const form = reactive({
  username: '',
  password: '',
})

const submitting = ref(false)
const lockSecondsLeft = ref(0)
let _lockTimer: number | null = null

// 注册（仅 Provider/Dealer；短信验证；注册后待审核）
const registerOpen = ref(false)
const registerRole = ref<'PROVIDER' | 'DEALER'>('PROVIDER')
const registerSubmitting = ref(false)
const registerSending = ref(false)
const registerResendLeft = ref(0)
let _registerTimer: number | null = null

const registerForm = reactive({
  username: '',
  password: '',
  providerName: '',
  dealerName: '',
  phone: '',
  smsCode: '',
})

function _startRegisterResendCountdown(seconds: number) {
  registerResendLeft.value = Math.max(0, Math.floor(seconds || 0))
  if (_registerTimer) {
    window.clearInterval(_registerTimer)
    _registerTimer = null
  }
  if (registerResendLeft.value <= 0) return
  _registerTimer = window.setInterval(() => {
    registerResendLeft.value = Math.max(0, (registerResendLeft.value || 0) - 1)
    if (registerResendLeft.value <= 0 && _registerTimer) {
      window.clearInterval(_registerTimer)
      _registerTimer = null
    }
  }, 1000)
}

function openRegister(role: 'PROVIDER' | 'DEALER') {
  registerRole.value = role
  registerForm.username = ''
  registerForm.password = ''
  registerForm.providerName = ''
  registerForm.dealerName = ''
  registerForm.phone = ''
  registerForm.smsCode = ''
  registerResendLeft.value = 0
  registerOpen.value = true
}

async function sendRegisterSms() {
  const phone = String(registerForm.phone || '').trim()
  if (!phone) return ElMessage.error('请输入手机号')
  registerSending.value = true
  try {
    const path = registerRole.value === 'PROVIDER' ? '/provider/auth/register/challenge' : '/dealer/auth/register/challenge'
    const data = await apiRequest<{ sent: boolean; expiresInSeconds: number; resendAfterSeconds: number }>(path, {
      method: 'POST',
      auth: false,
      body: { phone },
    })
    if (data.sent) {
      ElMessage.success('验证码已发送')
      _startRegisterResendCountdown(Number(data.resendAfterSeconds || 0))
    } else {
      ElMessage.error('发送失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '发送失败')
  } finally {
    registerSending.value = false
  }
}

async function submitRegister() {
  const username = String(registerForm.username || '').trim()
  const password = String(registerForm.password || '').trim()
  const phone = String(registerForm.phone || '').trim()
  const smsCode = String(registerForm.smsCode || '').trim()
  if (!username) return ElMessage.error('请输入用户名')
  if (!password) return ElMessage.error('请输入密码')
  if (!phone) return ElMessage.error('请输入手机号')
  if (!smsCode) return ElMessage.error('请输入验证码')

  if (registerRole.value === 'PROVIDER') {
    const providerName = String(registerForm.providerName || '').trim()
    if (!providerName) return ElMessage.error('请输入主体名称')
    registerSubmitting.value = true
    try {
      await apiRequest<{ submitted: boolean }>('/provider/auth/register', {
        method: 'POST',
        auth: false,
        body: { username, password, providerName, phone, smsCode },
      })
      ElMessage.success('已提交审核，请联系管理员启用后再登录')
      registerOpen.value = false
      form.username = username
      form.password = password
    } catch (e: any) {
      ElMessage.error(e?.apiError?.message ?? '注册失败')
    } finally {
      registerSubmitting.value = false
    }
    return
  }

  const dealerName = String(registerForm.dealerName || '').trim()
  if (!dealerName) return ElMessage.error('请输入主体名称')
  registerSubmitting.value = true
  try {
    await apiRequest<{ submitted: boolean }>('/dealer/auth/register', {
      method: 'POST',
      auth: false,
      body: { username, password, dealerName, phone, smsCode },
    })
    ElMessage.success('已提交审核，请联系管理员启用后再登录')
    registerOpen.value = false
    form.username = username
    form.password = password
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '注册失败')
  } finally {
    registerSubmitting.value = false
  }
}

const nextPath = computed(() => {
  const raw = route.query.next
  return typeof raw === 'string' && raw ? raw : ''
})

function _defaultHome(actorType: ActorType): string {
  if (actorType === 'ADMIN') return '/admin/dashboard'
  if (actorType === 'DEALER') return '/dealer/dashboard'
  return '/provider/workbench'
}

function _safeNextOrHome(next: string, actorType: ActorType): string {
  const n = String(next || '').trim()
  if (!n) return _defaultHome(actorType)
  // 防止 next 指向登录/403 等无意义页面，或指向其他身份的路由导致“登录成功但跳无权限”
  try {
    const resolved = router.resolve(n)
    const p = String(resolved.path || '')
    if (!p || p.startsWith('/login') || p === '/403') return _defaultHome(actorType)

    const requiredRole = resolved.meta?.role as string | undefined
    if (!requiredRole) return n
    if (requiredRole === 'ADMIN' && actorType !== 'ADMIN') return _defaultHome(actorType)
    if (requiredRole === 'DEALER' && actorType !== 'DEALER') return _defaultHome(actorType)
    if (requiredRole === 'PROVIDER' && !(actorType === 'PROVIDER' || actorType === 'PROVIDER_STAFF')) return _defaultHome(actorType)
    return n
  } catch {
    return _defaultHome(actorType)
  }
}

const loginToastShown = ref(false)

function showLoginReasonOnce() {
  if (loginToastShown.value) return
  const reason = typeof route.query.reason === 'string' ? String(route.query.reason || '').trim() : ''
  if (!reason) return
  loginToastShown.value = true

  if (reason === 'UNAUTHENTICATED') {
    ElMessage.error('请先登录')
  } else {
    ElMessage.error('请重新登录')
  }

  // 避免反复弹窗：清理 query.reason，但保留 next
  const next = nextPath.value
  router.replace({ path: '/login', query: next ? { next } : undefined }).catch(() => {
    // ignore
  })
}

function _isAuthFailed(e: unknown): boolean {
  return e instanceof ApiException && e.status === 401
}

function _getRetryAfterSeconds(e: unknown): number | null {
  if (!(e instanceof ApiException)) return null
  if (e.status !== 429) return null
  if (e.apiError?.code !== 'RATE_LIMITED') return null
  const s = Number((e.apiError as any)?.details?.retryAfterSeconds)
  if (!Number.isFinite(s) || s <= 0) return null
  return Math.floor(s)
}

function _startLockCountdown(seconds: number) {
  lockSecondsLeft.value = Math.max(1, Math.floor(seconds))
  if (_lockTimer) {
    window.clearInterval(_lockTimer)
    _lockTimer = null
  }
  _lockTimer = window.setInterval(() => {
    lockSecondsLeft.value = Math.max(0, (lockSecondsLeft.value || 0) - 1)
    if (lockSecondsLeft.value <= 0 && _lockTimer) {
      window.clearInterval(_lockTimer)
      _lockTimer = null
    }
  }, 1000)
}

async function smartLogin() {
  const username = String(form.username || '').trim()
  const password = String(form.password || '').trim()
  if (!username) return ElMessage.error('请输入用户名')
  if (!password) return ElMessage.error('请输入密码')
  if (lockSecondsLeft.value > 0) return

  submitting.value = true
  try {
    // 统一入口策略（v1 最小）：
    // - 优先按 Admin 登录（可能触发 2FA）
    // - 仅当“未登录/账号密码不匹配（401）”时，才尝试 Provider -> Dealer
    type AdminLoginOk = { token: string; admin: { id: string; username: string; phoneBound: boolean } }
    type AdminLogin2fa = { requires2fa: true; challengeId: string }
    try {
      const data = await apiRequest<AdminLoginOk | AdminLogin2fa>('/admin/auth/login', {
        method: 'POST',
        auth: false,
        body: { username, password },
      })

      const is2fa = (x: AdminLoginOk | AdminLogin2fa): x is AdminLogin2fa =>
        (x as AdminLogin2fa).requires2fa === true

      if (is2fa(data)) {
        await router.replace({
          path: '/admin-2fa',
          query: { challengeId: data.challengeId, next: _safeNextOrHome(nextPath.value, 'ADMIN') },
        })
        return
      }

      setSession({ token: data.token, actorType: 'ADMIN', actorUsername: data.admin.username })
      ElMessage.success('登录成功')
      if (data.admin.phoneBound === false) {
        ElMessage.warning('当前账号未绑定手机号：高风险操作前需要先绑定（安全设置里可绑定）')
      }
      await router.replace(_safeNextOrHome(nextPath.value, 'ADMIN'))
      return
    } catch (e: unknown) {
      const retryAfter = _getRetryAfterSeconds(e)
      if (retryAfter) {
        _startLockCountdown(retryAfter)
        ElMessage.error('登录失败次数过多，请稍后重试')
        return
      }
      if (!_isAuthFailed(e)) throw e
    }

    try {
      const data = await apiRequest<{ token: string; actor: { id: string; username: string; actorType: ActorType; providerId: string } }>(
        '/provider/auth/login',
        { method: 'POST', auth: false, body: { username, password } },
      )
      setSession({ token: data.token, actorType: data.actor.actorType, actorUsername: data.actor.username })
      ElMessage.success('登录成功')
      await router.replace(_safeNextOrHome(nextPath.value, data.actor.actorType))
      return
    } catch (e: unknown) {
      const retryAfter = _getRetryAfterSeconds(e)
      if (retryAfter) {
        _startLockCountdown(retryAfter)
        ElMessage.error('登录失败次数过多，请稍后重试')
        return
      }
      if (!_isAuthFailed(e)) throw e
    }

    try {
      const data = await apiRequest<{ token: string; actor: { id: string; username: string; actorType: 'DEALER'; dealerId: string } }>(
        '/dealer/auth/login',
        { method: 'POST', auth: false, body: { username, password } },
      )
      setSession({ token: data.token, actorType: data.actor.actorType as ActorType, actorUsername: data.actor.username })
      ElMessage.success('登录成功')
      await router.replace(_safeNextOrHome(nextPath.value, data.actor.actorType as ActorType))
      return
    } catch (e: unknown) {
      const retryAfter = _getRetryAfterSeconds(e)
      if (retryAfter) {
        _startLockCountdown(retryAfter)
        ElMessage.error('登录失败次数过多，请稍后重试')
        return
      }
      if (_isAuthFailed(e)) {
        ElMessage.error('账号或密码错误')
        return
      }
      throw e
    }
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? e?.message ?? '登录失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  showLoginReasonOnce()
})

onUnmounted(() => {
  if (_lockTimer) window.clearInterval(_lockTimer)
  _lockTimer = null
  if (_registerTimer) window.clearInterval(_registerTimer)
  _registerTimer = null
})
</script>

<template>
  <div class="page">
    <div class="panel">
      <div class="hero">
        <div class="hero__brand">
          <div class="hero__logo">LH</div>
          <div>
            <div class="hero__title">陆合铭云健康服务平台</div>
            <div class="hero__sub">运营 / 服务提供方 / 经销商后台</div>
          </div>
        </div>
        <div class="hero__points">
          <div class="hero__point"><b>可信赖</b>：关键操作有提示与可追溯信息</div>
          <div class="hero__point"><b>健康活力</b>：teal 品牌色，信息层级清晰</div>
          <div class="hero__point"><b>现代简洁</b>：统一卡片/表格/空态/错误态</div>
        </div>
      </div>

      <div class="card">
        <div class="card__title">登录</div>
        <div class="card__hint">同一入口登录后会自动进入对应后台；Admin 可能触发 2FA。</div>

        <el-form label-width="80px" @submit.prevent="smartLogin">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              :loading="submitting"
              :disabled="lockSecondsLeft > 0"
              native-type="submit"
              style="width: 100%"
            >
              {{ lockSecondsLeft > 0 ? `请等待 ${lockSecondsLeft}s` : '登录' }}
            </el-button>
          </el-form-item>
        </el-form>

        <el-alert
          v-if="lockSecondsLeft > 0"
          :title="`登录失败次数过多：${lockSecondsLeft}s 后可继续尝试`"
          type="warning"
          show-icon
          :closable="false"
        />

        <div style="display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap">
          <el-text type="info">可自助注册（短信验证），提交后需管理员启用。</el-text>
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <el-button type="primary" plain @click="openRegister('PROVIDER')">注册合作商</el-button>
            <el-button type="primary" plain @click="openRegister('DEALER')">注册经销商</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <el-dialog v-model="registerOpen" :title="registerRole === 'PROVIDER' ? '注册合作商（Provider）' : '注册经销商（Dealer）'" width="620px">
    <el-alert
      title="注册成功后账号为“待审核”，需管理员在“账号管理”中启用后才能登录。"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />
    <el-form label-width="110px">
      <el-form-item label="用户名">
        <el-input v-model="registerForm.username" placeholder="唯一登录名" autocomplete="username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="registerForm.password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item v-if="registerRole === 'PROVIDER'" label="合作商名称">
        <el-input v-model="registerForm.providerName" placeholder="例如：北京 XX 健康中心" />
      </el-form-item>
      <el-form-item v-else label="经销商名称">
        <el-input v-model="registerForm.dealerName" placeholder="例如：XX 经销商" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="registerForm.phone" placeholder="用于短信验证" autocomplete="tel" />
      </el-form-item>
      <el-form-item label="验证码">
        <div style="display: flex; gap: 8px; align-items: center; width: 100%">
          <el-input v-model="registerForm.smsCode" placeholder="短信验证码" style="flex: 1" />
          <el-button :loading="registerSending" :disabled="registerResendLeft > 0" @click="sendRegisterSms">
            {{ registerResendLeft > 0 ? `重新发送(${registerResendLeft}s)` : '发送验证码' }}
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="registerOpen = false">取消</el-button>
      <el-button type="primary" :loading="registerSubmitting" @click="submitRegister">提交注册</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1100px 640px at 12% 0%, rgba(20, 184, 166, 0.16), rgba(255, 255, 255, 0) 60%),
    radial-gradient(900px 600px at 100% 0%, rgba(20, 184, 166, 0.1), rgba(255, 255, 255, 0) 55%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0));
}

.panel {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 16px;
  align-items: stretch;
}

.hero {
  border-radius: 16px;
  padding: 22px 20px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(15, 23, 42, 0.1);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
}

.hero__brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hero__logo {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.95), rgba(13, 148, 136, 0.9));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.12);
}

.hero__title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.1;
}

.hero__sub {
  margin-top: 4px;
  font-size: 13px;
  color: rgba(15, 23, 42, 0.62);
}

.hero__points {
  margin-top: 16px;
  display: grid;
  gap: 10px;
  color: rgba(15, 23, 42, 0.76);
  font-size: 13px;
  line-height: 1.6;
}

.hero__point b {
  color: #0d9488;
}

.card {
  border-radius: 16px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(15, 23, 42, 0.1);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card__title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}

.card__hint {
  margin-top: -2px;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.6);
}

@media (max-width: 900px) {
  .panel {
    grid-template-columns: 1fr;
  }
}
</style>

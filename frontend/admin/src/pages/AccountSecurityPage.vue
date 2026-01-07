<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeaderBar from '../components/PageHeaderBar.vue'
import { apiRequest } from '../lib/api'
import { getSession, isAdmin, isDealer, isProvider } from '../lib/auth'
import { handleApiError } from '../lib/error-handling'

const session = computed(() => getSession())

const securityLoading = ref(false)
const twoFaEnabled = ref(false)
const phoneMasked = ref<string | null>(null)

async function loadSecurity() {
  const s = session.value
  if (!s || !isAdmin(s.actorType)) return
  securityLoading.value = true
  try {
    const data = await apiRequest<{ twoFaEnabled: boolean; phoneMasked?: string | null }>('/admin/auth/security')
    twoFaEnabled.value = !!data?.twoFaEnabled
    phoneMasked.value = (data?.phoneMasked ? String(data.phoneMasked) : null) || null
  } catch {
    // 不阻断页面：兜底为"未开启"
    twoFaEnabled.value = false
    phoneMasked.value = null
  } finally {
    securityLoading.value = false
  }
}

const form = reactive({
  oldPassword: '',
  newPassword: '',
  newPassword2: '',
})

const submitting = ref(false)

const bind = reactive({
  phone: '',
  smsCode: '',
})
const bindSending = ref(false)
const bindVerifying = ref(false)

const actorHint = computed(() => {
  const s = session.value
  if (!s) return ''
  if (isAdmin(s.actorType)) return '当前身份：ADMIN（运营后台）'
  if (isDealer(s.actorType)) return '当前身份：DEALER（经销商后台）'
  if (isProvider(s.actorType)) return `当前身份：${s.actorType}（服务提供方后台）`
  return `当前身份：${s.actorType}`
})

function validate(): string | null {
  if (!String(form.oldPassword || '').trim()) return '请输入旧密码'
  const p1 = String(form.newPassword || '')
  const p2 = String(form.newPassword2 || '')
  const s = session.value
  if (s && isAdmin(s.actorType)) {
    if (p1.length < 10) return '新密码长度至少为 10 位'
  } else {
    // PROVIDER / DEALER v1 最小：长度 ≥ 8（以现状后端口径为准）
    if (p1.length < 8) return '新密码长度至少为 8 位'
  }
  if (p1 !== p2) return '两次输入的新密码不一致'
  if (p1 === String(form.oldPassword || '')) return '新密码不能与旧密码相同'
  return null
}

async function sendBindCode() {
  const s = session.value
  if (!s || !isAdmin(s.actorType)) return ElMessage.error('仅 ADMIN 支持绑定手机号')
  const phone = String(bind.phone || '').trim()
  if (!phone) return ElMessage.error('请输入手机号')
  bindSending.value = true
  try {
    await apiRequest('/admin/auth/phone-bind/challenge', { method: 'POST', body: { phone } })
    ElMessage.success('验证码已发送（v1 mock：后端日志可见 code）')
  } catch (e: any) {
    handleApiError(e, { fallbackMessage: '发送失败' })
  } finally {
    bindSending.value = false
  }
}

async function verifyBindPhone() {
  const s = session.value
  if (!s || !isAdmin(s.actorType)) return ElMessage.error('仅 ADMIN 支持绑定手机号')
  const phone = String(bind.phone || '').trim()
  const smsCode = String(bind.smsCode || '').trim()
  if (!phone) return ElMessage.error('请输入手机号')
  if (!smsCode) return ElMessage.error('请输入验证码')
  bindVerifying.value = true
  try {
    await apiRequest('/admin/auth/phone-bind/verify', { method: 'POST', body: { phone, smsCode } })
    ElMessage.success('手机号绑定成功（已开启2FA）')
    bind.smsCode = ''
    await loadSecurity()
  } catch (e: any) {
    handleApiError(e, { fallbackMessage: '绑定失败' })
  } finally {
    bindVerifying.value = false
  }
}

async function submit() {
  const err = validate()
  if (err) return ElMessage.error(err)
  const s = session.value
  if (!s) return ElMessage.error('未登录')

  let endpoint = ''
  if (isAdmin(s.actorType)) endpoint = '/admin/auth/change-password'
  else if (isProvider(s.actorType)) endpoint = '/provider/auth/change-password'
  else if (isDealer(s.actorType)) endpoint = '/dealer/auth/change-password'
  else return ElMessage.error('当前身份暂不支持修改密码')

  submitting.value = true
  try {
    await apiRequest(endpoint, { method: 'POST', body: { oldPassword: form.oldPassword, newPassword: form.newPassword } })
    ElMessage.success('密码修改成功')
    form.oldPassword = ''
    form.newPassword = ''
    form.newPassword2 = ''
  } catch (e: any) {
    handleApiError(e, { fallbackMessage: '修改失败' })
  } finally {
    submitting.value = false
  }
}

// v1：仅 Admin 读取 2FA 开启状态与绑定手机号（脱敏）
watch(
  () => session.value?.actorType,
  () => {
    void loadSecurity()
  },
  { immediate: true },
)
</script>

<template>
  <div>
    <PageHeaderBar title="安全设置" />

    <el-card class="lh-card" style="margin-top: 12px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>修改密码（自助）</template>
        <div style="line-height: 1.7">
          <div>{{ actorHint }}</div>
          <div style="color: var(--lh-muted); margin-top: 4px">
            <span v-if="session && isAdmin(session.actorType)">规则：新密码长度至少 10 位，且需满足复杂度（大写/小写/数字/特殊字符至少 2 类）。</span>
            <span v-else>规则：新密码长度至少 8 位。</span>
          </div>
        </div>
      </el-alert>

      <el-form label-width="110px" style="max-width: 520px">
        <el-form-item label="旧密码">
          <el-input v-model="form.oldPassword" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="form.newPassword2" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="session && isAdmin(session.actorType)" class="lh-card" style="margin-top: 12px" :loading="securityLoading">
      <template v-if="twoFaEnabled">
        <el-alert type="success" show-icon :closable="false" style="margin-bottom: 12px">
          <template #title>2FA 已开启</template>
          <div style="line-height: 1.7">
            <div>当前绑定手机号：<b>{{ phoneMasked || '—' }}</b></div>
            <div style="color: var(--lh-muted); margin-top: 4px">手机号仅展示脱敏信息；如需更换请联系运维处理。</div>
          </div>
        </el-alert>
      </template>

      <template v-else>
        <el-alert type="warning" show-icon :closable="false" style="margin-bottom: 12px">
          <template #title>绑定手机号（开启 2FA）</template>
          <div style="line-height: 1.7">
            <div>未绑定手机号的管理员允许登录，但在“高风险操作”（结算/发货/强制取消/导出/发布等）前必须先绑定。</div>
            <div style="color: var(--lh-muted); margin-top: 4px">绑定动作会写审计日志（不记录手机号明文）。</div>
          </div>
        </el-alert>

        <el-form label-width="110px" style="max-width: 520px">
          <el-form-item label="手机号">
            <el-input v-model="bind.phone" placeholder="请输入手机号（11 位）" autocomplete="tel" />
          </el-form-item>
          <el-form-item label="验证码">
            <div style="display: flex; gap: 10px; width: 100%">
              <el-input v-model="bind.smsCode" placeholder="短信验证码" style="flex: 1" />
              <el-button :loading="bindSending" @click="sendBindCode">发送验证码</el-button>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="bindVerifying" @click="verifyBindPhone">确认绑定</el-button>
          </el-form-item>
        </el-form>
      </template>
    </el-card>
  </div>
</template>



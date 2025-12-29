<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type FooterConfig = {
  companyName: string
  cooperationEmail: string
  cooperationPhone: string
  icpBeianNo?: string | null
  icpBeianLink?: string | null
  publicAccountQrUrl?: string | null
  miniProgramQrUrl?: string | null
  version: string
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  companyName: '',
  cooperationEmail: '',
  cooperationPhone: '',
  icpBeianNo: '',
  icpBeianLink: '',
  publicAccountQrUrl: '',
  miniProgramQrUrl: '',
  version: '',
})

function isHttpUrlOrEmpty(x: string): boolean {
  const v = String(x || '').trim()
  if (!v) return true
  return /^https?:\/\//.test(v)
}

function isEmail(x: string): boolean {
  const v = String(x || '').trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<FooterConfig>('/admin/website/footer-config')
    cfg.companyName = data.companyName || ''
    cfg.cooperationEmail = data.cooperationEmail || ''
    cfg.cooperationPhone = data.cooperationPhone || ''
    cfg.icpBeianNo = (data.icpBeianNo as any) || ''
    cfg.icpBeianLink = (data.icpBeianLink as any) || ''
    cfg.publicAccountQrUrl = (data.publicAccountQrUrl as any) || ''
    cfg.miniProgramQrUrl = (data.miniProgramQrUrl as any) || ''
    cfg.version = data.version || '0'
    loadError.value = ''
    loadErrorCode.value = ''
    loadErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    loadError.value = msg
    loadErrorCode.value = e?.apiError?.code ?? ''
    loadErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

async function save() {
  const companyName = cfg.companyName.trim()
  const email = cfg.cooperationEmail.trim()
  const phone = cfg.cooperationPhone.trim()
  const icpLink = cfg.icpBeianLink.trim()
  const publicQr = cfg.publicAccountQrUrl.trim()
  const miniQr = cfg.miniProgramQrUrl.trim()

  if (!companyName) return ElMessage.error('公司名称不能为空')
  if (!email) return ElMessage.error('合作邮箱不能为空')
  if (!isEmail(email)) return ElMessage.error('合作邮箱格式不正确')
  if (!phone) return ElMessage.error('合作电话不能为空')
  if (!isHttpUrlOrEmpty(icpLink)) return ElMessage.error('ICP备案链接必须是 http(s):// URL（或留空）')
  if (!isHttpUrlOrEmpty(publicQr)) return ElMessage.error('公众号二维码 URL 必须是 http(s):// URL（或留空）')
  if (!isHttpUrlOrEmpty(miniQr)) return ElMessage.error('小程序码 URL 必须是 http(s):// URL（或留空）')

  saving.value = true
  try {
    await apiRequest<FooterConfig>('/admin/website/footer-config', {
      method: 'PUT',
      body: {
        companyName,
        cooperationEmail: email,
        cooperationPhone: phone,
        icpBeianNo: cfg.icpBeianNo.trim() || '',
        icpBeianLink: icpLink || '',
        publicAccountQrUrl: publicQr || '',
        miniProgramQrUrl: miniQr || '',
      },
    })
    ElMessage.success('已保存')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="官网基础配置：页脚与联系方式" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <el-form v-else label-width="140px">
        <el-form-item label="公司名称（必填）">
          <el-input v-model="cfg.companyName" placeholder="例如：陆合铭云健康服务平台" />
          <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ cfg.version || '0' }}</div>
        </el-form-item>

        <el-form-item label="合作邮箱（必填）">
          <el-input v-model="cfg.cooperationEmail" placeholder="bd@company.com" />
        </el-form-item>

        <el-form-item label="合作电话（必填）">
          <el-input v-model="cfg.cooperationPhone" placeholder="例如：400-000-0000" />
        </el-form-item>

        <el-form-item label="ICP备案号（可选）">
          <el-input v-model="cfg.icpBeianNo" placeholder="例如：京ICP备xxxxxx号" />
        </el-form-item>

        <el-form-item label="ICP备案链接（可选）">
          <el-input v-model="cfg.icpBeianLink" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="公众号二维码 URL（可选）">
          <el-input v-model="cfg.publicAccountQrUrl" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="小程序码 URL（可选）">
          <el-input v-model="cfg.miniProgramQrUrl" placeholder="https://..." />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>



<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type SiteSeo = {
  siteName: string
  defaultTitle: string
  defaultDescription: string
  canonicalBaseUrl?: string | null
  robots?: string | null
  version: string
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  siteName: '',
  defaultTitle: '',
  defaultDescription: '',
  canonicalBaseUrl: '',
  robots: '',
  version: '',
})

function isHttpUrlOrEmpty(x: string): boolean {
  const v = String(x || '').trim()
  if (!v) return true
  return /^https?:\/\//.test(v)
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<SiteSeo>('/admin/website/site-seo')
    cfg.siteName = data.siteName || ''
    cfg.defaultTitle = data.defaultTitle || ''
    cfg.defaultDescription = data.defaultDescription || ''
    cfg.canonicalBaseUrl = String(data.canonicalBaseUrl || '')
    cfg.robots = String(data.robots || '')
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
  const siteName = cfg.siteName.trim()
  const defaultTitle = cfg.defaultTitle.trim()
  const defaultDescription = cfg.defaultDescription.trim()
  const canonicalBaseUrl = cfg.canonicalBaseUrl.trim()
  const robots = cfg.robots.trim()

  if (!siteName) return ElMessage.error('siteName 不能为空')
  if (!defaultTitle) return ElMessage.error('defaultTitle 不能为空')
  if (!defaultDescription) return ElMessage.error('defaultDescription 不能为空')
  if (!isHttpUrlOrEmpty(canonicalBaseUrl)) return ElMessage.error('canonicalBaseUrl 必须是 http(s):// URL（或留空）')

  saving.value = true
  try {
    await apiRequest<SiteSeo>('/admin/website/site-seo', {
      method: 'PUT',
      body: {
        siteName,
        defaultTitle,
        defaultDescription,
        canonicalBaseUrl: canonicalBaseUrl || '',
        robots: robots || 'index,follow',
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
    <PageHeaderBar title="官网管理：站点信息与 SEO" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <el-form v-else label-width="160px">
        <el-form-item label="siteName（必填）">
          <el-input v-model="cfg.siteName" placeholder="例如：陆合铭云健康服务平台" />
          <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ cfg.version || '0' }}</div>
        </el-form-item>

        <el-form-item label="defaultTitle（必填）">
          <el-input v-model="cfg.defaultTitle" placeholder="默认 title（首页）" />
        </el-form-item>

        <el-form-item label="defaultDescription（必填）">
          <el-input v-model="cfg.defaultDescription" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="canonicalBaseUrl（可选）">
          <el-input v-model="cfg.canonicalBaseUrl" placeholder="http(s)://example.com（留空表示不输出 canonical）" />
        </el-form-item>

        <el-form-item label="robots（可选）">
          <el-input v-model="cfg.robots" placeholder="默认：index,follow" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>



<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type WebsiteExternalLinks = {
  miniProgramUrl: string
  h5BuyUrl: string
  version: string
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  miniProgramUrl: '',
  h5BuyUrl: '',
  version: '',
})

function isHttpUrl(x: string): boolean {
  return /^https?:\/\//.test(String(x || '').trim())
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<WebsiteExternalLinks>('/admin/website/external-links')
    cfg.miniProgramUrl = data.miniProgramUrl || ''
    cfg.h5BuyUrl = data.h5BuyUrl || ''
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
  const mini = cfg.miniProgramUrl.trim()
  const h5 = cfg.h5BuyUrl.trim()
  if (!mini) return ElMessage.error('小程序外链不能为空')
  if (!h5) return ElMessage.error('H5 购买外链不能为空')
  if (!isHttpUrl(mini)) return ElMessage.error('小程序外链必须是 http(s):// URL')
  if (!isHttpUrl(h5)) return ElMessage.error('H5 购买外链必须是 http(s):// URL')

  saving.value = true
  try {
    await apiRequest<WebsiteExternalLinks>('/admin/website/external-links', {
      method: 'PUT',
      body: { miniProgramUrl: mini, h5BuyUrl: h5 },
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
    <PageHeaderBar title="官网基础配置：导流外链" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <el-form v-else label-width="140px">
        <el-form-item label="小程序外链（必填）">
          <el-input v-model="cfg.miniProgramUrl" placeholder="https://..." />
          <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ cfg.version || '0' }}</div>
        </el-form-item>

        <el-form-item label="H5 购买外链（必填）">
          <el-input v-model="cfg.h5BuyUrl" placeholder="https://..." />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>



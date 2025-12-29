<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type AiConfig = {
  enabled: boolean
  provider: 'OPENAI_COMPAT'
  baseUrl: string
  model: string
  systemPrompt?: string | null
  temperature?: number | null
  maxTokens?: number | null
  timeoutMs?: number | null
  retries?: number | null
  rateLimitPerMinute?: number | null
  version: string
  apiKeyMasked?: string | null
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  enabled: false,
  baseUrl: '',
  apiKey: '',
  model: '',
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 1024,
  timeoutMs: 15000,
  retries: 1,
  rateLimitPerMinute: 30,
  apiKeyMasked: '',
  version: '',
})

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<AiConfig>('/admin/ai/config')
    cfg.enabled = data.enabled
    cfg.baseUrl = data.baseUrl
    cfg.model = data.model
    cfg.systemPrompt = data.systemPrompt ?? ''
    cfg.temperature = data.temperature ?? 0.7
    cfg.maxTokens = data.maxTokens ?? 1024
    cfg.timeoutMs = data.timeoutMs ?? 15000
    cfg.retries = data.retries ?? 1
    cfg.rateLimitPerMinute = data.rateLimitPerMinute ?? 30
    cfg.apiKeyMasked = data.apiKeyMasked ?? ''
    cfg.version = data.version
    cfg.apiKey = ''
    loadError.value = ''
    loadErrorCode.value = ''
    loadErrorRequestId.value = ''
  } catch (e: any) {
    // 保留页面级错误态渲染，同时统一走 handleApiError（含 ADMIN_PHONE_REQUIRED 跳转）
    loadError.value = e?.apiError?.message ?? '加载失败'
    loadErrorCode.value = e?.apiError?.code ?? ''
    loadErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await apiRequest<AiConfig>('/admin/ai/config', {
      method: 'PUT',
      body: {
        enabled: cfg.enabled,
        provider: 'OPENAI_COMPAT',
        baseUrl: cfg.baseUrl,
        apiKey: cfg.apiKey || undefined,
        model: cfg.model,
        systemPrompt: cfg.systemPrompt,
        temperature: cfg.temperature,
        maxTokens: cfg.maxTokens,
        timeoutMs: cfg.timeoutMs,
        retries: cfg.retries,
        rateLimitPerMinute: cfg.rateLimitPerMinute,
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
    <PageHeaderBar title="AI 配置中心" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />
      <el-form v-else label-width="140px">
        <el-form-item label="启用">
          <el-switch v-model="cfg.enabled" />
          <span style="margin-left: 8px; color: rgba(0, 0, 0, 0.55); font-size: 12px">version={{ cfg.version }}</span>
        </el-form-item>
        <el-form-item label="baseUrl">
          <el-input v-model="cfg.baseUrl" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="apiKey（可选更新）">
          <el-input v-model="cfg.apiKey" placeholder="留空表示不更新" show-password />
          <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">当前：{{ cfg.apiKeyMasked || '-' }}</div>
        </el-form-item>
        <el-form-item label="model">
          <el-input v-model="cfg.model" placeholder="模型名" />
        </el-form-item>
        <el-form-item label="systemPrompt">
          <el-input v-model="cfg.systemPrompt" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="temperature">
          <el-input-number v-model="cfg.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="maxTokens">
          <el-input-number v-model="cfg.maxTokens" :min="1" :max="200000" />
        </el-form-item>
        <el-form-item label="timeoutMs">
          <el-input-number v-model="cfg.timeoutMs" :min="100" :max="120000" />
        </el-form-item>
        <el-form-item label="retries">
          <el-input-number v-model="cfg.retries" :min="0" :max="10" />
        </el-form-item>
        <el-form-item label="rateLimitPerMinute">
          <el-input-number v-model="cfg.rateLimitPerMinute" :min="1" :max="100000" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

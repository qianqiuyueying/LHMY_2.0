<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type AiProvider = {
  id: string
  name: string
  providerType: string
  endpoint?: string | null
  extra: Record<string, any>
  status: string
  apiKeyMasked?: string | null
  credentialsKeys: string[]
}

const router = useRouter()
const loading = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')

const items = ref<AiProvider[]>([])

const dialogVisible = ref(false)
const saving = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  name: '',
  providerType: 'openapi_compatible',
  endpoint: '',
  status: 'ENABLED',
  apiKeyUpdate: '',
  appId: '',
  defaultModel: '',
  timeoutMs: 15000,
  retries: 1,
  rateLimitPerMinute: 30,
  extraJson: '{\n}\n',
})

const providerTypeOptions = [
  { label: 'DashScope 应用模式', value: 'dashscope_application' },
  { label: 'DashScope 模型模式', value: 'dashscope_model' },
  { label: 'OpenAPI compatible', value: 'openapi_compatible' },
  { label: '自定义 Provider（预留）', value: 'custom_provider' },
]

const isOpenApi = computed(() => form.providerType === 'openapi_compatible')
const isDashscopeApp = computed(() => form.providerType === 'dashscope_application')
const isDashscopeModel = computed(() => form.providerType === 'dashscope_model')
const supportsDefaultModel = computed(() => isOpenApi.value || isDashscopeModel.value)

function resetForm() {
  form.name = ''
  form.providerType = 'openapi_compatible'
  form.endpoint = ''
  form.status = 'ENABLED'
  form.apiKeyUpdate = ''
  form.appId = ''
  form.defaultModel = ''
  form.timeoutMs = 15000
  form.retries = 1
  form.rateLimitPerMinute = 30
  form.extraJson = '{\n}\n'
}

function safeParseJson(label: string, raw: string): any {
  const s = String(raw ?? '').trim()
  if (!s) return {}
  try {
    return JSON.parse(s)
  } catch {
    throw new Error(`${label} 不是合法 JSON`)
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: AiProvider[] }>('/admin/ai/providers')
    items.value = data.items ?? []
    loadError.value = ''
    loadErrorCode.value = ''
    loadErrorRequestId.value = ''
  } catch (e: any) {
    loadError.value = e?.apiError?.message ?? '加载失败'
    loadErrorCode.value = e?.apiError?.code ?? ''
    loadErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  isEditing.value = false
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: AiProvider) {
  resetForm()
  isEditing.value = true
  editingId.value = row.id
  form.name = row.name
  form.providerType = row.providerType
  form.endpoint = row.endpoint ?? ''
  form.status = row.status

  // 注意：后端不会返回 apiKey 明文；编辑时仅允许“可选更新”
  form.apiKeyUpdate = ''
  form.appId = ''
  form.defaultModel = ''
  form.extraJson = JSON.stringify(row.extra ?? {}, null, 2) + '\n'
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const extraFromJson = safeParseJson('extra', form.extraJson)

    // 结构化字段写入 extra（避免运营/管理员手拼 JSON）
    const extra: Record<string, any> = { ...(extraFromJson || {}) }
    if (supportsDefaultModel.value) {
      if (form.defaultModel.trim()) extra.default_model = form.defaultModel.trim()
      extra.timeoutMs = Number(form.timeoutMs)
      extra.retries = Number(form.retries)
      extra.rateLimitPerMinute = Number(form.rateLimitPerMinute)
    }

    const credentials: Record<string, any> = {}
    if (form.apiKeyUpdate.trim()) credentials.api_key = form.apiKeyUpdate.trim()
    if (isDashscopeApp.value && form.appId.trim()) credentials.app_id = form.appId.trim()

    if (!isEditing.value) {
      await apiRequest<AiProvider>('/admin/ai/providers', {
        method: 'POST',
        idempotencyKey: newIdempotencyKey(),
        body: {
          name: form.name,
          providerType: form.providerType,
          endpoint: form.endpoint || null,
          status: form.status,
          credentials,
          extra,
        },
      })
      ElMessage.success('已创建')
    } else {
      await apiRequest<AiProvider>(`/admin/ai/providers/${editingId.value}`, {
        method: 'PUT',
        idempotencyKey: newIdempotencyKey(),
        body: {
          name: form.name,
          providerType: form.providerType,
          endpoint: form.endpoint || null,
          status: form.status,
          credentials,
          extra,
        },
      })
      ElMessage.success('已保存')
    }

    dialogVisible.value = false
    await load()
  } catch (e: any) {
    const msg = e?.message || e?.apiError?.message
    if (msg && String(msg).includes('JSON')) {
      ElMessage.error(String(msg))
    } else {
      handleApiError(e, { router, fallbackMessage: '保存失败' })
    }
  } finally {
    saving.value = false
  }
}

async function testConnection(row: AiProvider) {
  try {
    const data = await apiRequest<{ ok: boolean; latencyMs: number; providerLatencyMs?: number | null }>(
      `/admin/ai/providers/${row.id}/test-connection`,
      { method: 'POST', idempotencyKey: newIdempotencyKey(), body: {} },
    )
    if (data.ok) {
      ElMessage.success(`连接正常（耗时 ${data.latencyMs}ms）`)
    } else {
      ElMessage.error('连接测试失败')
    }
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '连接测试失败' })
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="AI Provider（技术配置）" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <template v-else>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <div style="color: rgba(0, 0, 0, 0.55); font-size: 12px">
            Provider 用于“能不能连上 AI”。敏感凭证不会在列表/审计中返回明文。
          </div>
          <div>
            <el-button type="primary" @click="openCreate">新增 Provider</el-button>
            <el-button :disabled="loading" @click="load">刷新</el-button>
          </div>
        </div>

        <el-table :data="items" size="small" border>
          <el-table-column prop="name" label="标识（name）" min-width="160" />
          <el-table-column prop="providerType" label="类型" min-width="180" />
          <el-table-column prop="endpoint" label="endpoint" min-width="240" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column prop="apiKeyMasked" label="apiKey" width="140" />
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="success" @click="testConnection(row)">连接测试</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑 Provider' : '新增 Provider'" width="720px">
      <el-form label-width="150px">
        <el-form-item label="标识（name）">
          <el-input v-model="form.name" placeholder="例如：dashscope_app_prod" :disabled="false" />
        </el-form-item>
        <el-form-item label="Provider 类型">
          <el-select v-model="form.providerType" style="width: 100%">
            <el-option v-for="x in providerTypeOptions" :key="x.value" :label="x.label" :value="x.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="endpoint（可选）">
          <el-input v-model="form.endpoint" placeholder="留空表示使用默认 endpoint（如适用）" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="ENABLED" value="ENABLED" />
            <el-option label="DISABLED" value="DISABLED" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">凭证（credentials）</el-divider>
        <el-form-item label="apiKey（可选更新）">
          <el-input v-model="form.apiKeyUpdate" placeholder="留空表示不更新" show-password />
        </el-form-item>
        <el-form-item v-if="isDashscopeApp" label="appId">
          <el-input v-model="form.appId" placeholder="DashScope 应用 ID" />
        </el-form-item>

        <el-divider content-position="left">扩展字段（extra）</el-divider>
        <template v-if="supportsDefaultModel">
          <el-form-item label="default_model（可选）">
            <el-input
              v-model="form.defaultModel"
              placeholder="默认模型标识（仅存储在 Provider.extra；不会出现在 Strategy）"
            />
          </el-form-item>
          <el-form-item label="timeoutMs">
            <el-input-number v-model="form.timeoutMs" :min="100" :max="120000" />
          </el-form-item>
          <el-form-item label="retries">
            <el-input-number v-model="form.retries" :min="0" :max="10" />
          </el-form-item>
          <el-form-item label="rateLimitPerMinute">
            <el-input-number v-model="form.rateLimitPerMinute" :min="1" :max="100000" />
          </el-form-item>
        </template>
        <el-form-item label="extra（JSON）">
          <el-input v-model="form.extraJson" type="textarea" :rows="6" placeholder="{ ... }" />
          <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">
            该字段由 Provider adapter 自行解释；Strategy 不应依赖这里的私有字段。
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>


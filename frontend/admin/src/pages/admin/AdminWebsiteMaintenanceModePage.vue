<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type MaintenanceMode = {
  enabled: boolean
  messageTitle: string
  messageBody: string
  allowPaths: string[]
  allowIps?: string[]
  version: string
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  enabled: false,
  messageTitle: '维护中',
  messageBody: '我们正在进行系统维护，请稍后再试。',
  allowPathsText: '/contact',
  allowIpsText: '',
  version: '0',
})

function parseLines(text: string): string[] {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean)
  return Array.from(new Set(lines))
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<MaintenanceMode>('/admin/website/maintenance-mode')
    cfg.enabled = !!data.enabled
    cfg.messageTitle = data.messageTitle || '维护中'
    cfg.messageBody = data.messageBody || '我们正在进行系统维护，请稍后再试。'
    cfg.allowPathsText = (data.allowPaths || []).join('\n')
    cfg.allowIpsText = (data.allowIps || []).join('\n')
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
  const messageTitle = cfg.messageTitle.trim()
  const messageBody = cfg.messageBody.trim()
  if (!messageTitle) return ElMessage.error('messageTitle 不能为空')
  if (!messageBody) return ElMessage.error('messageBody 不能为空')

  const allowPaths = parseLines(cfg.allowPathsText)
  for (const p of allowPaths) {
    if (!p.startsWith('/')) return ElMessage.error('allowPaths 每行必须以 / 开头')
  }
  const allowIps = parseLines(cfg.allowIpsText)

  saving.value = true
  try {
    await apiRequest<MaintenanceMode>('/admin/website/maintenance-mode', {
      method: 'PUT',
      body: {
        enabled: !!cfg.enabled,
        messageTitle,
        messageBody,
        allowPaths,
        // v2 最小：allowIps 仅保存，不在官网侧启用（为未来升级预留）
        allowIps,
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
    <PageHeaderBar title="官网管理：维护模式" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <el-form v-else label-width="160px">
        <el-form-item label="启用维护模式">
          <el-switch v-model="cfg.enabled" />
          <span style="margin-left: 8px; color: rgba(0, 0, 0, 0.55); font-size: 12px">version={{ cfg.version }}</span>
        </el-form-item>

        <el-form-item label="维护页标题（必填）">
          <el-input v-model="cfg.messageTitle" />
        </el-form-item>

        <el-form-item label="维护页说明（必填）">
          <el-input v-model="cfg.messageBody" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="放行路径 allowPaths（可选）">
          <el-input
            v-model="cfg.allowPathsText"
            type="textarea"
            :rows="4"
            placeholder="每行一个 path，例如：/contact"
          />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">
            维护模式开启时，这些路径仍可访问；其余路径将显示维护页。
          </div>
        </el-form-item>

        <el-form-item label="allowIps（预留）">
          <el-input
            v-model="cfg.allowIpsText"
            type="textarea"
            :rows="3"
            placeholder="每行一个 IP（v2 最小仅保存不启用）"
          />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">
            v2 最小实现仅保存，不在官网侧启用；后续可按网关/反代口径升级（如 X-Forwarded-For）。
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>



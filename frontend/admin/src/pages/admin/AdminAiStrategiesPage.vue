<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type AiStrategy = {
  id: string
  scene: string
  displayName: string
  providerId?: string | null
  promptTemplate: string
  generationConfig: Record<string, any>
  constraints: Record<string, any>
  status: string
}

const router = useRouter()
const loading = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const items = ref<AiStrategy[]>([])

const dialogVisible = ref(false)
const saving = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  scene: '',
  displayName: '',
  promptTemplate: '',
  status: 'ENABLED',
  generationConfigJson: '{\n  "temperature": 0.4,\n  "max_output_tokens": 800\n}\n',
  constraintsJson: '{\n  "forbid_medical_diagnosis": true,\n  "safe_mode": true\n}\n',
})

function resetForm() {
  form.scene = ''
  form.displayName = ''
  form.promptTemplate = ''
  form.status = 'ENABLED'
  form.generationConfigJson = '{\n  "temperature": 0.4,\n  "max_output_tokens": 800\n}\n'
  form.constraintsJson = '{\n  "forbid_medical_diagnosis": true,\n  "safe_mode": true\n}\n'
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
    const data = await apiRequest<{ items: AiStrategy[] }>('/admin/ai/strategies')
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

function openEdit(row: AiStrategy) {
  resetForm()
  isEditing.value = true
  editingId.value = row.id
  form.scene = row.scene
  form.displayName = row.displayName
  form.promptTemplate = row.promptTemplate
  form.status = row.status
  form.generationConfigJson = JSON.stringify(row.generationConfig ?? {}, null, 2) + '\n'
  form.constraintsJson = JSON.stringify(row.constraints ?? {}, null, 2) + '\n'
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const generationConfig = safeParseJson('generationConfig', form.generationConfigJson)
    const constraints = safeParseJson('constraints', form.constraintsJson)

    if (!isEditing.value) {
      await apiRequest<AiStrategy>('/admin/ai/strategies', {
        method: 'POST',
        idempotencyKey: newIdempotencyKey(),
        body: {
          scene: form.scene,
          displayName: form.displayName,
          promptTemplate: form.promptTemplate,
          generationConfig,
          constraints,
        },
      })
      ElMessage.success('已创建')
    } else {
      await apiRequest<AiStrategy>(`/admin/ai/strategies/${editingId.value}`, {
        method: 'PUT',
        idempotencyKey: newIdempotencyKey(),
        body: {
          displayName: form.displayName,
          promptTemplate: form.promptTemplate,
          generationConfig,
          constraints,
          status: form.status,
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

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="AI Strategy（业务能力）" />

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
            Strategy 描述“是干嘛的、怎么说话、有什么边界”。不允许出现 model/apiKey/appId 等技术字段。
          </div>
          <div>
            <el-button type="primary" @click="openCreate">新增 Strategy</el-button>
            <el-button :disabled="loading" @click="load">刷新</el-button>
          </div>
        </div>

        <el-table :data="items" size="small" border>
          <el-table-column prop="scene" label="scene" min-width="160" />
          <el-table-column prop="displayName" label="名称" min-width="160" />
          <el-table-column prop="providerId" label="绑定 ProviderId" min-width="220" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑 Strategy' : '新增 Strategy'" width="760px">
      <el-form label-width="150px">
        <el-form-item label="scene">
          <el-input v-model="form.scene" :disabled="isEditing" placeholder="例如：knowledge_qa" />
        </el-form-item>
        <el-form-item label="展示名称">
          <el-input v-model="form.displayName" placeholder="例如：健康知识助手" />
        </el-form-item>
        <el-form-item label="promptTemplate">
          <el-input v-model="form.promptTemplate" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="generationConfig（JSON）">
          <el-input v-model="form.generationConfigJson" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="constraints（JSON）">
          <el-input v-model="form.constraintsJson" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item v-if="isEditing" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="ENABLED" value="ENABLED" />
            <el-option label="DISABLED" value="DISABLED" />
          </el-select>
        </el-form-item>
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="绑定 Provider 请到「AI 绑定关系」页操作（避免把技术绑定混入业务编辑）。"
        />
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>


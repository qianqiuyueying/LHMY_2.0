<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type AiProvider = { id: string; name: string; providerType: string; status: string }
type AiStrategy = { id: string; scene: string; displayName: string; providerId?: string | null; status: string }

const router = useRouter()
const loading = ref(false)
const resetting = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')

const providers = ref<AiProvider[]>([])
const strategies = ref<AiStrategy[]>([])

const providerOptions = computed(() =>
  providers.value.map((p) => ({
    label: `${p.name} (${p.providerType})`,
    value: p.id,
  })),
)

async function load() {
  loading.value = true
  try {
    const [p, s] = await Promise.all([
      apiRequest<{ items: AiProvider[] }>('/admin/ai/providers'),
      apiRequest<{ items: AiStrategy[] }>('/admin/ai/strategies'),
    ])
    providers.value = p.items ?? []
    strategies.value = s.items ?? []
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

async function bind(strategyId: string, providerId: string | null) {
  try {
    await apiRequest(`/admin/ai/strategies/${strategyId}/bind-provider`, {
      method: 'POST',
      idempotencyKey: newIdempotencyKey(),
      body: { providerId },
    })
    ElMessage.success('已更新绑定')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '绑定失败' })
  }
}

async function devReset() {
  resetting.value = true
  try {
    await apiRequest('/admin/ai/dev/reset', {
      method: 'POST',
      idempotencyKey: newIdempotencyKey(),
      body: { resetAudit: true, resetChatAudits: false },
    })
    ElMessage.success('已清空 AI 配置（Provider/Strategy/绑定）')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '清空失败' })
  } finally {
    resetting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="AI 绑定关系（Strategy ↔ Provider）" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <template v-else>
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="怎么用：1）先创建 Provider（技术配置）2）创建 Strategy（业务能力，scene=knowledge_qa）3）在这里把 knowledge_qa 绑定到某个 Provider。小程序端只传 scene，不会感知模型/SDK。"
        />
        <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <div style="color: rgba(0, 0, 0, 0.55); font-size: 12px">
            你看到的“已有数据”来自数据库（容器重启不会清空 DB volume）。开发/测试可点右侧按钮清空。
          </div>
          <div style="display: flex; gap: 8px">
            <el-button type="danger" :loading="resetting" @click="devReset">清空 AI 配置</el-button>
            <el-button :disabled="loading" @click="load">刷新</el-button>
          </div>
        </div>

        <el-table :data="strategies" size="small" border>
          <el-table-column prop="scene" label="scene" min-width="160" />
          <el-table-column prop="displayName" label="名称" min-width="160" />
          <el-table-column prop="status" label="Strategy 状态" width="120" />
          <el-table-column label="绑定 Provider" min-width="360">
            <template #default="{ row }">
              <el-select
                :model-value="row.providerId || ''"
                placeholder="未绑定"
                style="width: 100%"
                @change="(v: string) => bind(row.id, v || null)"
              >
                <el-option label="（取消绑定）" value="" />
                <el-option v-for="x in providerOptions" :key="x.value" :label="x.label" :value="x.value" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>
  </div>
</template>


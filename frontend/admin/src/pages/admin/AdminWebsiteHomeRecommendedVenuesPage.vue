<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type ItemView = {
  venueId: string
  name: string
  publishStatus: string
}

type AdminRecommendedResp = {
  version: string
  items: ItemView[]
}

type AdminVenueListItem = {
  id: string
  name: string
  publishStatus: string
  providerId?: string
  providerName?: string
}
type AdminVenueListResp = {
  items: AdminVenueListItem[]
  page: number
  pageSize: number
  total: number
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const state = reactive({
  version: '0',
  items: [] as ItemView[],
  newVenueId: '',
})

const venueSearchLoading = ref(false)
const venueSearchKeyword = ref('')
const venueOptions = ref<Array<{ value: string; label: string; name: string; publishStatus: string }>>([])

const hasDuplicates = computed(() => {
  const ids = state.items.map((x) => x.venueId.trim()).filter(Boolean)
  return new Set(ids).size !== ids.length
})

async function searchVenues(keyword: string) {
  const kw = String(keyword || '').trim()
  venueSearchKeyword.value = kw
  if (!kw) {
    venueOptions.value = []
    return
  }
  venueSearchLoading.value = true
  try {
    const data = await apiRequest<AdminVenueListResp>('/admin/venues', {
      query: { keyword: kw, publishStatus: 'PUBLISHED', page: 1, pageSize: 20 },
    })
    const items = (data.items || []).map((x) => {
      const id = String(x.id || '').trim()
      const name = String(x.name || '').trim()
      const ps = String(x.publishStatus || '').trim()
      const providerName = String((x as any).providerName || '').trim()
      const label = `${name || id}${providerName ? `（${providerName}）` : ''}（id=${id}）`
      return { value: id, label, name, publishStatus: ps }
    })
    venueOptions.value = items.filter((x) => x.value)
  } catch (e: any) {
    venueOptions.value = []
    handleApiError(e, { router, fallbackMessage: '场所搜索失败' })
  } finally {
    venueSearchLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<AdminRecommendedResp>('/admin/website/home/recommended-venues')
    state.version = data.version || '0'
    state.items = (data.items || []).map((x) => ({
      venueId: String(x.venueId || '').trim(),
      name: String(x.name || ''),
      publishStatus: String(x.publishStatus || ''),
    }))
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

function add() {
  const vid = state.newVenueId.trim()
  if (!vid) return ElMessage.error('请选择场所')
  if (state.items.some((x) => x.venueId === vid)) return ElMessage.error('该场所已在推荐列表中')

  const opt = venueOptions.value.find((x) => x.value === vid)
  state.items.push({ venueId: vid, name: opt?.name || '', publishStatus: opt?.publishStatus || '' })
  state.newVenueId = ''
}

function removeAt(i: number) {
  state.items.splice(i, 1)
}

function moveUp(i: number) {
  if (i <= 0) return
  const a = state.items[i]
  const b = state.items[i - 1]
  if (!a || !b) return
  state.items[i - 1] = a
  state.items[i] = b
}

function moveDown(i: number) {
  if (i >= state.items.length - 1) return
  const a = state.items[i]
  const b = state.items[i + 1]
  if (!a || !b) return
  state.items[i + 1] = a
  state.items[i] = b
}

async function save() {
  const venueIds = state.items.map((x) => x.venueId.trim()).filter(Boolean)
  if (venueIds.length !== state.items.length) return ElMessage.error('推荐列表中存在空的场所ID')
  if (hasDuplicates.value) return ElMessage.error('推荐列表中存在重复的场所ID')

  saving.value = true
  try {
    await apiRequest('/admin/website/home/recommended-venues', {
      method: 'PUT',
      body: { items: venueIds.map((venueId) => ({ venueId })) },
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
    <PageHeaderBar title="官网基础配置：首页推荐场所" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <div v-else>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px">
          <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0">
            <el-select
              v-model="state.newVenueId"
              filterable
              remote
              clearable
              reserve-keyword
              :remote-method="searchVenues"
              :loading="venueSearchLoading"
              placeholder="搜索并选择场所（仅 PUBLISHED）"
              style="max-width: 520px; width: 100%"
            >
              <el-option v-for="opt in venueOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-button type="primary" @click="add">添加</el-button>
            <span style="font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ state.version }}</span>
          </div>
          <div style="display: flex; gap: 8px">
            <el-button :disabled="loading" @click="load">刷新</el-button>
            <el-button type="primary" :loading="saving" :disabled="hasDuplicates" @click="save">保存</el-button>
          </div>
        </div>

        <el-alert
          v-if="hasDuplicates"
          type="warning"
          show-icon
          title="推荐列表存在重复的场所ID，请先去重再保存"
          style="margin-bottom: 12px"
        />

        <el-table :data="state.items" row-key="venueId" border style="width: 100%">
          <el-table-column type="index" width="60" label="#" />
          <el-table-column prop="venueId" label="场所ID" min-width="220" />
          <el-table-column prop="name" label="场所名称（回显）" min-width="220" />
          <el-table-column prop="publishStatus" label="发布状态（回显）" width="140" />
          <el-table-column label="操作" width="220">
            <template #default="{ $index }">
              <el-button size="small" @click="moveUp($index)">上移</el-button>
              <el-button size="small" @click="moveDown($index)">下移</el-button>
              <el-button size="small" type="danger" @click="removeAt($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>



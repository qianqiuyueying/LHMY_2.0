<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type EnterpriseItem = {
  id: string
  name: string
  cityCode?: string | null
  source: 'USER_FIRST_BINDING' | 'IMPORT' | 'MANUAL'
  createdAt: string
}

type EnterpriseDetail = {
  id: string
  name: string
  cityCode?: string | null
  source: 'USER_FIRST_BINDING' | 'IMPORT' | 'MANUAL'
  createdAt: string
}

type RegionOption = { code: string; name: string; sort: number }

const filters = reactive({
  keyword: '',
  cityCode: '',
  source: '' as '' | EnterpriseItem['source'],
})

const regionLoading = ref(false)
const regionOptions = ref<RegionOption[]>([])

async function loadCityOptions() {
  // 读侧：仅已发布/启用项；性能：不分页拉全量（全国地级市量级可接受）
  regionLoading.value = true
  try {
    const data = await apiRequest<{ items: RegionOption[]; version: string }>('/regions/cities', { auth: false })
    regionOptions.value = (data.items || []).filter((x) => String(x.code || '').startsWith('CITY:'))
  } catch {
    regionOptions.value = []
  } finally {
    regionLoading.value = false
  }
}

const loading = ref(false)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const rows = ref<EnterpriseItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const drawerOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<EnterpriseDetail | null>(null)

const editDialogOpen = ref(false)
const editLoading = ref(false)
const editForm = reactive({ id: '', name: '' })

const router = useRouter()

function reset() {
  filters.keyword = ''
  filters.cityCode = ''
  filters.source = ''
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<EnterpriseItem>>('/admin/enterprises', {
      query: {
        keyword: filters.keyword || null,
        cityCode: filters.cityCode || null,
        source: filters.source || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items || []
    total.value = data.total
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

async function openDetail(id: string) {
  drawerOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await apiRequest<EnterpriseDetail>(`/admin/enterprises/${encodeURIComponent(id)}`)
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    detailLoading.value = false
  }
}

function openEdit(row: EnterpriseItem) {
  editForm.id = row.id
  editForm.name = row.name
  editDialogOpen.value = true
}

async function saveEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('企业名称不能为空')
    return
  }
  editLoading.value = true
  try {
    await apiRequest(`/admin/enterprises/${encodeURIComponent(editForm.id)}`, {
      method: 'PUT',
      body: { name: editForm.name.trim() }, // v1 固化：仅允许更新 name
    })
    ElMessage.success('已保存')
    editDialogOpen.value = false
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    editLoading.value = false
  }
}

function goEnterpriseUsers(enterpriseId: string) {
  const id = String(enterpriseId || '').trim()
  if (!id) return
  router.push({ path: '/admin/users', query: { enterpriseId: id } })
}

onMounted(async () => {
  await loadCityOptions()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="企业信息库" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="企业名称" style="width: 220px" />
        </el-form-item>
        <el-form-item label="城市">
          <el-select
            v-model="filters.cityCode"
            filterable
            clearable
            placeholder="全部城市"
            style="width: 260px"
            :loading="regionLoading"
          >
            <el-option label="全部" value="" />
            <el-option v-for="c in regionOptions" :key="c.code" :label="`${c.name}（${c.code}）`" :value="c.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.source" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="用户首次绑定（USER_FIRST_BINDING）" value="USER_FIRST_BINDING" />
            <el-option label="导入（IMPORT）" value="IMPORT" />
            <el-option label="手动创建（MANUAL）" value="MANUAL" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无企业" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="企业ID" width="240" />
        <el-table-column prop="name" label="企业名称" min-width="220" />
        <el-table-column prop="cityCode" label="城市" width="160" />
        <el-table-column prop="source" label="来源" width="200" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button type="primary" link @click="openDetail(scope.row.id)">详情</el-button>
            <el-button type="primary" link @click="goEnterpriseUsers(scope.row.id)">查看员工</el-button>
            <el-button type="primary" link @click="openEdit(scope.row)">编辑名称</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @change="load"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerOpen" title="企业详情" size="520px">
      <el-skeleton v-if="detailLoading" :rows="8" animated />
      <el-empty v-else-if="!detail" description="暂无数据" />
      <el-descriptions v-else :column="1" border>
        <el-descriptions-item label="企业ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="企业名称">{{ detail.name }}</el-descriptions-item>
        <el-descriptions-item label="城市">{{ detail.cityCode || '—' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ detail.source }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.createdAt }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="detail" style="margin-top: 12px">
        <el-button type="primary" @click="goEnterpriseUsers(detail.id)">查看该企业绑定的员工用户</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="editDialogOpen" title="编辑企业名称" width="520px">
      <el-form label-width="120px">
        <el-form-item label="企业ID"><el-input v-model="editForm.id" disabled /></el-form-item>
        <el-form-item label="企业名称"><el-input v-model="editForm.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped></style>

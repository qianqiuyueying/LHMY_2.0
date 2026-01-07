<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { fmtBeijingDateTime } from '../../lib/time'

type ServiceLine = { serviceType: string; totalCount: number }

type ServicePackageItem = {
  id: string
  name: string
  regionLevel: string
  tier: string
  description?: string | null
  serviceCount: number
  createdAt?: string | null
  updatedAt?: string | null
}

type DetailResp = {
  id: string
  name: string
  regionLevel: string
  tier: string
  description?: string | null
  services: ServiceLine[]
  locked: boolean
}

const keyword = ref('')
const loading = ref(false)
const rows = ref<ServicePackageItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

const editorOpen = ref(false)
const editorMode = ref<'CREATE' | 'EDIT'>('CREATE')
const locked = ref(false)

type ServiceCategory = { id: string; code: string; displayName: string; status: 'ENABLED' | 'DISABLED'; sort: number }
const categoriesLoading = ref(false)
const categories = ref<ServiceCategory[]>([])
const enabledCategories = computed(() => (categories.value || []).filter((x) => x.status === 'ENABLED'))
const categoryNameByCode = computed(() => {
  const m = new Map<string, string>()
  for (const c of categories.value) m.set(c.code, c.displayName)
  return m
})

const form = reactive({
  id: '',
  name: '',
  regionLevel: 'CITY',
  tier: 'DEFAULT',
  description: '',
  services: [] as ServiceLine[],
})

async function loadCategories() {
  categoriesLoading.value = true
  try {
    const data = await apiRequest<PageResp<ServiceCategory>>('/admin/service-categories', { query: { page: 1, pageSize: 200 } })
    categories.value = data.items || []
  } catch {
    categories.value = []
  } finally {
    categoriesLoading.value = false
  }
}

function resetSearch() {
  keyword.value = ''
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<ServicePackageItem>>('/admin/service-packages', {
      query: { page: page.value, pageSize: pageSize.value, keyword: keyword.value || null },
    })
    rows.value = data.items || []
    total.value = data.total
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    errorText.value = e?.apiError?.message ?? '加载失败'
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editorMode.value = 'CREATE'
  locked.value = false
  form.id = ''
  form.name = ''
  form.regionLevel = 'CITY'
  form.tier = 'DEFAULT'
  form.description = ''
  form.services = [{ serviceType: enabledCategories.value[0]?.code || '', totalCount: 1 }]
  editorOpen.value = true
}

async function openEdit(row: ServicePackageItem) {
  editorMode.value = 'EDIT'
  loading.value = true
  try {
    const data = await apiRequest<DetailResp>(`/admin/service-packages/${row.id}`)
    form.id = data.id
    form.name = data.name
    form.regionLevel = data.regionLevel
    form.tier = data.tier
    form.description = data.description ?? ''
    form.services = (data.services || []).map((x) => ({ serviceType: x.serviceType, totalCount: Number(x.totalCount) }))
    if (form.services.length === 0) form.services = [{ serviceType: '', totalCount: 1 }]
    locked.value = !!data.locked
    editorOpen.value = true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    loading.value = false
  }
}

function addLine() {
  form.services.push({ serviceType: enabledCategories.value[0]?.code || '', totalCount: 1 })
}

function removeLine(idx: number) {
  if (form.services.length <= 1) return
  form.services.splice(idx, 1)
}

function validateBeforeSave(): string | null {
  if (!String(form.name || '').trim()) return '名称不能为空'
  if (!String(form.regionLevel || '').trim()) return 'regionLevel 不能为空'
  if (!String(form.tier || '').trim()) return 'tier 不能为空'
  if (!Array.isArray(form.services) || form.services.length === 0) return '服务明细不能为空'
  const seen = new Set<string>()
  for (const x of form.services) {
    const st = String(x.serviceType || '').trim()
    if (!st) return '服务类目 serviceType 不能为空'
    if (seen.has(st)) return `服务类目重复：${st}`
    seen.add(st)
    const c = Number(x.totalCount)
    if (!Number.isFinite(c) || c < 1) return '次数 totalCount 必须为 >= 1 的数字'
  }
  return null
}

async function save() {
  const err = validateBeforeSave()
  if (err) return ElMessage.error(err)

  const payload = {
    name: String(form.name).trim(),
    regionLevel: String(form.regionLevel).trim(),
    tier: String(form.tier).trim(),
    description: String(form.description || '').trim() || null,
    services: form.services.map((x) => ({ serviceType: String(x.serviceType).trim(), totalCount: Number(x.totalCount) })),
  }

  try {
    if (editorMode.value === 'CREATE') {
      await apiRequest('/admin/service-packages', { method: 'POST', body: payload, idempotencyKey: newIdempotencyKey() })
      ElMessage.success('已创建')
    } else {
      await apiRequest(`/admin/service-packages/${form.id}`, { method: 'PUT', body: payload })
      ElMessage.success('已保存')
    }
    editorOpen.value = false
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

onMounted(async () => {
  await loadCategories()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="服务包模板管理" />

    <el-card style="margin-top: 12px">
      <el-alert
        title="用于配置健行天下“高端服务卡/服务包模板”（区域级别、等级、服务类目×次数）。若模板已产生实例（已有成交交付），将自动锁定 regionLevel/tier/明细，仅允许修改名称/说明。"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

      <el-form :inline="true" label-width="90px">
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="按名称模糊搜索" style="width: 260px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="success" @click="openCreate">新增模板</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无服务包模板" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="模板ID" width="260" />
        <el-table-column prop="name" label="名称" min-width="220" />
        <el-table-column prop="regionLevel" label="区域级别" width="120" />
        <el-table-column prop="tier" label="等级" width="140" />
        <el-table-column prop="serviceCount" label="服务项数" width="100" />
        <el-table-column prop="updatedAt" label="更新时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column label="操作" width="140">
          <template #default="scope">
            <el-button type="primary" size="small" @click="openEdit(scope.row)">编辑</el-button>
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

    <el-dialog v-model="editorOpen" :title="editorMode === 'CREATE' ? '新增服务包模板' : '编辑服务包模板'" width="920px">
      <el-alert
        v-if="editorMode === 'EDIT' && locked"
        title="该模板已产生实例：regionLevel / tier / 服务类目×次数 已锁定，仅允许修改名称/说明。"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

      <el-form label-width="110px">
        <el-form-item v-if="editorMode === 'EDIT'" label="模板ID">
          <el-input v-model="form.id" disabled />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="区域级别">
          <el-select v-model="form.regionLevel" style="width: 200px" :disabled="locked">
            <el-option label="城市（CITY）" value="CITY" />
            <el-option label="省（PROVINCE）" value="PROVINCE" />
            <el-option label="全国（COUNTRY）" value="COUNTRY" />
          </el-select>
        </el-form-item>
        <el-form-item label="等级(tier)">
          <el-input v-model="form.tier" placeholder="例如：DEFAULT / T1 / T2" style="width: 240px" :disabled="locked" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>

        <el-form-item label="服务类目×次数">
          <div style="width: 100%">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px">
              <div style="color: var(--lh-muted)">
                至少 1 项；服务类目（serviceType）来自“服务大类管理”，需在字典中启用后才能选择
              </div>
              <el-button :disabled="locked" @click="addLine">新增一行</el-button>
            </div>
            <el-table :data="form.services" border size="small" style="width: 100%">
              <el-table-column label="服务编码（serviceType）" min-width="240">
                <template #default="scope">
                  <el-select
                    v-model="scope.row.serviceType"
                    filterable
                    placeholder="选择服务大类"
                    :disabled="locked"
                    :loading="categoriesLoading"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="c in enabledCategories"
                      :key="c.code"
                      :label="`${c.displayName}（${c.code}）`"
                      :value="c.code"
                    />
                  </el-select>
                  <div v-if="scope.row.serviceType && categoryNameByCode.get(scope.row.serviceType)" style="margin-top: 4px; font-size: 12px; color: var(--lh-muted-2)">
                    已选：{{ categoryNameByCode.get(scope.row.serviceType) }}（{{ scope.row.serviceType }}）
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="次数（totalCount）" width="180">
                <template #default="scope">
                  <el-input-number v-model="scope.row.totalCount" :min="1" :disabled="locked" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="scope">
                  <el-button :disabled="locked || form.services.length <= 1" type="danger" size="small" @click="removeLine(scope.$index)"
                    >删除</el-button
                  >
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>


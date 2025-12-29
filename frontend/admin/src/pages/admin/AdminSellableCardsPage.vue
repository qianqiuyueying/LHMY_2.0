<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type Status = 'ENABLED' | 'DISABLED'
type SellableCard = {
  id: string
  name: string
  servicePackageTemplateId: string
  regionLevel: 'CITY' | 'PROVINCE' | 'COUNTRY'
  priceOriginal: number
  status: Status
  sort: number
  createdAt?: string | null
  updatedAt?: string | null
}

const STATUS_LABEL: Record<Status, string> = { ENABLED: '启用', DISABLED: '停用' }

type TemplateLite = { id: string; name: string; regionLevel: string; tier: string }

const loading = ref(false)
const rows = ref<SellableCard[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

const filters = reactive({
  status: '' as '' | Status,
  keyword: '',
})

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<SellableCard>>('/admin/sellable-cards', {
      query: { status: filters.status || null, keyword: filters.keyword || null, page: page.value, pageSize: pageSize.value },
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

const editorOpen = ref(false)
const editorMode = ref<'CREATE' | 'EDIT'>('CREATE')
const editorTitle = computed(() => (editorMode.value === 'CREATE' ? '新增可售卡' : '编辑可售卡'))
const editingId = ref<string | null>(null)

const templatesLoading = ref(false)
const templates = ref<TemplateLite[]>([])

const form = reactive({
  name: '',
  servicePackageTemplateId: '',
  regionLevel: 'CITY' as 'CITY' | 'PROVINCE' | 'COUNTRY',
  priceOriginal: 0,
  sort: 0,
})

async function loadTemplates() {
  templatesLoading.value = true
  try {
    const data = await apiRequest<PageResp<TemplateLite>>('/admin/service-packages', { query: { page: 1, pageSize: 200 } })
    templates.value = data.items || []
  } catch {
    templates.value = []
  } finally {
    templatesLoading.value = false
  }
}

function openCreate() {
  editorMode.value = 'CREATE'
  editingId.value = null
  Object.assign(form, { name: '', servicePackageTemplateId: '', regionLevel: 'CITY', priceOriginal: 0, sort: 0 })
  editorOpen.value = true
}

function openEdit(row: SellableCard) {
  editorMode.value = 'EDIT'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    servicePackageTemplateId: row.servicePackageTemplateId,
    regionLevel: row.regionLevel,
    priceOriginal: Number(row.priceOriginal ?? 0),
    sort: Number(row.sort ?? 0),
  })
  editorOpen.value = true
}

async function save() {
  const name = String(form.name || '').trim()
  const servicePackageTemplateId = String(form.servicePackageTemplateId || '').trim()
  const regionLevel = String(form.regionLevel || '').trim().toUpperCase()
  const priceOriginal = Number(form.priceOriginal ?? 0)
  const sort = Number(form.sort ?? 0)

  if (!name) return ElMessage.error('名称不能为空')
  if (!servicePackageTemplateId) return ElMessage.error('servicePackageTemplateId 不能为空')
  if (!['CITY', 'PROVINCE', 'COUNTRY'].includes(regionLevel)) return ElMessage.error('regionLevel 不合法')
  if (!Number.isFinite(priceOriginal) || priceOriginal < 0) return ElMessage.error('售价必须为 >= 0 的数字')

  const body = { name, servicePackageTemplateId, regionLevel, priceOriginal, sort }
  try {
    if (editorMode.value === 'CREATE') {
      await apiRequest('/admin/sellable-cards', { method: 'POST', body })
      ElMessage.success('已新增')
    } else {
      await apiRequest(`/admin/sellable-cards/${editingId.value}`, { method: 'PUT', body })
      ElMessage.success('已保存')
    }
    editorOpen.value = false
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

async function enable(row: SellableCard) {
  try {
    await apiRequest(`/admin/sellable-cards/${row.id}/enable`, { method: 'POST' })
    ElMessage.success('已启用')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function disable(row: SellableCard) {
  try {
    await ElMessageBox.confirm('确认停用该可售卡？停用后经销商不可选择，历史链接打开也将无法下单。', '停用', {
      type: 'warning',
      confirmButtonText: '停用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/sellable-cards/${row.id}/disable`, { method: 'POST' })
    ElMessage.success('已停用')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

onMounted(load)
onMounted(loadTemplates)
</script>

<template>
  <div>
    <PageHeaderBar title="可售卡管理（经销商选卡售卖）" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>说明（v2 口径）</template>
      <div style="line-height: 1.7">
        <div>本页维护“经销商生成链接时可选择卖哪张卡”的可售卡清单。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">
          可售卡仅配置“区域级别”（市/省/全国）；消费者在 H5 下单时选择具体区域（并写入订单/权益范围）。
        </div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="启用（ENABLED）" value="ENABLED" />
            <el-option label="停用（DISABLED）" value="DISABLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="名称/ID/productId/templateId/regionLevel" style="width: 320px" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            @click="
              page = 1;
              load()
            "
          >
            查询
          </el-button>
          <el-button
            @click="
              filters.status = '';
              filters.keyword = '';
              page = 1;
              load()
            "
          >
            重置
          </el-button>
          <el-button type="success" @click="openCreate">新增</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无可售卡" description="建议先新增一条：绑定计价商品 + 服务包模板 + 区域级别（市/省/全国）。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="可售卡ID" width="240" />
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="servicePackageTemplateId" label="模板ID" width="220" />
        <el-table-column prop="regionLevel" label="区域级别" width="120" />
      <el-table-column prop="priceOriginal" label="售价（元）" width="140" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small" :type="scope.row.status === 'ENABLED' ? 'success' : 'info'">
                {{ STATUS_LABEL[scope.row.status as keyof typeof STATUS_LABEL] ?? scope.row.status }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <el-button size="small" type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button v-if="scope.row.status === 'ENABLED'" size="small" type="warning" @click="disable(scope.row)">停用</el-button>
            <el-button v-else size="small" type="success" @click="enable(scope.row)">启用</el-button>
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

    <el-dialog v-model="editorOpen" :title="editorTitle" width="820px">
      <el-form label-width="160px">
        <el-form-item label="名称（给经销商看）">
          <el-input v-model="form.name" placeholder="例如：健身市卡-北京" style="width: 520px" />
        </el-form-item>
        <el-form-item label="服务包模板（必填）">
          <el-select
            v-model="form.servicePackageTemplateId"
            filterable
            placeholder="请选择"
            style="width: 520px"
            :loading="templatesLoading"
            @change="
              (id: string) => {
                const t = templates.find((x) => x.id === id)
                if (t?.regionLevel) form.regionLevel = (String(t.regionLevel).toUpperCase() as any) || form.regionLevel
              }
            "
          >
            <el-option v-for="t in templates" :key="t.id" :label="`${t.name}（${t.regionLevel}/${t.tier}｜${t.id}）`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="售价（唯一）">
          <el-input-number v-model="form.priceOriginal" :min="0" :max="999999" :precision="2" />
          <div style="margin-top: 6px; font-size: 12px; color: var(--lh-muted)">
            说明：v2.1 口径下，健行天下订单计价以可售卡的售价为准，不再依赖任何“基建联防商品/服务”作为计价载体。
          </div>
        </el-form-item>
        <el-form-item label="区域级别（regionLevel）">
          <el-radio-group v-model="form.regionLevel">
            <el-radio-button label="CITY">市卡</el-radio-button>
            <el-radio-button label="PROVINCE">省卡</el-radio-button>
            <el-radio-button label="COUNTRY">全国卡</el-radio-button>
          </el-radio-group>
          <div style="margin-top: 6px; font-size: 12px; color: var(--lh-muted)">
            说明：可售卡只配置“级别”；消费者在 H5 购买时选择具体城市/省份（全国卡无需选择）。
          </div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="9999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>


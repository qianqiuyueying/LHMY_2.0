<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import { uploadImage } from '../../lib/uploads'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type PriceObj = { original: number; employee?: number | null; member?: number | null; activity?: number | null }
type ProductItem = {
  id: string
  title: string
  fulfillmentType: 'SERVICE' | 'PHYSICAL_GOODS'
  categoryId?: string | null
  coverImageUrl?: string | null
  imageUrls?: string[] | null
  description?: string | null
  price: PriceObj
  stock?: number | null
  reservedStock?: number | null
  weight?: number | null
  shippingFee?: number | null
  tags?: string[] | null
  status: 'PENDING_REVIEW' | 'ON_SALE' | 'OFF_SHELF' | 'REJECTED'
  rejectReason?: string | null
  rejectedAt?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

const PRODUCT_STATUS_LABEL: Record<ProductItem['status'], string> = {
  PENDING_REVIEW: '待审核',
  ON_SALE: '已上架',
  OFF_SHELF: '已下架',
  REJECTED: '已驳回',
}

function statusTagType(status: ProductItem['status']): 'info' | 'warning' | 'success' | 'danger' {
  if (status === 'PENDING_REVIEW') return 'warning'
  if (status === 'ON_SALE') return 'success'
  if (status === 'REJECTED') return 'danger'
  return 'info'
}

const FULFILLMENT_LABEL: Record<ProductItem['fulfillmentType'], string> = {
  SERVICE: '服务',
  PHYSICAL_GOODS: '物流商品',
}

const loading = ref(false)
const submitting = ref(false)
const tagsLoading = ref(false)
const tagOptions = ref<string[]>([])
const rows = ref<ProductItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

// el-upload 的 on-change 可能在同一文件的状态变化中触发多次，导致重复上传
const _uploadingUids = new Set<string>()

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<ProductItem>>('/provider/products', { query: { page: page.value, pageSize: pageSize.value } })
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
    ElMessage.error(
      `${msg}${errorCode.value ? `（code=${errorCode.value}）` : ''}${errorRequestId.value ? `（requestId=${errorRequestId.value}）` : ''}`,
    )
  } finally {
    loading.value = false
  }
}

const editorOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
  title: '',
  fulfillmentType: 'SERVICE' as ProductItem['fulfillmentType'],
  coverImageUrl: '' as string,
  imageUrls: [] as string[],
  description: '' as string,
  tags: [] as string[],
  original: 0,
  employee: null as number | null,
  member: null as number | null,
  activity: null as number | null,
  stock: null as number | null,
  weight: null as number | null,
  shippingFee: null as number | null,
  // vNow：SERVICE 商品预约配置
  serviceType: '' as string,
  bookingRequired: false as boolean,
  applicableRegions: [] as string[],
})
type ServiceCategory = { id: string; code: string; displayName: string }
type RegionOption = { code: string; name: string; sort: number }
const categoriesLoading = ref(false)
const categories = ref<ServiceCategory[]>([])
const regionsLoading = ref(false)
const regionOptions = ref<RegionOption[]>([])

// 业务口径：provider 在哪，场所就得在哪；“适用地区”只能是当前场所所在城市
const venueCityCode = ref('')

async function loadServiceCategories() {
  categoriesLoading.value = true
  try {
    const data = await apiRequest<PageResp<ServiceCategory>>('/service-categories', { query: { page: 1, pageSize: 200 } })
    categories.value = data.items || []
  } catch {
    categories.value = []
  } finally {
    categoriesLoading.value = false
  }
}

async function loadRegions() {
  regionsLoading.value = true
  try {
    const data = await apiRequest<{ items: RegionOption[]; version: string }>('/regions/cities', { auth: false })
    const all = (data.items || []).slice().sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0))
    if (venueCityCode.value) {
      const only = all.filter((x) => String(x?.code || '') === venueCityCode.value)
      regionOptions.value = only.length > 0 ? only : [{ code: venueCityCode.value, name: venueCityCode.value, sort: 0 }]
    } else {
      regionOptions.value = all
    }
  } catch {
    regionOptions.value = []
  } finally {
    regionsLoading.value = false
  }
}

async function loadVenueBoundCity() {
  try {
    const v = await apiRequest<{ items: Array<{ id: string }>; total: number }>('/provider/venues')
    const id = String(v?.items?.[0]?.id || '').trim()
    if (!id) {
      venueCityCode.value = ''
      return
    }
    const d = await apiRequest<any>(`/provider/venues/${id}`)
    venueCityCode.value = String(d?.cityCode || '').trim()
  } catch {
    venueCityCode.value = ''
  }
}

const editorTitle = computed(() => (editingId.value ? '编辑商品/服务' : '新增商品/服务'))

async function loadTagOptions() {
  const type = form.fulfillmentType === 'PHYSICAL_GOODS' ? 'PRODUCT' : 'SERVICE'
  tagsLoading.value = true
  try {
    const data = await apiRequest<{ items: Array<{ id: string; name: string }> }>('/tags', { query: { type } })
    const names = (data.items || []).map((x) => String(x.name || '').trim()).filter((x) => !!x)
    // 保留已选标签（即使已停用/被移除）
    const picked = (form.tags || []).map((x) => String(x || '').trim()).filter((x) => !!x)
    tagOptions.value = Array.from(new Set([...names, ...picked]))
  } catch {
    // 兜底：至少包含已选
    const picked = (form.tags || []).map((x) => String(x || '').trim()).filter((x) => !!x)
    tagOptions.value = Array.from(new Set(picked))
  } finally {
    tagsLoading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    title: '',
    fulfillmentType: 'SERVICE',
    coverImageUrl: '',
    imageUrls: [],
    description: '',
    tags: [],
    original: 0,
    employee: null,
    member: null,
    activity: null,
    stock: null,
    weight: null,
    shippingFee: null,
    serviceType: categories.value[0]?.code || '',
    bookingRequired: false,
    applicableRegions: venueCityCode.value ? [venueCityCode.value] : [],
  })
  editorOpen.value = true
  loadTagOptions()
}

function openEdit(row: ProductItem) {
  editingId.value = row.id
  Object.assign(form, {
    title: row.title,
    fulfillmentType: row.fulfillmentType,
    coverImageUrl: String(row.coverImageUrl || ''),
    imageUrls: Array.isArray(row.imageUrls) ? row.imageUrls.map((x) => String(x)) : [],
    description: String(row.description || ''),
    tags: Array.isArray(row.tags) ? row.tags.map((x) => String(x)) : [],
    original: Number(row.price?.original ?? 0),
    employee: row.price?.employee ?? null,
    member: row.price?.member ?? null,
    activity: row.price?.activity ?? null,
    stock: row.stock ?? null,
    weight: row.weight ?? null,
    shippingFee: row.shippingFee ?? null,
    serviceType: '',
    bookingRequired: false,
    applicableRegions: [],
  })
  editorOpen.value = true
  loadTagOptions()
}

async function uploadCover(f: any) {
  const uid = String(f?.uid || '')
  if (uid) {
    if (_uploadingUids.has(uid)) return
    _uploadingUids.add(uid)
  }
  const raw = f?.raw as File | undefined
  if (!raw) return
  try {
    const url = await uploadImage(raw)
    form.coverImageUrl = url
    ElMessage.success('封面已上传')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? e ?? '上传失败'))
  } finally {
    if (uid) _uploadingUids.delete(uid)
  }
}

async function uploadGallery(f: any) {
  const uid = String(f?.uid || '')
  if (uid) {
    if (_uploadingUids.has(uid)) return
    _uploadingUids.add(uid)
  }
  const raw = f?.raw as File | undefined
  if (!raw) return
  try {
    if (form.imageUrls.length >= 9) return ElMessage.warning('最多上传 9 张详情图')
    const url = await uploadImage(raw)
    form.imageUrls.push(url)
    ElMessage.success('已上传')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? e ?? '上传失败'))
  } finally {
    if (uid) _uploadingUids.delete(uid)
  }
}

function removeGallery(url: string) {
  form.imageUrls = form.imageUrls.filter((x) => x !== url)
}

function validate(): string | null {
  if (!String(form.title || '').trim()) return '名称不能为空'
  const o = Number(form.original)
  if (!Number.isFinite(o) || o < 0) return '原价必须为 >= 0 的数字'
  for (const k of ['employee', 'member', 'activity'] as const) {
    const v = form[k]
    if (v === null || v === undefined) continue
    const n = Number(v)
    if (!Number.isFinite(n) || n < 0) return `价格字段 ${k} 必须为 >= 0 的数字`
  }
  if (form.fulfillmentType === 'PHYSICAL_GOODS') {
    const s = Number(form.stock)
    if (!Number.isFinite(s) || s < 0) return '物流商品库存 stock 必须为 >= 0 的数字'
    const fee = Number(form.shippingFee)
    if (!Number.isFinite(fee) || fee < 0) return '物流商品运费 shippingFee 必须为 >= 0 的数字'
    if (form.weight !== null && form.weight !== undefined) {
      const w = Number(form.weight)
      if (!Number.isFinite(w) || w < 0) return '物流商品重量 weight 必须为 >= 0 的数字'
    }
  }
  return null
}

async function save() {
  const err = validate()
  if (err) return ElMessage.error(err)

  const title = String(form.title).trim()
  const description = String(form.description || '').trim()
  const cover = String(form.coverImageUrl || '').trim()
  const hasSuggestGap = !cover || description.length < 20
  if (hasSuggestGap) {
    try {
      await ElMessageBox.confirm(
        '当前“封面图/介绍”未完善（建议用于审核展示）。仍要继续保存吗？',
        '信息未完善',
        { type: 'warning', confirmButtonText: '继续保存', cancelButtonText: '返回完善' },
      )
    } catch {
      return
    }
  }

  const body = {
    title,
    fulfillmentType: form.fulfillmentType,
    coverImageUrl: cover || null,
    imageUrls: (form.imageUrls || []).slice(0, 9),
    description: description || null,
    tags: (form.tags || []).filter((x) => !!String(x || '').trim()).map((x) => String(x).trim()).slice(0, 10),
    stock: form.fulfillmentType === 'PHYSICAL_GOODS' ? Number(form.stock ?? 0) : null,
    weight: form.fulfillmentType === 'PHYSICAL_GOODS' ? (form.weight === null || form.weight === undefined ? null : Number(form.weight)) : null,
    shippingFee: form.fulfillmentType === 'PHYSICAL_GOODS' ? Number(form.shippingFee ?? 0) : null,
    price: {
      original: Number(form.original),
      employee: form.employee === null || form.employee === undefined ? null : Number(form.employee),
      member: form.member === null || form.member === undefined ? null : Number(form.member),
      activity: form.activity === null || form.activity === undefined ? null : Number(form.activity),
    },
  }

  if (form.fulfillmentType === 'SERVICE') {
    if (!venueCityCode.value) return ElMessage.error('场所尚未绑定城市（cityCode），请先到“场所信息”完善后再保存')
    if (!String(form.serviceType || '').trim()) return ElMessage.error('服务型商品必须选择服务类目（serviceType）')
    ;(body as any).serviceType = String(form.serviceType || '').trim()
    ;(body as any).bookingRequired = !!form.bookingRequired
    // 业务口径：仅允许场所所在城市
    ;(body as any).applicableRegions = [venueCityCode.value]
  }

  submitting.value = true
  try {
    if (!editingId.value) {
      await apiRequest('/provider/products', { method: 'POST', body })
      ElMessage.success('已创建并提交审核')
    } else {
      await apiRequest(`/provider/products/${editingId.value}`, { method: 'PUT', body })
      ElMessage.success('已保存')
    }
    editorOpen.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '保存失败')
  } finally {
    submitting.value = false
  }
}

async function submitForReview(row: ProductItem) {
  try {
    await ElMessageBox.confirm('确认提交审核？提交后需平台审核通过才能上架。', '提交审核', {
      type: 'warning',
      confirmButtonText: '提交',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/provider/products/${row.id}`, { method: 'PUT', body: { status: 'PENDING_REVIEW' } })
    ElMessage.success('已提交审核')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function offShelf(row: ProductItem) {
  try {
    await ElMessageBox.confirm('确认下架？下架后用户将无法继续购买。', '下架', {
      type: 'warning',
      confirmButtonText: '下架',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/provider/products/${row.id}`, { method: 'PUT', body: { status: 'OFF_SHELF' } })
    ElMessage.success('已下架')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

onMounted(async () => {
  await loadServiceCategories()
  await loadVenueBoundCity()
  await loadRegions()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="商品/服务管理（基建联防）" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>说明（v2）</template>
      <div style="line-height: 1.7">
        <div>这里管理的是“基建联防电商侧上架的商品/服务”（需平台审核）。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">v2 支持：服务（SERVICE）与物流商品（PHYSICAL_GOODS）。</div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap">
        <div style="font-weight: 700">列表</div>
        <div style="display: flex; gap: 8px">
          <el-button type="primary" @click="openCreate">新增</el-button>
          <el-button :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无商品/服务" description="建议先点右上角“新增”，创建后会进入待审核状态。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="商品ID" width="220" />
        <el-table-column label="封面" width="90">
          <template #default="scope">
            <el-image v-if="scope.row.coverImageUrl" :src="scope.row.coverImageUrl" style="width: 64px; height: 40px; border-radius: 8px" fit="cover" />
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="名称" min-width="220" />
        <el-table-column label="类型" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.fulfillmentType" placement="top">
              <el-tag size="small">{{ FULFILLMENT_LABEL[scope.row.fulfillmentType as keyof typeof FULFILLMENT_LABEL] ?? scope.row.fulfillmentType }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="库存" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">{{ scope.row.stock ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="占用" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">{{ scope.row.reservedStock ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="运费" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">¥{{ scope.row.shippingFee ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="price.original" label="原价" width="100" />
        <el-table-column label="状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small" :type="statusTagType(scope.row.status)">{{
                PRODUCT_STATUS_LABEL[scope.row.status as keyof typeof PRODUCT_STATUS_LABEL] ?? scope.row.status
              }}</el-tag>
            </el-tooltip>
            <div v-if="scope.row.status === 'REJECTED'" style="margin-top: 6px; font-size: 12px; color: rgba(0, 0, 0, 0.55); line-height: 1.5">
              原因：{{ scope.row.rejectReason || '—' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="scope">
            <el-button size="small" type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button v-if="scope.row.status === 'OFF_SHELF' || scope.row.status === 'REJECTED'" size="small" @click="submitForReview(scope.row)">提交审核</el-button>
            <el-button v-if="scope.row.status === 'ON_SALE'" size="small" type="warning" @click="offShelf(scope.row)">下架</el-button>
            <el-tag v-if="scope.row.status === 'PENDING_REVIEW'" size="small" type="info">待审核</el-tag>
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

    <el-dialog v-model="editorOpen" :title="editorTitle" width="720px">
      <el-form label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="form.title" placeholder="商品/服务名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.fulfillmentType" style="width: 240px" @change="loadTagOptions">
            <el-option label="服务（SERVICE）" value="SERVICE" />
            <el-option label="物流商品（PHYSICAL_GOODS）" value="PHYSICAL_GOODS" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.fulfillmentType === 'SERVICE'" label="服务类目（serviceType）">
          <el-select
            v-model="form.serviceType"
            filterable
            placeholder="请选择服务大类"
            style="width: 420px"
            :loading="categoriesLoading"
          >
            <el-option v-for="c in categories" :key="c.code" :label="`${c.displayName}（${c.code}）`" :value="c.code" />
          </el-select>
          <div style="font-size: 12px; color: var(--lh-muted); margin-top: 6px">
            说明：用于小程序“服务型商品独立预约”解析 serviceType。
          </div>
        </el-form-item>

        <el-form-item v-if="form.fulfillmentType === 'SERVICE'" label="需要预约">
          <el-switch v-model="form.bookingRequired" />
          <div style="font-size: 12px; color: var(--lh-muted); margin-top: 6px">开启后，消费者需先预约再到店核销。</div>
        </el-form-item>

        <el-form-item v-if="form.fulfillmentType === 'SERVICE'" label="适用区域">
          <el-select
            v-model="form.applicableRegions"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            :disabled="true"
            placeholder="已锁定为场所所在城市"
            style="width: 560px"
            :loading="regionsLoading"
          >
            <el-option
              v-for="r in regionOptions"
              :key="r.code"
              :label="`${r.name}（${r.code}）`"
              :value="r.code"
            />
          </el-select>
          <div style="font-size: 12px; color: var(--lh-muted); margin-top: 6px">
            提示：业务口径为“provider 在哪，场所就得在哪”，服务型商品适用地区仅允许为当前场所所在城市。
          </div>
        </el-form-item>
        <el-form-item v-if="form.fulfillmentType === 'PHYSICAL_GOODS'" label="库存">
          <el-input-number v-model="form.stock" :min="0" />
        </el-form-item>
        <el-form-item v-if="form.fulfillmentType === 'PHYSICAL_GOODS'" label="运费（固定）">
          <el-input-number v-model="form.shippingFee" :min="0" />
        </el-form-item>
        <el-form-item v-if="form.fulfillmentType === 'PHYSICAL_GOODS'" label="重量（可选）">
          <el-input-number v-model="form.weight" :min="0" />
          <el-button style="margin-left: 8px" @click="form.weight = null">清空</el-button>
        </el-form-item>
        <el-form-item label="原价">
          <el-input-number v-model="form.original" :min="0" />
        </el-form-item>
        <el-form-item label="封面图（建议）">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
            <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="uploadCover">
              <el-button type="primary">上传封面</el-button>
            </el-upload>
            <el-input v-model="form.coverImageUrl" style="width: 420px" placeholder="或粘贴图片 URL" />
          </div>
          <div v-if="form.coverImageUrl" style="margin-top: 8px">
            <el-image :src="form.coverImageUrl" style="width: 220px; height: 120px; border-radius: 12px" fit="cover" />
          </div>
        </el-form-item>

        <el-form-item label="详情图（可选）">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
            <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" multiple :on-change="uploadGallery">
              <el-button>上传详情图</el-button>
            </el-upload>
            <span style="color: var(--lh-muted)">最多 9 张，当前 {{ form.imageUrls.length }} 张</span>
          </div>
          <div v-if="form.imageUrls.length > 0" style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap">
            <div v-for="u in form.imageUrls" :key="u" style="position: relative">
              <el-image :src="u" style="width: 120px; height: 80px; border-radius: 10px" fit="cover" />
              <el-button size="small" type="danger" style="position: absolute; right: 6px; top: 6px" @click="removeGallery(u)">删</el-button>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="介绍（建议）">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="建议至少 20 个字，便于审核展示" />
        </el-form-item>

        <el-form-item label="标签（可选）">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            :loading="tagsLoading"
            style="width: 420px"
            placeholder="选择标签（由 Admin 维护）"
            @visible-change="(v: boolean) => v && loadTagOptions()"
            @change="loadTagOptions"
          >
            <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="员工价（可选）">
          <el-input-number v-model="form.employee" :min="0" />
          <el-button style="margin-left: 8px" @click="form.employee = null">清空</el-button>
        </el-form-item>
        <el-form-item label="会员价（可选）">
          <el-input-number v-model="form.member" :min="0" />
          <el-button style="margin-left: 8px" @click="form.member = null">清空</el-button>
        </el-form-item>
        <el-form-item label="活动价（可选）">
          <el-input-number v-model="form.activity" :min="0" />
          <el-button style="margin-left: 8px" @click="form.activity = null">清空</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>


<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type VenueLite = { id: string; name: string; publishStatus: string }

type ServiceCategory = { id: string; code: string; displayName: string }
type Onboarding = {
  infraCommerceStatus: 'NOT_OPENED' | 'OPENED'
  healthCardStatus: 'NOT_APPLIED' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
  notes?: string | null
}

type VenueService = {
  id: string
  venueId: string
  serviceType: string
  title: string
  fulfillmentType: 'SERVICE'
  productId?: string | null
  bookingRequired: boolean
  redemptionMethod: 'QR_CODE' | 'VOUCHER_CODE' | 'BOTH'
  applicableRegions?: string[] | null
  status: 'ENABLED' | 'DISABLED'
}

const loading = ref(false)
const venues = ref<VenueLite[]>([])
const venueId = ref('')
const venueName = ref('')
const services = ref<VenueService[]>([])
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const categoriesLoading = ref(false)
const categories = ref<ServiceCategory[]>([])

type RegionOption = { code: string; name: string; sort: number }
const regionsLoading = ref(false)
const regionOptions = ref<RegionOption[]>([])

// 业务口径：provider 在哪，场所就得在哪；“适用地区”只能是当前场所所在城市
const venueCityCode = ref('')

const onboardingLoading = ref(false)
const onboarding = ref<Onboarding | null>(null)

const dialogOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
  serviceType: '',
  title: '',
  fulfillmentType: 'SERVICE' as 'SERVICE',
  productId: '',
  bookingRequired: false,
  redemptionMethod: 'BOTH' as 'QR_CODE' | 'VOUCHER_CODE' | 'BOTH',
  applicableRegions: [] as string[],
  status: 'ENABLED' as 'ENABLED' | 'DISABLED',
})

async function loadRegions() {
  regionsLoading.value = true
  try {
    // 读侧：只返回已发布/启用项（用于下拉）
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

async function loadVenues() {
  const data = await apiRequest<{ items: VenueLite[]; total: number }>('/provider/venues')
  venues.value = data.items
  if (venues.value.length > 1) {
    // 业务规则：单 Provider=单场所；若历史数据异常，默认使用第一条
    ElMessage.warning('检测到多个场所（异常数据），已默认选择第一条作为当前场所')
  }
  if (venues.value[0]?.id) {
    venueId.value = venues.value[0].id
    venueName.value = venues.value[0].name
  }
}

async function loadVenueBoundCity() {
  if (!venueId.value) return
  try {
    const d = await apiRequest<any>(`/provider/venues/${venueId.value}`)
    venueCityCode.value = String(d?.cityCode || '').trim()
  } catch {
    venueCityCode.value = ''
  }
}

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

async function loadOnboarding() {
  onboardingLoading.value = true
  try {
    onboarding.value = await apiRequest<Onboarding>('/provider/onboarding')
  } catch {
    onboarding.value = null
  } finally {
    onboardingLoading.value = false
  }
}

async function loadServices() {
  if (!venueId.value) return
  loading.value = true
  try {
    const data = await apiRequest<{ items: VenueService[]; total: number }>(`/provider/venues/${venueId.value}/services`)
    services.value = data.items
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

function openCreate() {
  if (onboarding.value?.healthCardStatus !== 'APPROVED') {
    ElMessage.warning('健行天下未开通：请先在“工作台 → 健行天下开通”提交审核并通过后再新增服务')
    return
  }
  if (!venueCityCode.value) {
    ElMessage.warning('场所尚未绑定城市（cityCode），请先到“场所信息”完善后再新增服务')
    return
  }
  editingId.value = null
  Object.assign(form, {
    serviceType: categories.value[0]?.code || '',
    title: '',
    fulfillmentType: 'SERVICE',
    productId: '',
    bookingRequired: false,
    // vNow：默认双支持，不让 Provider 选择
    redemptionMethod: 'BOTH',
    // 业务口径：锁定为场所所在城市
    applicableRegions: [venueCityCode.value],
    status: 'ENABLED',
  })
  dialogOpen.value = true
}

function openEdit(row: VenueService) {
  if (onboarding.value?.healthCardStatus !== 'APPROVED') {
    ElMessage.warning('健行天下未开通：当前仅允许查看，禁止编辑服务')
    return
  }
  if (!venueCityCode.value) {
    ElMessage.warning('场所尚未绑定城市（cityCode），请先到“场所信息”完善后再编辑服务')
    return
  }
  editingId.value = row.id
  Object.assign(form, {
    serviceType: row.serviceType,
    title: row.title,
    fulfillmentType: row.fulfillmentType,
    productId: row.productId ?? '',
    bookingRequired: row.bookingRequired,
    // vNow：统一升级为默认双支持（兼容历史单选数据）
    redemptionMethod: 'BOTH',
    // 业务口径：保存时会强制锁定为场所所在城市
    applicableRegions: [venueCityCode.value],
    status: row.status,
  })
  dialogOpen.value = true
}

async function save() {
  if (!venueId.value) return
  try {
    if (!venueCityCode.value) return ElMessage.error('场所尚未绑定城市（cityCode），请先到“场所信息”完善后再保存')
    if (!String(form.serviceType || '').trim()) return ElMessage.error('服务类目不能为空，请先让运营在“服务大类管理”维护后再选择')
    if (!String(form.title || '').trim()) return ElMessage.error('服务名称不能为空')

    const body = {
      serviceType: form.serviceType,
      title: form.title,
      fulfillmentType: form.fulfillmentType,
      productId: form.productId || null,
      bookingRequired: form.bookingRequired,
      // vNow：默认双支持
      redemptionMethod: 'BOTH',
      // 业务口径：仅允许场所所在城市
      applicableRegions: [venueCityCode.value],
      status: form.status,
    }

    if (!editingId.value) {
      await apiRequest(`/provider/venues/${venueId.value}/services`, { method: 'POST', body })
      ElMessage.success('已创建')
    } else {
      await apiRequest(`/provider/venues/${venueId.value}/services/${editingId.value}`, { method: 'PUT', body })
      ElMessage.success('已保存')
    }

    dialogOpen.value = false
    await loadServices()
  } catch (e: any) {
    ElMessage.error(e?.message ?? e?.apiError?.message ?? '保存失败')
  }
}

onMounted(async () => {
  await loadOnboarding()
  await loadServiceCategories()
  await loadVenues()
  await loadVenueBoundCity()
  await loadRegions()
  await loadServices()
})
</script>

<template>
  <div>
    <PageHeaderBar title="健行天下服务（特供服务项）" />

    <el-alert
      title="本页配置用于“健行天下权益核销/预约”的特供服务项。服务类目（serviceType）来自平台统一字典；需预约=是时，核销前必须存在已确认预约。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />
    <el-alert v-if="onboarding?.healthCardStatus !== 'APPROVED'" type="warning" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>健行天下未开通（门禁）</template>
      <div style="line-height: 1.7">
        <div>
          当前状态：{{
            onboarding?.healthCardStatus === 'SUBMITTED'
              ? '待审核'
              : onboarding?.healthCardStatus === 'REJECTED'
                ? '已驳回'
                : '未申请'
          }}
        </div>
        <div v-if="onboarding?.healthCardStatus === 'REJECTED' && onboarding?.notes" style="margin-top: 4px">
          驳回原因：{{ onboarding?.notes }}
        </div>
        <div style="color: var(--lh-muted); margin-top: 6px">请先到“工作台”提交健行天下开通申请并通过审核后，再新增/编辑服务。</div>
        <div style="margin-top: 8px">
          <el-button size="small" type="primary" @click="$router.push('/provider/workbench')">去工作台开通</el-button>
          <el-button size="small" @click="$router.push('/provider/venues')">去完善场所信息</el-button>
        </div>
      </div>
    </el-alert>
    <el-alert v-if="categories.length === 0" type="warning" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>缺少“服务大类”字典</template>
      <div style="line-height: 1.7">
        <div>当前系统未配置任何可用服务大类（serviceType）。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">请让运营先在 Admin 侧“健行天下 → 服务大类管理”新增并启用，然后回到本页刷新。</div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="场所">
          <el-tag type="info">{{ venueName || '—' }}</el-tag>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="categories.length === 0 || onboarding?.healthCardStatus !== 'APPROVED'" @click="openCreate">新增服务</el-button>
          <el-button :loading="loading" @click="loadServices">刷新</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        style="margin-top: 12px"
        @retry="loadServices"
      />
      <PageEmptyState
        v-else-if="!loading && services.length === 0"
        title="暂无服务"
        description="建议先创建服务：填写 serviceType（唯一）与名称；如果需要预约，请开启“需预约”。"
        style="margin-top: 12px"
      />
      <el-table v-else :data="services" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="serviceType" label="服务类目编码" width="220" />
        <el-table-column prop="title" label="服务名称" min-width="180" />
        <el-table-column label="需预约" width="110">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.bookingRequired ? 'warning' : 'info'">{{ scope.row.bookingRequired ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="核销方式" width="140">
          <template #default="scope">
            <el-tag size="small" type="info">
              {{
                scope.row.redemptionMethod === 'BOTH'
                  ? '扫码/券码'
                  : scope.row.redemptionMethod === 'QR_CODE'
                    ? '扫码'
                    : '券码'
              }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.status === 'ENABLED' ? 'success' : 'info'">{{ scope.row.status === 'ENABLED' ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="scope">
            <el-button type="primary" size="small" @click="openEdit(scope.row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogOpen" :title="editingId ? '编辑服务' : '新增服务'" width="760px">
      <el-form label-width="120px">
        <el-form-item label="服务类目">
          <el-select v-model="form.serviceType" filterable placeholder="请选择服务大类" style="width: 420px" :loading="categoriesLoading">
            <el-option v-for="c in categories" :key="c.code" :label="`${c.displayName}（${c.code}）`" :value="c.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务名称">
          <el-input v-model="form.title" placeholder="例如：肩颈按摩" />
        </el-form-item>
        <el-form-item label="需要预约">
          <el-switch v-model="form.bookingRequired" />
        </el-form-item>
        <el-form-item label="核销方式">
          <el-tag type="info">默认支持扫码 + 券码</el-tag>
        </el-form-item>
        <el-form-item label="适用区域">
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
            提示：业务口径为“provider 在哪，场所就得在哪”，服务适用地区仅允许为当前场所所在城市。
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 200px">
            <el-option label="启用（ENABLED）" value="ENABLED" />
            <el-option label="停用（DISABLED）" value="DISABLED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

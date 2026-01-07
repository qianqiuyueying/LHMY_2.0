<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { fmtBeijingDateTime, formatBeijingDateTime } from '../../lib/time'
import { handleApiError } from '../../lib/error-handling'

type PublishStatus = 'DRAFT' | 'PUBLISHED' | 'OFFLINE'
type ReviewStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
type VenueRow = {
  id: string
  name: string
  providerId: string
  providerName: string
  publishStatus: PublishStatus
  reviewStatus?: ReviewStatus | null
  offlineReason?: string | null
  offlinedAt?: string | null
  updatedAt: string
  createdAt: string
}

type VenueDetail = {
  id: string
  providerId: string
  providerName: string
  name: string
  address?: string | null
  contactPhone?: string | null
  businessHours?: string | null
  countryCode?: string | null
  provinceCode?: string | null
  cityCode?: string | null
  description?: string | null
  logoUrl?: string | null
  coverImageUrl?: string | null
  imageUrls?: string[] | null
  tags?: string[] | null
  publishStatus: PublishStatus
  reviewStatus?: ReviewStatus | null
  rejectReason?: string | null
  rejectedAt?: string | null
  offlineReason?: string | null
  offlinedAt?: string | null
  updatedAt: string
  createdAt: string
}

type CityItem = { code: string; name: string; sort: number }
const cities = ref<CityItem[]>([])
const cityNameByCode = computed<Record<string, string>>(() => {
  const out: Record<string, string> = {}
  for (const x of cities.value || []) {
    if (!x?.code) continue
    out[String(x.code)] = String(x.name || '')
  }
  return out
})
const detailCityName = computed(() => {
  const code = String(detail.value?.cityCode || '').trim()
  if (!code) return ''
  return cityNameByCode.value[code] || ''
})

const STATUS_LABEL: Record<PublishStatus, string> = {
  DRAFT: '草稿/待审核',
  PUBLISHED: '已发布',
  OFFLINE: '已下线',
}

const REVIEW_LABEL: Record<ReviewStatus, string> = {
  DRAFT: '草稿',
  SUBMITTED: '待审核',
  APPROVED: '已通过',
  REJECTED: '已驳回',
}

function reviewLabel(v: unknown): string {
  const raw = String(v || '').trim() as ReviewStatus | ''
  const key: ReviewStatus = (raw && raw in REVIEW_LABEL ? (raw as ReviewStatus) : 'DRAFT')
  return REVIEW_LABEL[key] ?? (raw || '-')
}

const loading = ref(false)
const rows = ref<VenueRow[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const filters = reactive({
  keyword: '',
  providerId: '',
  publishStatus: '' as '' | PublishStatus,
})

const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<VenueDetail | null>(null)
const router = useRouter()

async function openDetail(row: VenueRow) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await apiRequest<VenueDetail>(`/admin/venues/${row.id}`)
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '加载详情失败' })
  } finally {
    detailLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<VenueRow>>('/admin/venues', {
      query: {
        keyword: filters.keyword || null,
        providerId: filters.providerId || null,
        publishStatus: filters.publishStatus || null,
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

async function approve(row: VenueRow) {
  try {
    await ElMessageBox.confirm('确认通过该场所的审核？（注意：此操作不会发布上线；发布请前往“内容与投放 → 官网投放”。）', '通过审核', {
      type: 'warning',
      confirmButtonText: '通过',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/venues/${row.id}/approve`, { method: 'POST' })
    ElMessage.success('已通过（未发布）')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败', preferRefreshHintOn409: true })
  }
}

async function reject(row: VenueRow) {
  let reason = ''
  try {
    const r = await ElMessageBox.prompt('请输入驳回原因（将展示给 Provider，可覆盖更新）', '驳回', {
      type: 'warning',
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：资料不完整/图片不清晰/信息不一致…',
      inputValidator: (v: string) => {
        if (!String(v || '').trim()) return '驳回原因不能为空'
        if (String(v || '').trim().length > 200) return '驳回原因最多 200 字'
        return true
      },
    })
    reason = String(r?.value || '').trim()
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/venues/${row.id}/reject`, { method: 'POST', body: { reason } })
    ElMessage.success('已驳回')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败', preferRefreshHintOn409: true })
  }
}

async function offline(row: VenueRow) {
  let reason = ''
  try {
    const r = await ElMessageBox.prompt('请输入下线原因（将展示给 Provider，可覆盖更新）', '下线', {
      type: 'warning',
      confirmButtonText: '下线',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：信息过期/资料不合规/暂不合作…',
      inputValidator: (v: string) => {
        if (!String(v || '').trim()) return '下线原因不能为空'
        if (String(v || '').trim().length > 200) return '下线原因最多 200 字'
        return true
      },
    })
    reason = String(r?.value || '').trim()
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/venues/${row.id}/offline`, { method: 'POST', body: { reason } })
    ElMessage.success('已下线')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败', preferRefreshHintOn409: true })
  }
}

onMounted(load)

async function loadCities() {
  try {
    const data = await apiRequest<{ items: CityItem[] }>('/regions/cities')
    cities.value = (data.items || []).filter((x) => String(x?.code || '').startsWith('CITY:'))
  } catch {
    cities.value = []
  }
}

onMounted(loadCities)
</script>

<template>
  <div>
    <PageHeaderBar title="场所管理/审核" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>本页有什么用？（供给侧-场所）</template>
      <div style="line-height: 1.7">
        <div>用于审核与管理 Provider 的“场所对外展示资料”。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">
          审核通过=资料审核通过（不等于发布上线）；发布上线请前往「内容与投放 → 官网投放」。
        </div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="场所名称/地址（模糊）" style="width: 260px" />
        </el-form-item>
        <el-form-item label="ProviderID">
          <el-input v-model="filters.providerId" placeholder="可选（精确）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.publishStatus" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="草稿/待审核（DRAFT）" value="DRAFT" />
            <el-option label="已发布（PUBLISHED）" value="PUBLISHED" />
            <el-option label="已下线（OFFLINE）" value="OFFLINE" />
          </el-select>
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
              filters.keyword = '';
              filters.providerId = '';
              filters.publishStatus = '';
              page = 1;
              load()
            "
          >
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无场所" description="可清空筛选条件重试；或让 Provider 先完善场所信息。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="场所ID" width="240" />
        <el-table-column prop="name" label="场所名称" min-width="200" />
        <el-table-column prop="providerName" label="Provider" min-width="180" />
        <el-table-column label="状态" width="260">
          <template #default="scope">
            <div style="display: flex; gap: 6px; flex-wrap: wrap">
              <el-tooltip :content="scope.row.publishStatus" placement="top">
                <el-tag size="small">
                  {{ STATUS_LABEL[scope.row.publishStatus as keyof typeof STATUS_LABEL] ?? scope.row.publishStatus }}
                </el-tag>
              </el-tooltip>
              <el-tooltip :content="String(scope.row.reviewStatus || '')" placement="top">
                <el-tag size="small" type="info">
                  {{ reviewLabel(scope.row.reviewStatus) }}
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column label="操作" width="280">
          <template #default="scope">
            <el-button size="small" @click="openDetail(scope.row)">详情</el-button>
            <el-button v-if="scope.row.reviewStatus === 'SUBMITTED'" size="small" type="success" @click="approve(scope.row)">通过</el-button>
            <el-button v-if="scope.row.publishStatus === 'PUBLISHED'" size="small" type="warning" @click="offline(scope.row)">下线</el-button>
            <el-button v-if="scope.row.reviewStatus === 'SUBMITTED'" size="small" type="danger" plain @click="reject(scope.row)">驳回</el-button>
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

    <el-drawer v-model="detailOpen" title="场所申请内容详情" size="680px">
      <el-skeleton v-if="detailLoading" :rows="10" animated />
      <el-empty v-else-if="!detail" description="暂无数据" />
      <div v-else>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="场所ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="Provider">{{ detail.providerName }}（{{ detail.providerId }}）</el-descriptions-item>
          <el-descriptions-item label="场所名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="发布状态">{{ STATUS_LABEL[detail.publishStatus] ?? detail.publishStatus }}</el-descriptions-item>
          <el-descriptions-item label="审核状态">{{ reviewLabel(detail.reviewStatus) }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.publishStatus === 'OFFLINE'" label="下线原因">
            {{ detail.offlineReason || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.reviewStatus === 'REJECTED'" label="驳回原因">
            {{ detail.rejectReason || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="所在城市">{{ detailCityName || detail.cityCode || '—' }}</el-descriptions-item>
          <el-descriptions-item label="地址">{{ detail.address || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ detail.contactPhone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="营业时间">{{ detail.businessHours || '—' }}</el-descriptions-item>
          <el-descriptions-item label="简介">{{ detail.description || '—' }}</el-descriptions-item>
          <el-descriptions-item label="标签">{{ (detail.tags || []).join('、') || '—' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatBeijingDateTime(detail.updatedAt) }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-top: 12px">
          <div style="font-weight: 800; margin-bottom: 8px">图片资料</div>

          <div style="margin-top: 8px">
            <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55); margin-bottom: 6px">Logo</div>
            <div v-if="detail.logoUrl" style="display: flex; gap: 10px; flex-wrap: wrap">
              <el-image :src="detail.logoUrl" style="width: 120px; height: 120px; border-radius: 10px" fit="cover" />
            </div>
            <div v-else style="font-size: 12px; color: rgba(0, 0, 0, 0.45)">未提交</div>
          </div>

          <div style="margin-top: 12px">
            <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55); margin-bottom: 6px">封面</div>
            <div v-if="detail.coverImageUrl" style="display: flex; gap: 10px; flex-wrap: wrap">
              <el-image :src="detail.coverImageUrl" style="width: 220px; height: 120px; border-radius: 10px" fit="cover" />
            </div>
            <div v-else style="font-size: 12px; color: rgba(0, 0, 0, 0.45)">未提交</div>
          </div>

          <div style="margin-top: 12px">
            <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55); margin-bottom: 6px">环境/服务图</div>
            <div v-if="(detail.imageUrls || []).length > 0" style="display: flex; gap: 10px; flex-wrap: wrap">
              <el-image v-for="u in detail.imageUrls || []" :key="u" :src="u" style="width: 160px; height: 100px; border-radius: 10px" fit="cover" />
            </div>
            <div v-else style="font-size: 12px; color: rgba(0, 0, 0, 0.45)">未提交</div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>


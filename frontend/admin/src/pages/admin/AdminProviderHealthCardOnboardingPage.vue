<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type HealthCardStatus = 'NOT_APPLIED' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
type InfraStatus = 'NOT_OPENED' | 'OPENED'

type Row = {
  providerId: string
  providerName: string
  infraCommerceStatus: InfraStatus
  healthCardStatus: HealthCardStatus
  agreementAcceptedAt?: string | null
  submittedAt?: string | null
  reviewedAt?: string | null
  notes?: string | null
  updatedAt?: string | null
}

type VenueDetail = {
  id: string
  providerId: string
  providerName: string
  name: string
  address?: string | null
  contactPhone?: string | null
  businessHours?: string | null
  cityCode?: string | null
  description?: string | null
  coverImageUrl?: string | null
  imageUrls?: string[] | null
  tags?: string[] | null
  publishStatus: string
  updatedAt: string
}

const STATUS_LABEL: Record<HealthCardStatus, string> = {
  NOT_APPLIED: '未申请',
  SUBMITTED: '待审核',
  APPROVED: '已开通',
  REJECTED: '已驳回',
}

const loading = ref(false)
const rows = ref<Row[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const filters = reactive({
  status: 'SUBMITTED' as '' | HealthCardStatus,
  keyword: '',
})

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<Row>>('/admin/provider-onboarding/health-card', {
      query: {
        status: filters.status || null,
        keyword: filters.keyword || null,
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
    ElMessage.error(
      `${msg}${errorCode.value ? `（code=${errorCode.value}）` : ''}${errorRequestId.value ? `（requestId=${errorRequestId.value}）` : ''}`,
    )
  } finally {
    loading.value = false
  }
}

const decideDialogOpen = ref(false)
const decidingProviderId = ref<string>('')
const decidingProviderName = ref<string>('')
const decideMode = ref<'APPROVE' | 'REJECT'>('APPROVE')
const decideNotes = ref('')
const decideTitle = computed(() => (decideMode.value === 'APPROVE' ? '通过开通申请' : '驳回开通申请'))

const venueDetailOpen = ref(false)
const venueDetailLoading = ref(false)
const venueDetail = ref<VenueDetail | null>(null)

async function openVenueDetail(row: Row) {
  venueDetailOpen.value = true
  venueDetailLoading.value = true
  venueDetail.value = null
  try {
    const list = await apiRequest<{ items: any[]; total: number }>('/admin/venues', {
      query: { providerId: row.providerId, page: 1, pageSize: 1 },
    })
    const id = String(list.items?.[0]?.id || '')
    if (!id) throw new Error('该 Provider 暂无场所资料')
    venueDetail.value = await apiRequest<VenueDetail>(`/admin/venues/${id}`)
  } catch (e: any) {
    ElMessage.error(e?.message ?? e?.apiError?.message ?? '加载场所资料失败')
  } finally {
    venueDetailLoading.value = false
  }
}

function openApprove(row: Row) {
  decidingProviderId.value = row.providerId
  decidingProviderName.value = row.providerName
  decideMode.value = 'APPROVE'
  decideNotes.value = ''
  decideDialogOpen.value = true
}

function openReject(row: Row) {
  decidingProviderId.value = row.providerId
  decidingProviderName.value = row.providerName
  decideMode.value = 'REJECT'
  decideNotes.value = row.notes ?? ''
  decideDialogOpen.value = true
}

async function submitDecision() {
  if (!decidingProviderId.value) return
  if (decideMode.value === 'REJECT' && !String(decideNotes.value || '').trim()) {
    return ElMessage.error('驳回原因必填')
  }
  try {
    await apiRequest(`/admin/provider-onboarding/${decidingProviderId.value}/health-card/decide`, {
      method: 'PUT',
      body: { decision: decideMode.value, notes: decideNotes.value || null },
    })
    ElMessage.success('已处理')
    decideDialogOpen.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function quickReject(row: Row) {
  try {
    await ElMessageBox.confirm('确认驳回？驳回后该 Provider 无法配置健行天下服务，可再次提交审核。', '驳回', {
      type: 'warning',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  openReject(row)
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="Provider 健行天下开通审核" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>说明（v1）</template>
      <div style="line-height: 1.7">
        <div>Provider 提交开通申请后，平台在此处“通过/驳回”。通过后 Provider 才能配置健行天下特供服务。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">建议默认查看“待审核（SUBMITTED）”。驳回需填写原因。</div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="待审核（SUBMITTED）" value="SUBMITTED" />
            <el-option label="已开通（APPROVED）" value="APPROVED" />
            <el-option label="已驳回（REJECTED）" value="REJECTED" />
            <el-option label="未申请（NOT_APPLIED）" value="NOT_APPLIED" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="Provider 名称/ID" style="width: 260px" />
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
              filters.status = 'SUBMITTED';
              filters.keyword = '';
              page = 1;
              load()
            "
          >
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无记录" description="可切换筛选状态或清空关键词后重试。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="providerId" label="ProviderID" width="240" />
        <el-table-column prop="providerName" label="Provider 名称" min-width="200" />
        <el-table-column label="基建联防" width="120">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.infraCommerceStatus === 'OPENED' ? 'success' : 'info'">
              {{ scope.row.infraCommerceStatus === 'OPENED' ? '已开通' : '未开通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="健行天下" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.healthCardStatus" placement="top">
              <el-tag
                size="small"
                :type="scope.row.healthCardStatus === 'APPROVED' ? 'success' : scope.row.healthCardStatus === 'SUBMITTED' ? 'warning' : scope.row.healthCardStatus === 'REJECTED' ? 'danger' : 'info'"
              >
                {{ STATUS_LABEL[scope.row.healthCardStatus as keyof typeof STATUS_LABEL] ?? scope.row.healthCardStatus }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="submittedAt" label="提交时间" width="200" />
        <el-table-column prop="reviewedAt" label="审核时间" width="200" />
        <el-table-column prop="notes" label="备注/原因" min-width="200" />
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <template v-if="scope.row.healthCardStatus === 'SUBMITTED'">
              <el-button size="small" type="success" @click="openApprove(scope.row)">通过</el-button>
              <el-button size="small" type="danger" @click="quickReject(scope.row)">驳回</el-button>
            </template>
            <el-button size="small" @click="openVenueDetail(scope.row)">查看场所资料</el-button>
            <el-tag v-if="scope.row.healthCardStatus !== 'SUBMITTED'" size="small" type="info">只读</el-tag>
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

    <el-dialog v-model="decideDialogOpen" :title="decideTitle" width="640px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>审核对象</template>
        <div>Provider：{{ decidingProviderName }}（{{ decidingProviderId }}）</div>
      </el-alert>
      <el-form label-width="120px">
        <el-form-item label="决策">
          <el-radio-group v-model="decideMode">
            <el-radio label="APPROVE">通过</el-radio>
            <el-radio label="REJECT">驳回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注/原因">
          <el-input v-model="decideNotes" type="textarea" :rows="4" placeholder="驳回时必填原因；通过可选填写备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="decideDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="submitDecision">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="venueDetailOpen" title="场所申请内容详情" size="680px">
      <el-skeleton v-if="venueDetailLoading" :rows="10" animated />
      <el-empty v-else-if="!venueDetail" description="暂无数据" />
      <div v-else>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="场所ID">{{ venueDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="Provider">{{ venueDetail.providerName }}（{{ venueDetail.providerId }}）</el-descriptions-item>
          <el-descriptions-item label="场所名称">{{ venueDetail.name }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ venueDetail.publishStatus }}</el-descriptions-item>
          <el-descriptions-item label="所在城市">{{ venueDetail.cityCode || '—' }}</el-descriptions-item>
          <el-descriptions-item label="地址">{{ venueDetail.address || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ venueDetail.contactPhone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="营业时间">{{ venueDetail.businessHours || '—' }}</el-descriptions-item>
          <el-descriptions-item label="简介">{{ venueDetail.description || '—' }}</el-descriptions-item>
          <el-descriptions-item label="标签">{{ (venueDetail.tags || []).join('、') || '—' }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ venueDetail.updatedAt }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-top: 12px">
          <div style="font-weight: 800; margin-bottom: 8px">图片资料</div>

          <div style="margin-top: 8px">
            <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55); margin-bottom: 6px">封面</div>
            <div v-if="venueDetail.coverImageUrl" style="display: flex; gap: 10px; flex-wrap: wrap">
              <el-image :src="venueDetail.coverImageUrl" style="width: 220px; height: 120px; border-radius: 10px" fit="cover" />
            </div>
            <div v-else style="font-size: 12px; color: rgba(0, 0, 0, 0.45)">未提交</div>
          </div>

          <div style="margin-top: 12px">
            <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55); margin-bottom: 6px">环境/服务图</div>
            <div v-if="(venueDetail.imageUrls || []).length > 0" style="display: flex; gap: 10px; flex-wrap: wrap">
              <el-image v-for="u in venueDetail.imageUrls || []" :key="u" :src="u" style="width: 160px; height: 100px; border-radius: 10px" fit="cover" />
            </div>
            <div v-else style="font-size: 12px; color: rgba(0, 0, 0, 0.45)">未提交</div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>


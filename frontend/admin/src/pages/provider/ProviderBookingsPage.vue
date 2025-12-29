<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type BookingItem = {
  id: string
  sourceType?: 'ENTITLEMENT' | 'ORDER_ITEM'
  entitlementId?: string | null
  orderId?: string | null
  orderItemId?: string | null
  productId?: string | null
  userId: string
  venueId: string
  serviceType: string
  bookingDate: string
  timeSlot: string
  status: 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'COMPLETED'
  confirmationMethod: 'AUTO' | 'MANUAL'
  confirmedAt?: string | null
  createdAt: string
}

type VenueLite = { id: string; name: string; publishStatus: string }
type VenueServiceLite = { id: string; serviceType: string; title: string; productId?: string | null; bookingRequired: boolean; status: string }

const filters = reactive({
  status: '',
  serviceType: '',
  keyword: '',
  dateFrom: '',
  dateTo: '',
})

const venueId = ref('')
const venueName = ref('')
const servicesLoading = ref(false)
const services = ref<VenueServiceLite[]>([])

const serviceGroups = computed(() => {
  const items = (services.value || []).filter((x) => x.status === 'ENABLED')
  const health = items.filter((x) => !x.productId).map((x) => ({ label: `${x.title}（${x.serviceType}）`, value: x.serviceType }))
  const infra = items.filter((x) => !!x.productId).map((x) => ({ label: `${x.title}（${x.serviceType}）`, value: x.serviceType }))
  return [
    { label: '健行天下服务（权益）', options: health },
    { label: '基建联防服务型商品（订单）', options: infra },
  ].filter((g) => g.options.length > 0)
})

const loading = ref(false)
const rows = ref<BookingItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const STATUS_LABEL: Record<BookingItem['status'], string> = {
  PENDING: '待确认',
  CONFIRMED: '已确认',
  CANCELLED: '已取消',
  COMPLETED: '已完成',
}

const CONFIRM_METHOD_LABEL: Record<BookingItem['confirmationMethod'], string> = {
  AUTO: '自动',
  MANUAL: '人工',
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<BookingItem>>('/provider/bookings', {
      query: {
        status: filters.status || null,
        serviceType: filters.serviceType || null,
        keyword: filters.keyword || null,
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items
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

async function loadVenueAndServices() {
  try {
    const v = await apiRequest<{ items: VenueLite[]; total: number }>('/provider/venues')
    if (v.items?.[0]?.id) {
      venueId.value = v.items[0].id
      venueName.value = v.items[0].name
      servicesLoading.value = true
      try {
        const s = await apiRequest<{ items: VenueServiceLite[]; total: number }>(`/provider/venues/${venueId.value}/services`)
        services.value = s.items || []
      } catch {
        services.value = []
      } finally {
        servicesLoading.value = false
      }
    }
  } catch {
    // ignore
  }
}

async function confirm(id: string) {
  try {
    await ElMessageBox.confirm('确认该预约？确认后用户将收到确认结果（若业务流程有通知）。', '确认预约', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/bookings/${id}/confirm`, { method: 'PUT', idempotencyKey: newIdempotencyKey() })
    ElMessage.success('已确认')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function cancel(id: string) {
  try {
    await ElMessageBox.confirm('确认取消该预约？取消后将释放对应排期容量（如适用）。', '取消预约', {
      type: 'warning',
      confirmButtonText: '取消预约',
      cancelButtonText: '返回',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/provider/bookings/${id}/cancel`, { method: 'POST' })
    ElMessage.success('已取消')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

onMounted(async () => {
  await loadVenueAndServices()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="预约管理" />

    <el-alert
      title="本页用于场所侧日常履约：对 PENDING 预约进行确认/取消；完成后核销将按规则扣次数。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="待确认（PENDING）" value="PENDING" />
            <el-option label="已确认（CONFIRMED）" value="CONFIRMED" />
            <el-option label="已取消（CANCELLED）" value="CANCELLED" />
            <el-option label="已完成（COMPLETED）" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务">
          <el-select v-model="filters.serviceType" filterable clearable placeholder="全部服务" style="width: 320px" :loading="servicesLoading">
            <el-option label="全部" value="" />
            <el-option-group v-for="g in serviceGroups" :key="g.label" :label="g.label">
              <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="预约ID / 用户ID" style="width: 240px" />
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.status='';filters.serviceType='';filters.keyword='';filters.dateFrom='';filters.dateTo='';page=1;load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        style="margin-top: 12px"
        @retry="load"
      />
      <PageEmptyState
        v-else-if="!loading && rows.length === 0"
        title="暂无预约"
        description="可尝试：选择状态=待确认；缩小日期范围；或确认是否已有预约数据。"
        style="margin-top: 12px"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="预约ID" width="240" />
        <el-table-column label="来源" width="160">
          <template #default="scope">
            <el-tag size="small" type="info">{{ scope.row.sourceType === 'ORDER_ITEM' ? '订单（基建联防）' : '权益（健行天下）' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="venueId" label="场所ID" width="220" />
        <el-table-column prop="serviceType" label="服务类目（serviceType）" width="220" />
        <el-table-column label="时间" width="210">
          <template #default="scope">{{ scope.row.bookingDate }} {{ scope.row.timeSlot }}</template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ STATUS_LABEL[scope.row.status as keyof typeof STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="确认方式" width="150">
          <template #default="scope">
            <el-tooltip :content="scope.row.confirmationMethod" placement="top">
              <el-tag size="small" type="info">
                {{ CONFIRM_METHOD_LABEL[scope.row.confirmationMethod as keyof typeof CONFIRM_METHOD_LABEL] ?? scope.row.confirmationMethod }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="scope">
            <el-button v-if="scope.row.status === 'PENDING'" type="success" size="small" @click="confirm(scope.row.id)">确认</el-button>
            <el-button
              v-if="scope.row.status === 'PENDING' || scope.row.status === 'CONFIRMED'"
              type="warning"
              size="small"
              @click="cancel(scope.row.id)"
              >取消</el-button
            >
            <el-tag v-if="scope.row.status === 'CANCELLED' || scope.row.status === 'COMPLETED'" size="small" type="info">只读</el-tag>
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
  </div>
</template>

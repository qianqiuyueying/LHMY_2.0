<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiException, apiDownload, apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import { useRouter } from 'vue-router'

type OrderItem = {
  id: string
  orderNo: string
  userId: string
  buyerPhoneMasked?: string | null
  orderType: 'SERVICE_PACKAGE'
  paymentStatus: 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED'
  totalAmount: number
  dealerId?: string | null
  dealerLinkId?: string | null
  sellableCardId?: string | null
  sellableCardName?: string | null
  regionLevel?: string | null
  createdAt: string
  paidAt?: string | null
}

const PAYMENT_STATUS_LABEL: Record<OrderItem['paymentStatus'], string> = {
  PENDING: '待支付',
  PAID: '已支付',
  FAILED: '失败',
  REFUNDED: '已退款',
}

const filters = reactive({
  orderNo: '',
  phone: '',
  dealerLinkId: '',
  paymentStatus: '' as '' | OrderItem['paymentStatus'],
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<OrderItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<OrderItem>>('/dealer/orders', {
      query: {
        orderNo: filters.orderNo || null,
        phone: filters.phone || null,
        dealerLinkId: filters.dealerLinkId || null,
        paymentStatus: filters.paymentStatus || null,
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

onMounted(load)

function handleApiError(e: unknown, fallbackMessage: string): void {
  if (e instanceof ApiException) {
    const code = e.apiError.code
    if (e.status === 401) return
    if (e.status === 403 || code === 'FORBIDDEN') {
      try {
        router.push('/403')
      } catch {
        // ignore
      }
      return
    }
    if (e.status === 409 && (code === 'STATE_CONFLICT' || code === 'INVALID_STATE_TRANSITION')) {
      ElMessage.warning('状态已变化，请刷新后重试')
      return
    }
    if (e.status === 400 || e.status === 404) {
      ElMessage.error(
        `${e.apiError.message}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
      )
      return
    }
    ElMessage.error(
      `${e.apiError.message || fallbackMessage}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
    )
    return
  }
  ElMessage.error(fallbackMessage)
}

async function exportCsv() {
  // 你已拍板：dateFrom/dateTo 不填就禁止导出（前端禁用 + 后端硬拒绝）
  if (!filters.dateFrom || !filters.dateTo) return
  try {
    const { blob, filename } = await apiDownload('/dealer/orders/export', {
      query: {
        orderNo: filters.orderNo || null,
        phone: filters.phone || null,
        dealerLinkId: filters.dealerLinkId || null,
        paymentStatus: filters.paymentStatus || null,
        dateFrom: filters.dateFrom,
        dateTo: filters.dateTo,
      },
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `dealer-orders-${filters.dateFrom}-${filters.dateTo}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    handleApiError(e, '导出失败')
  }
}
</script>

<template>
  <div>
    <PageHeaderBar title="订单归属" />

    <el-alert
      title="本页展示归属到当前经销商的订单（无需手填 dealerId）。可按支付状态与日期筛选。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="订单号">
          <el-input v-model="filters.orderNo" style="width: 220px" />
        </el-form-item>
        <el-form-item label="投放链接ID">
          <el-input v-model="filters.dealerLinkId" placeholder="dealerLinkId（可选）" style="width: 260px" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="filters.phone" style="width: 200px" />
        </el-form-item>
        <el-form-item label="支付状态">
          <el-select v-model="filters.paymentStatus" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="待支付（PENDING）" value="PENDING" />
            <el-option label="已支付（PAID）" value="PAID" />
            <el-option label="失败（FAILED）" value="FAILED" />
            <el-option label="已退款（REFUNDED）" value="REFUNDED" />
          </el-select>
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.orderNo='';filters.phone='';filters.dealerLinkId='';filters.paymentStatus='';filters.dateFrom='';filters.dateTo='';page=1;load()">重置</el-button>
          <el-button :disabled="!filters.dateFrom || !filters.dateTo" @click="exportCsv">导出CSV</el-button>
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
        title="暂无订单"
        description="可尝试：缩小日期范围、清空筛选条件；或确认是否已有成交订单。"
        style="margin-top: 12px"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="orderNo" label="订单号" width="240" />
        <el-table-column prop="dealerLinkId" label="投放链接ID" width="260" />
        <el-table-column label="卡片" min-width="220">
          <template #default="scope">
            <div style="font-weight: 600">{{ scope.row.sellableCardName || '—' }}</div>
            <div style="font-size: 12px; color: var(--lh-muted)">sellableCardId：{{ scope.row.sellableCardId || '—' }}；regionLevel：{{ scope.row.regionLevel || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="buyerPhoneMasked" label="手机号" width="160" />
        <el-table-column label="支付状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.paymentStatus" placement="top">
              <el-tag size="small">{{ PAYMENT_STATUS_LABEL[scope.row.paymentStatus as keyof typeof PAYMENT_STATUS_LABEL] ?? scope.row.paymentStatus }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="totalAmount" label="金额" width="120" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column prop="paidAt" label="支付时间" width="200" />
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

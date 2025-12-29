<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiException, apiRequest, newIdempotencyKey } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError as handleApiErrorGlobal } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { useRouter } from 'vue-router'

type BookingItem = {
  id: string
  entitlementId: string
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

const BOOKING_STATUS_LABEL: Record<BookingItem['status'], string> = {
  PENDING: '待确认',
  CONFIRMED: '已确认',
  CANCELLED: '已取消',
  COMPLETED: '已完成',
}

const CONFIRM_METHOD_LABEL: Record<BookingItem['confirmationMethod'], string> = {
  AUTO: '自动',
  MANUAL: '人工',
}

const filters = reactive({
  status: '',
  serviceType: '',
  keyword: '',
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<BookingItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

function handleApiError(e: unknown, fallbackMessage: string): void {
  // 统一口径（过渡期）：优先使用全局错误处理；保留本地旧逻辑作为兜底
  try {
    handleApiErrorGlobal(e, { router, fallbackMessage, preferRefreshHintOn409: true })
    return
  } catch {
    // ignore
  }

  if (e instanceof ApiException) {
    const code = e.apiError.code
    // 401：apiRequest 已统一跳转登录；这里不重复弹窗避免噪声
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

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<BookingItem>>('/admin/bookings', {
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
    handleApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function cancelBooking(row: BookingItem) {
  try {
    const { value } = await ElMessageBox.prompt('请输入取消原因（必填）', '取消预约', {
      confirmButtonText: '确认取消',
      cancelButtonText: '返回',
      inputPlaceholder: '例如：用户临时取消/场所原因/其他',
      inputValidator: (v: string) => {
        if (!String(v || '').trim()) return '必须填写取消原因'
        return true
      },
      type: 'warning',
    })

    await apiRequest(`/admin/bookings/${row.id}`, {
      method: 'DELETE',
      idempotencyKey: newIdempotencyKey(),
      body: { reason: String(value || '').trim() },
    })
    ElMessage.success('已取消预约')
    await load()
  } catch (e: any) {
    if (e === 'cancel' || e?.message === 'cancel') return
    handleApiError(e, '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="预约管理" />

    <el-card style="margin-top: 12px">
      <el-alert
        title="本页为平台监管视图（只读）。日常确认/取消由场所后台处理；本页仅保留“强制取消（原因必填）”用于例外处置。"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

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
          <el-input v-model="filters.serviceType" placeholder="服务编码（serviceType，可选）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="预约ID / 用户ID / 场所ID" style="width: 240px" />
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
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无预约" />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="预约ID" width="240" />
        <el-table-column prop="venueId" label="场所" width="200" />
        <el-table-column prop="serviceType" label="服务" width="160" />
        <el-table-column label="时间" width="200">
          <template #default="scope">{{ scope.row.bookingDate }} {{ scope.row.timeSlot }}</template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ BOOKING_STATUS_LABEL[scope.row.status as keyof typeof BOOKING_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="确认方式" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.confirmationMethod" placement="top">
              <el-tag size="small">{{ CONFIRM_METHOD_LABEL[scope.row.confirmationMethod as keyof typeof CONFIRM_METHOD_LABEL] ?? scope.row.confirmationMethod }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'PENDING' || scope.row.status === 'CONFIRMED'"
              type="danger"
              size="small"
              @click="cancelBooking(scope.row)"
            >
              强制取消
            </el-button>
            <el-tag v-else size="small" type="info">只读</el-tag>
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

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { fmtBeijingDateTime } from '../../lib/time'

type AfterSaleCase = {
  id: string
  orderId: string
  userId: string
  type: 'RETURN' | 'REFUND' | 'AFTER_SALE_SERVICE'
  status: 'SUBMITTED' | 'UNDER_REVIEW' | 'DECIDED' | 'CLOSED'
  amount: number
  reason?: string | null
  decision?: string | null
  decisionNotes?: string | null
  createdAt: string
  updatedAt: string
}

const CASE_TYPE_LABEL: Record<AfterSaleCase['type'], string> = {
  RETURN: '退货',
  REFUND: '退款',
  AFTER_SALE_SERVICE: '售后服务',
}

const CASE_STATUS_LABEL: Record<AfterSaleCase['status'], string> = {
  SUBMITTED: '已提交',
  UNDER_REVIEW: '审核中',
  DECIDED: '已裁决',
  CLOSED: '已关闭',
}

const filters = reactive({
  type: '' as '' | AfterSaleCase['type'],
  status: '' as '' | AfterSaleCase['status'],
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<AfterSaleCase[]>([])
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
    const data = await apiRequest<PageResp<AfterSaleCase>>('/admin/after-sales', {
      query: {
        type: filters.type || null,
        status: filters.status || null,
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
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

async function decide(id: string, decision: 'APPROVE' | 'REJECT') {
  try {
    const { value } = await ElMessageBox.prompt('裁决备注（可选）', `售后裁决：${decision}`, {
      inputType: 'textarea',
      inputPlaceholder: '可留空',
      confirmButtonText: '提交',
      cancelButtonText: '取消',
    })

    await apiRequest(`/admin/after-sales/${id}/decide`, {
      method: 'PUT',
      body: { decision, decisionNotes: value || null },
    })

    ElMessage.success('已裁决')
    await load()
  } catch (e: any) {
    if (e === 'cancel') return
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="售后仲裁" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="类型">
          <el-select v-model="filters.type" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="退货（RETURN）" value="RETURN" />
            <el-option label="退款（REFUND）" value="REFUND" />
            <el-option label="售后服务（AFTER_SALE_SERVICE）" value="AFTER_SALE_SERVICE" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="审核中（UNDER_REVIEW）" value="UNDER_REVIEW" />
            <el-option label="已关闭（CLOSED）" value="CLOSED" />
            <el-option label="已提交（SUBMITTED）" value="SUBMITTED" />
            <el-option label="已裁决（DECIDED）" value="DECIDED" />
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
          <el-button @click="filters.type='';filters.status='';filters.dateFrom='';filters.dateTo='';page=1;load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无售后单" />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="申请单号" width="240" />
        <el-table-column prop="orderId" label="订单号" width="240" />
        <el-table-column label="类型" width="160">
          <template #default="scope">
            <el-tooltip :content="scope.row.type" placement="top">
              <el-tag size="small">{{ CASE_TYPE_LABEL[scope.row.type as keyof typeof CASE_TYPE_LABEL] ?? scope.row.type }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ CASE_STATUS_LABEL[scope.row.status as keyof typeof CASE_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="createdAt" label="创建时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column label="操作" width="240">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'UNDER_REVIEW'"
              type="success"
              size="small"
              @click="decide(scope.row.id, 'APPROVE')"
              >同意</el-button
            >
            <el-button
              v-if="scope.row.status === 'UNDER_REVIEW'"
              type="danger"
              size="small"
              @click="decide(scope.row.id, 'REJECT')"
              >驳回</el-button
            >
            <el-tag v-if="scope.row.status !== 'UNDER_REVIEW'" size="small" type="info">只读</el-tag>
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

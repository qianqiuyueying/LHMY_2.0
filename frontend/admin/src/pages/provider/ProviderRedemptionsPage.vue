<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type Redemption = {
  id: string
  redemptionTime: string
  userId: string
  entitlementId: string
  bookingId?: string | null
  venueId: string
  serviceType: string
  redemptionMethod: 'QR_CODE' | 'VOUCHER_CODE'
  status: 'SUCCESS' | 'FAILED'
  failureReason?: string | null
  operatorId: string
  notes?: string | null
}

const filters = reactive({
  dateFrom: '',
  dateTo: '',
  serviceType: '',
  status: '',
  operatorId: '',
})

const loading = ref(false)
const rows = ref<Redemption[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const METHOD_LABEL: Record<Redemption['redemptionMethod'], string> = {
  QR_CODE: '扫码',
  VOUCHER_CODE: '券码',
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<Redemption>>('/provider/redemptions', {
      query: {
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        serviceType: filters.serviceType || null,
        status: filters.status || null,
        operatorId: filters.operatorId || null,
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
</script>

<template>
  <div>
    <PageHeaderBar title="核销记录" />

    <el-alert
      title="核销记录用于对账与排查：可按日期/服务/状态筛选；失败原因将直接展示。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="服务">
          <el-input v-model="filters.serviceType" placeholder="服务编码（serviceType，可选）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="成功（SUCCESS）" value="SUCCESS" />
            <el-option label="失败（FAILED）" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作员">
          <el-input v-model="filters.operatorId" placeholder="操作员ID（operatorId）" style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.dateFrom='';filters.dateTo='';filters.serviceType='';filters.status='';filters.operatorId='';page=1;load()">重置</el-button>
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
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无核销记录" description="可尝试：缩小日期范围或清空筛选条件。" style="margin-top: 12px" />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="redemptionTime" label="核销时间" width="200" />
        <el-table-column prop="userId" label="用户ID" width="220" />
        <el-table-column prop="entitlementId" label="权益ID" width="240" />
        <el-table-column prop="serviceType" label="服务编码" width="160" />
        <el-table-column label="方式" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.redemptionMethod" placement="top">
              <el-tag size="small" type="info">
                {{ METHOD_LABEL[scope.row.redemptionMethod as keyof typeof METHOD_LABEL] ?? scope.row.redemptionMethod }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="120">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.status === 'SUCCESS' ? 'success' : 'danger'">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="failureReason" label="失败原因" min-width="200" />
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

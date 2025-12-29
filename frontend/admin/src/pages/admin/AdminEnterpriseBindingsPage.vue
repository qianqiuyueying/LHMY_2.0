<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type BindingItem = {
  id: string
  userId: string
  userPhoneMasked?: string | null
  enterpriseId: string
  enterpriseName: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  bindingTime: string
}

const BINDING_STATUS_LABEL: Record<BindingItem['status'], string> = {
  PENDING: '待审核',
  APPROVED: '已通过',
  REJECTED: '已驳回',
}

const filters = reactive({
  status: '' as '' | 'PENDING' | 'APPROVED' | 'REJECTED',
  phone: '',
  enterpriseName: '',
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<BindingItem[]>([])
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
    const data = await apiRequest<PageResp<BindingItem>>('/admin/enterprise-bindings', {
      query: {
        status: filters.status || null,
        phone: filters.phone || null,
        enterpriseName: filters.enterpriseName || null,
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

async function approve(id: string) {
  try {
    await apiRequest<{ id: string; status: string }>(`/admin/enterprise-bindings/${id}/approve`, { method: 'PUT' })
    ElMessage.success('已通过')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function reject(id: string) {
  try {
    await apiRequest<{ id: string; status: string }>(`/admin/enterprise-bindings/${id}/reject`, { method: 'PUT' })
    ElMessage.success('已驳回')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="企业绑定审核" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="80px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="待处理（PENDING）" value="PENDING" />
            <el-option label="已通过（APPROVED）" value="APPROVED" />
            <el-option label="已驳回（REJECTED）" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="filters.phone" placeholder="模糊匹配" style="width: 200px" />
        </el-form-item>
        <el-form-item label="企业名">
          <el-input v-model="filters.enterpriseName" placeholder="模糊匹配" style="width: 220px" />
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.status = ''; filters.phone = ''; filters.enterpriseName = ''; filters.dateFrom = ''; filters.dateTo = ''; page = 1; load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState
        v-else-if="!loading && rows.length === 0"
        title="暂无绑定申请"
        description="可尝试：切换状态筛选或清空条件；若环境暂无业务数据，可先执行“演示数据初始化（seed）”。"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="绑定ID" width="260" />
        <el-table-column prop="userPhoneMasked" label="用户手机号" width="140" />
        <el-table-column prop="enterpriseName" label="企业" min-width="200" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ BINDING_STATUS_LABEL[scope.row.status as keyof typeof BINDING_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="bindingTime" label="绑定时间" width="200" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'PENDING'"
              type="success"
              size="small"
              @click="approve(scope.row.id)"
              >通过</el-button
            >
            <el-button v-if="scope.row.status === 'PENDING'" type="danger" size="small" @click="reject(scope.row.id)"
              >驳回</el-button
            >
            <el-tag v-if="scope.row.status !== 'PENDING'" size="small" type="info">已处理</el-tag>
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

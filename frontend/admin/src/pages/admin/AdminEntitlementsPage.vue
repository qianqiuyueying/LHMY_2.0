<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { fmtBeijingDateTime } from '../../lib/time'

type EntitlementItem = {
  id: string
  ownerId: string
  userId: string
  orderId: string
  entitlementType: 'SERVICE_PACKAGE'
  serviceType: string
  remainingCount: number
  totalCount: number
  validFrom: string
  validUntil: string
  status: 'ACTIVE' | 'USED' | 'EXPIRED' | 'TRANSFERRED' | 'REFUNDED'
}

const activeTab = ref<'ENTITLEMENTS' | 'REDEMPTIONS' | 'TRANSFERS'>('ENTITLEMENTS')

const filters = reactive({
  type: '' as '' | EntitlementItem['entitlementType'],
  status: '' as '' | EntitlementItem['status'],
})

type RedemptionItem = {
  id: string
  redemptionTime: string
  userId: string
  venueId: string
  serviceType: string
  operatorId: string
  status: 'SUCCESS' | 'FAILED'
  failureReason?: string | null
  entitlementId: string
  bookingId?: string | null
}

type TransferItem = {
  id: string
  transferredAt: string
  fromOwnerId: string
  toOwnerId: string
  entitlementId: string
  status?: string | null
}

const loading = ref(false)
const rows = ref<EntitlementItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const redemptions = ref<RedemptionItem[]>([])
const transfers = ref<TransferItem[]>([])

function reset() {
  filters.type = ''
  filters.status = ''
  page.value = 1
  load()
}

async function loadEntitlements() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<EntitlementItem>>('/entitlements', {
      query: {
        type: filters.type || null,
        status: filters.status || null,
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

async function loadRedemptions() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<RedemptionItem>>('/admin/redemptions', {
      query: { page: page.value, pageSize: pageSize.value },
    })
    redemptions.value = data.items || []
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

async function loadTransfers() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<TransferItem>>('/admin/entitlement-transfers', {
      query: { page: page.value, pageSize: pageSize.value },
    })
    transfers.value = data.items || []
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

async function load() {
  if (activeTab.value === 'ENTITLEMENTS') return await loadEntitlements()
  if (activeTab.value === 'REDEMPTIONS') return await loadRedemptions()
  return await loadTransfers()
}

function onTabChange() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="权益与核销" />

    <el-card style="margin-top: 12px">
      <el-alert
        title="本页为平台监管视图（只读）。日常核销请在「场所后台 → 核销」完成；本页用于查询权益/核销记录/转赠记录。"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

      <el-tabs v-model="activeTab" @tab-change="onTabChange" style="margin-bottom: 10px">
        <el-tab-pane label="权益列表" name="ENTITLEMENTS" />
        <el-tab-pane label="核销记录" name="REDEMPTIONS" />
        <el-tab-pane label="转赠记录" name="TRANSFERS" />
      </el-tabs>

      <el-form :inline="true" label-width="90px">
        <el-form-item v-if="activeTab === 'ENTITLEMENTS'" label="类型">
          <el-select v-model="filters.type" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="服务包（SERVICE_PACKAGE）" value="SERVICE_PACKAGE" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="activeTab === 'ENTITLEMENTS'" label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="可用（ACTIVE）" value="ACTIVE" />
            <el-option label="已使用（USED）" value="USED" />
            <el-option label="已过期（EXPIRED）" value="EXPIRED" />
            <el-option label="已转赠（TRANSFERRED）" value="TRANSFERRED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="reset">重置</el-button>
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
        v-else-if="!loading && activeTab === 'ENTITLEMENTS' && rows.length === 0"
        title="暂无权益"
      />
      <PageEmptyState
        v-else-if="!loading && activeTab === 'REDEMPTIONS' && redemptions.length === 0"
        title="暂无核销记录"
      />
      <PageEmptyState
        v-else-if="!loading && activeTab === 'TRANSFERS' && transfers.length === 0"
        title="暂无转赠记录"
      />

      <el-table v-else-if="activeTab === 'ENTITLEMENTS'" :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="权益ID" width="240" />
        <el-table-column prop="ownerId" label="归属ID（ownerId）" width="240" />
        <el-table-column prop="entitlementType" label="类型" width="160" />
        <el-table-column prop="serviceType" label="服务类别" width="160" />
        <el-table-column label="次数" width="120">
          <template #default="scope">{{ scope.row.remainingCount }}/{{ scope.row.totalCount }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="validUntil" label="有效期至" width="200" />
      </el-table>

      <el-table v-else-if="activeTab === 'REDEMPTIONS'" :data="redemptions" :loading="loading" style="width: 100%">
        <el-table-column prop="redemptionTime" label="时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="serviceType" label="服务类别" width="160" />
        <el-table-column prop="userId" label="用户ID（userId）" width="220" />
        <el-table-column prop="venueId" label="场所ID（venueId）" width="220" />
        <el-table-column prop="operatorId" label="操作员ID（operatorId）" width="220" />
        <el-table-column prop="entitlementId" label="权益ID（entitlementId）" width="240" />
        <el-table-column prop="failureReason" label="失败原因" min-width="220" />
      </el-table>

      <el-table v-else :data="transfers" :loading="loading" style="width: 100%">
        <el-table-column prop="transferredAt" label="时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column prop="fromOwnerId" label="转出方（fromOwnerId）" width="240" />
        <el-table-column prop="toOwnerId" label="转入方（toOwnerId）" width="240" />
        <el-table-column prop="entitlementId" label="权益ID（entitlementId）" width="240" />
        <el-table-column prop="status" label="状态" width="140" />
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

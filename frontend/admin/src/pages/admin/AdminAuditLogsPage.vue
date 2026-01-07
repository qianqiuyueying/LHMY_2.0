<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type AuditLog = {
  id: string
  actorType: 'ADMIN' | 'USER' | 'DEALER' | 'PROVIDER' | 'PROVIDER_STAFF'
  actorId: string
  action: 'CREATE' | 'UPDATE' | 'PUBLISH' | 'OFFLINE' | 'APPROVE' | 'REJECT' | 'LOGIN' | 'LOGOUT'
  resourceType: string
  resourceId?: string | null
  summary?: string | null
  ip?: string | null
  userAgent?: string | null
  metadata?: unknown
  createdAt: string
}

function _fmtBeijingDateTime(isoUtc: string): string {
  // Spec: Admin 审计日志时间统一展示为北京时间（UTC+8）
  // 后端 createdAt 口径：UTC ISO8601 + Z，例如 2026-01-07T12:34:56Z
  const d = new Date(isoUtc)
  if (Number.isNaN(d.getTime())) return isoUtc
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const m: Record<string, string> = {}
  for (const p of parts) {
    if (p.type !== 'literal') m[p.type] = p.value
  }
  // YYYY-MM-DD HH:mm:ss
  return `${m.year}-${m.month}-${m.day} ${m.hour}:${m.minute}:${m.second}`
}

const ACTOR_TYPE_LABEL: Record<AuditLog['actorType'], string> = {
  ADMIN: '平台运营',
  USER: '用户',
  DEALER: '经销商',
  PROVIDER: '场所',
  PROVIDER_STAFF: '场所员工',
}

const ACTION_LABEL: Record<AuditLog['action'], string> = {
  CREATE: '创建',
  UPDATE: '更新',
  PUBLISH: '发布',
  OFFLINE: '下线',
  APPROVE: '通过',
  REJECT: '驳回',
  LOGIN: '登录',
  LOGOUT: '退出',
}

const filters = reactive({
  actorType: '',
  actorId: '',
  action: '',
  resourceType: '',
  resourceId: '',
  keyword: '',
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<AuditLog[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<AuditLog>>('/admin/audit-logs', {
      query: {
        actorType: filters.actorType || null,
        actorId: filters.actorId || null,
        action: filters.action || null,
        resourceType: filters.resourceType || null,
        resourceId: filters.resourceId || null,
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

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="审计日志" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="100px">
        <el-form-item label="操作者类型">
          <el-select v-model="filters.actorType" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="运营后台（ADMIN）" value="ADMIN" />
            <el-option label="场所后台（PROVIDER）" value="PROVIDER" />
            <el-option label="场所员工（PROVIDER_STAFF）" value="PROVIDER_STAFF" />
            <el-option label="经销商（DEALER）" value="DEALER" />
            <el-option label="C 端用户（USER）" value="USER" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作者ID">
          <el-input v-model="filters.actorId" placeholder="精确匹配" style="width: 220px" />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="登录（LOGIN）" value="LOGIN" />
            <el-option label="退出（LOGOUT）" value="LOGOUT" />
            <el-option label="创建（CREATE）" value="CREATE" />
            <el-option label="更新（UPDATE）" value="UPDATE" />
            <el-option label="通过（APPROVE）" value="APPROVE" />
            <el-option label="驳回（REJECT）" value="REJECT" />
            <el-option label="发布（PUBLISH）" value="PUBLISH" />
            <el-option label="下线（OFFLINE）" value="OFFLINE" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象类型">
          <el-input v-model="filters.resourceType" placeholder="例如：ORDER / PRODUCT / BOOKING" style="width: 220px" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="摘要模糊匹配" style="width: 200px" />
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="Object.assign(filters,{actorType:'',actorId:'',action:'',resourceType:'',resourceId:'',keyword:'',dateFrom:'',dateTo:''});page=1;load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无审计日志" />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column label="时间" width="200">
          <template #default="scope">
            {{ _fmtBeijingDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作者类型" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.actorType" placement="top">
              <el-tag size="small">{{ ACTOR_TYPE_LABEL[scope.row.actorType as keyof typeof ACTOR_TYPE_LABEL] ?? scope.row.actorType }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="actorId" label="操作者ID" width="220" />
        <el-table-column label="动作" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.action" placement="top">
              <el-tag size="small">{{ ACTION_LABEL[scope.row.action as keyof typeof ACTION_LABEL] ?? scope.row.action }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="resourceType" label="对象" width="160" />
        <el-table-column prop="resourceId" label="对象ID" width="220" />
        <el-table-column prop="summary" label="摘要" min-width="220" />
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

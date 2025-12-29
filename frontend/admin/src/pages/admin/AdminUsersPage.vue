<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { handleApiError } from '../../lib/error-handling'

type UserListItem = {
  id: string
  nickname: string
  phoneMasked?: string | null
  identities?: string[]
  enterpriseId?: string | null
  enterpriseName?: string | null
  createdAt: string
}

type UserDetail = {
  id: string
  nickname: string
  avatar?: string | null
  phoneMasked?: string | null
  identities?: string[]
  enterpriseId?: string | null
  enterpriseName?: string | null
  createdAt: string
}

const filters = reactive({
  phone: '',
  nickname: '',
  identity: '' as '' | 'MEMBER' | 'EMPLOYEE',
  enterpriseId: '',
  enterpriseName: '',
})

const loading = ref(false)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const rows = ref<UserListItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const drawerOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<UserDetail | null>(null)
const router = useRouter()

function reset() {
  filters.phone = ''
  filters.nickname = ''
  filters.identity = ''
  filters.enterpriseId = ''
  filters.enterpriseName = ''
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<UserListItem>>('/admin/users', {
      query: {
        phone: filters.phone || null,
        nickname: filters.nickname || null,
        identity: filters.identity || null,
        enterpriseId: filters.enterpriseId || null,
        enterpriseName: filters.enterpriseName || null,
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

async function openDetail(id: string) {
  drawerOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await apiRequest<UserDetail>(`/admin/users/${encodeURIComponent(id)}`)
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    detailLoading.value = false
  }
}

const route = useRoute()
onMounted(() => {
  const eid = String(route.query.enterpriseId || '').trim()
  if (eid) {
    filters.enterpriseId = eid
  }
  load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="用户列表" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="手机号">
          <el-input v-model="filters.phone" placeholder="明文手机号（若接口支持）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="filters.nickname" placeholder="昵称" style="width: 220px" />
        </el-form-item>
        <el-form-item label="身份">
          <el-select v-model="filters.identity" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="会员（MEMBER）" value="MEMBER" />
            <el-option label="员工（EMPLOYEE）" value="EMPLOYEE" />
          </el-select>
        </el-form-item>
        <el-form-item label="企业ID">
          <el-input v-model="filters.enterpriseId" placeholder="enterpriseId（精确）" style="width: 240px" />
        </el-form-item>
        <el-form-item label="企业">
          <el-input v-model="filters.enterpriseName" placeholder="企业名称" style="width: 220px" />
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
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无用户" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="用户ID" width="240" />
        <el-table-column prop="nickname" label="昵称" width="180" />
        <el-table-column prop="phoneMasked" label="手机号（脱敏）" width="160" />
        <el-table-column label="身份" width="180">
          <template #default="scope">
            <el-tag v-for="x in scope.row.identities || []" :key="x" size="small" style="margin-right: 6px">{{ x }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enterpriseName" label="企业" min-width="180" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button type="primary" link @click="openDetail(scope.row.id)">详情</el-button>
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

    <el-drawer v-model="drawerOpen" title="用户详情" size="520px">
      <el-skeleton v-if="detailLoading" :rows="8" animated />
      <el-empty v-else-if="!detail" description="暂无数据" />
      <el-descriptions v-else :column="1" border>
        <el-descriptions-item label="用户ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="昵称">{{ detail.nickname }}</el-descriptions-item>
        <el-descriptions-item label="手机号（脱敏）">{{ detail.phoneMasked || '—' }}</el-descriptions-item>
        <el-descriptions-item label="身份">
          <el-tag v-for="x in detail.identities || []" :key="x" size="small" style="margin-right: 6px">{{ x }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="企业">{{ detail.enterpriseName || '—' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.createdAt }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<style scoped></style>

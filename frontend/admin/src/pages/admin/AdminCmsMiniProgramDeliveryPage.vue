<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type CmsContentListItem = {
  id: string
  title: string
  summary?: string | null
  mpStatus?: 'DRAFT' | 'PUBLISHED' | 'OFFLINE' | null
  mpPublishedAt?: string | null
  updatedAt: string
}

const router = useRouter()

const loading = ref(false)
const rows = ref<CmsContentListItem[]>([])
const error = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const filters = reactive({
  status: '' as '' | 'DRAFT' | 'PUBLISHED' | 'OFFLINE',
  keyword: '',
})
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function loadList() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<CmsContentListItem>>('/admin/cms/contents', {
      query: {
        scope: 'MINI_PROGRAM',
        status: filters.status || null,
        keyword: filters.keyword || null,
        includeContent: false,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
    error.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载内容失败'
    error.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

function goEditInContentCenter(id: string) {
  void router.push({ path: '/admin/cms/content-center', query: { editId: id } })
}

async function publishMp(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/publish`, { method: 'POST', query: { scope: 'MINI_PROGRAM' } })
    ElMessage.success('已发布到小程序')
    await loadList()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineMp(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/offline`, { method: 'POST', query: { scope: 'MINI_PROGRAM' } })
    ElMessage.success('小程序已下线')
    await loadList()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

onMounted(async () => {
  await loadList()
})
</script>

<template>
  <div>
    <PageHeaderBar title="小程序投放（CMS）" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="90px" style="margin-bottom: 12px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="草稿（DRAFT）" value="DRAFT" />
            <el-option label="已发布（PUBLISHED）" value="PUBLISHED" />
            <el-option label="已下线（OFFLINE）" value="OFFLINE" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="标题/摘要" style="width: 240px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; loadList()">查询</el-button>
          <el-button @click="filters.status='';filters.keyword='';page=1;loadList()">重置</el-button>
          <el-button @click="loadList">刷新</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && error" :message="error" :code="errorCode" :requestId="errorRequestId" @retry="loadList" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无内容" />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="内容ID" width="260" />
        <el-table-column prop="title" label="标题" min-width="260" />
        <el-table-column prop="mpStatus" label="小程序状态" width="140" />
        <el-table-column prop="updatedAt" label="更新时间" width="200" />
        <el-table-column label="操作" width="460">
          <template #default="scope">
            <el-button size="small" @click="goEditInContentCenter(scope.row.id)">去内容中心编辑</el-button>
            <el-divider direction="vertical" />
            <el-button v-if="scope.row.mpStatus !== 'PUBLISHED'" type="success" size="small" plain @click="publishMp(scope.row.id)">
              发布到小程序
            </el-button>
            <el-button v-if="scope.row.mpStatus === 'PUBLISHED'" type="warning" size="small" plain @click="offlineMp(scope.row.id)">
              小程序下线
            </el-button>
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
          @change="loadList"
        />
      </div>
    </el-card>
  </div>
</template>



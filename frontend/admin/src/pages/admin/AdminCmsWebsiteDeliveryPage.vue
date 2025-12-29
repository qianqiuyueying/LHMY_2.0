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

type CmsChannel = { id: string; name: string; sort: number; status: 'ENABLED' | 'DISABLED' }
type CmsContentListItem = {
  id: string
  channelId?: string | null
  title: string
  coverImageUrl?: string | null
  summary?: string | null
  status: 'DRAFT' | 'PUBLISHED' | 'OFFLINE'
  publishedAt?: string | null
  updatedAt: string
}

const router = useRouter()

const tab = ref<'channels' | 'contents' | 'recommendedVenues'>('channels')

const channels = ref<CmsChannel[]>([])
const channelLoading = ref(false)
const channelError = ref('')
const channelErrorCode = ref('')
const channelErrorRequestId = ref('')

const channelDialogOpen = ref(false)
const channelEditingId = ref<string | null>(null)
const channelForm = reactive({ name: '', sort: 0, status: 'ENABLED' as 'ENABLED' | 'DISABLED' })

const contentsLoading = ref(false)
const contents = ref<CmsContentListItem[]>([])
const contentsError = ref('')
const contentsErrorCode = ref('')
const contentsErrorRequestId = ref('')
const contentFilters = reactive({
  channelId: '',
  status: '' as '' | CmsContentListItem['status'],
  keyword: '',
})
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 官网首页推荐场所（与官网首页“推荐场所”模块一致）
type RecommendedVenueItem = { venueId: string; name: string; publishStatus: string }
type RecommendedVenuesResp = { version: string; items: RecommendedVenueItem[]; enabled: boolean }
const recLoading = ref(false)
const recSaving = ref(false)
const recError = ref('')
const recErrorCode = ref('')
const recErrorRequestId = ref('')
const recEnabled = ref(false)
const recVersion = ref('0')
const recItems = ref<RecommendedVenueItem[]>([])

const recNewVenueId = ref('')
const recVenueSearchLoading = ref(false)
const recVenueOptions = ref<Array<{ value: string; label: string; name: string; publishStatus: string }>>([])

async function loadRecommendedVenues() {
  recLoading.value = true
  try {
    const data = await apiRequest<RecommendedVenuesResp>('/admin/website/home/recommended-venues')
    recEnabled.value = !!(data as any).enabled
    recVersion.value = data.version || '0'
    recItems.value = (data.items || []).map((x) => ({
      venueId: String((x as any).venueId || '').trim(),
      name: String((x as any).name || ''),
      publishStatus: String((x as any).publishStatus || ''),
    }))
    recError.value = ''
    recErrorCode.value = ''
    recErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    recError.value = msg
    recErrorCode.value = e?.apiError?.code ?? ''
    recErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    recLoading.value = false
  }
}

async function searchRecommendedVenueOptions(keyword: string) {
  const kw = String(keyword || '').trim()
  if (!kw) {
    recVenueOptions.value = []
    return
  }
  recVenueSearchLoading.value = true
  try {
    const data = await apiRequest<PageResp<any>>('/admin/venues', {
      // 口径：推荐候选以“审核通过”为准；若尚未发布，上线会在保存推荐时自动补发布
      query: { keyword: kw, reviewStatus: 'APPROVED', page: 1, pageSize: 20 },
    })
    recVenueOptions.value = (data.items || []).map((x: any) => {
      const id = String(x.id || '').trim()
      const name = String(x.name || '').trim()
      const ps = String(x.publishStatus || '').trim()
      const providerName = String(x.providerName || '').trim()
      const label = `${name || id}${providerName ? `（${providerName}）` : ''}（发布=${ps || '-'} / id=${id}）`
      return { value: id, label, name, publishStatus: ps }
    })
  } catch (e: any) {
    recVenueOptions.value = []
    handleApiError(e, { router, fallbackMessage: '场所搜索失败' })
  } finally {
    recVenueSearchLoading.value = false
  }
}

function addRecommendedVenue() {
  const vid = String(recNewVenueId.value || '').trim()
  if (!vid) return ElMessage.error('请选择场所')
  if (recItems.value.some((x) => x.venueId === vid)) return ElMessage.error('该场所已在推荐列表中')
  const opt = recVenueOptions.value.find((x) => x.value === vid)
  recItems.value.push({ venueId: vid, name: opt?.name || '', publishStatus: opt?.publishStatus || '' })
  recNewVenueId.value = ''
}

function removeRecommendedVenueAt(i: number) {
  recItems.value.splice(i, 1)
}

function moveRecommendedVenueUp(i: number) {
  if (i <= 0) return
  const a = recItems.value[i]
  const b = recItems.value[i - 1]
  if (!a || !b) return
  recItems.value[i - 1] = a
  recItems.value[i] = b
}

function moveRecommendedVenueDown(i: number) {
  if (i >= recItems.value.length - 1) return
  const a = recItems.value[i]
  const b = recItems.value[i + 1]
  if (!a || !b) return
  recItems.value[i + 1] = a
  recItems.value[i] = b
}

async function saveRecommendedVenues() {
  const venueIds = recItems.value.map((x) => String(x.venueId || '').trim()).filter(Boolean)
  if (venueIds.length !== recItems.value.length) return ElMessage.error('推荐列表中存在空的场所ID')
  recSaving.value = true
  try {
    // 若场所尚未发布：这里补“发布上线”，确保官网/小程序读侧能看到
    for (const it of recItems.value) {
      const vid = String(it.venueId || '').trim()
      if (!vid) continue
      const ps = String(it.publishStatus || '').toUpperCase()
      if (ps !== 'PUBLISHED') {
        await apiRequest(`/admin/venues/${vid}/publish`, { method: 'POST' })
      }
    }
    await apiRequest('/admin/website/home/recommended-venues', {
      method: 'PUT',
      body: { enabled: recEnabled.value, items: venueIds.map((venueId) => ({ venueId })) },
    })
    ElMessage.success('已保存')
    await loadRecommendedVenues()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    recSaving.value = false
  }
}

const assignDialogOpen = ref(false)
const assignTargetId = ref<string>('')
const assignChannelId = ref<string>('')

async function loadChannels() {
  channelLoading.value = true
  try {
    const data = await apiRequest<{ items: CmsChannel[] }>('/admin/cms/channels')
    channels.value = data.items
    channelError.value = ''
    channelErrorCode.value = ''
    channelErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载栏目失败'
    channelError.value = msg
    channelErrorCode.value = e?.apiError?.code ?? ''
    channelErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    channelLoading.value = false
  }
}

function openCreateChannel() {
  channelEditingId.value = null
  channelForm.name = ''
  channelForm.sort = 0
  channelForm.status = 'ENABLED'
  channelDialogOpen.value = true
}

function openEditChannel(row: CmsChannel) {
  channelEditingId.value = row.id
  channelForm.name = row.name
  channelForm.sort = row.sort
  channelForm.status = row.status
  channelDialogOpen.value = true
}

async function saveChannel() {
  try {
    if (!channelForm.name.trim()) {
      ElMessage.error('栏目名称不能为空')
      return
    }

    if (!channelEditingId.value) {
      await apiRequest('/admin/cms/channels', { method: 'POST', body: { name: channelForm.name, sort: channelForm.sort } })
      ElMessage.success('已创建')
    } else {
      await apiRequest(`/admin/cms/channels/${channelEditingId.value}`, {
        method: 'PUT',
        body: { name: channelForm.name, sort: channelForm.sort, status: channelForm.status },
      })
      ElMessage.success('已保存')
    }

    channelDialogOpen.value = false
    await loadChannels()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

async function loadContents() {
  contentsLoading.value = true
  try {
    const data = await apiRequest<PageResp<CmsContentListItem>>('/admin/cms/contents', {
      query: {
        scope: 'WEB',
        channelId: contentFilters.channelId || null,
        status: contentFilters.status || null,
        keyword: contentFilters.keyword || null,
        includeContent: false,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    contents.value = data.items
    total.value = data.total
    contentsError.value = ''
    contentsErrorCode.value = ''
    contentsErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载内容失败'
    contentsError.value = msg
    contentsErrorCode.value = e?.apiError?.code ?? ''
    contentsErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    contentsLoading.value = false
  }
}

function _channelName(id: string | null | undefined): string {
  if (!id) return '（未分配）'
  return channels.value.find((c) => c.id === id)?.name ?? id
}

function openAssignChannel(row: CmsContentListItem) {
  assignTargetId.value = row.id
  assignChannelId.value = String(row.channelId || '')
  assignDialogOpen.value = true
}

async function saveAssignChannel() {
  try {
    await apiRequest(`/admin/cms/contents/${assignTargetId.value}`, { method: 'PUT', body: { channelId: assignChannelId.value || '' } })
    ElMessage.success('已设置栏目')
    assignDialogOpen.value = false
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '设置栏目失败' })
  }
}

function goEditInContentCenter(id: string) {
  void router.push({ path: '/admin/cms/content-center', query: { editId: id } })
}

async function publishWeb(row: CmsContentListItem) {
  if (!String(row.channelId || '').trim()) {
    ElMessage.error('请先设置栏目，再发布到官网')
    return
  }
  try {
    await apiRequest(`/admin/cms/contents/${row.id}/publish`, { method: 'POST', query: { scope: 'WEB' } })
    ElMessage.success('已发布到官网')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineWeb(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/offline`, { method: 'POST', query: { scope: 'WEB' } })
    ElMessage.success('官网已下线')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

onMounted(async () => {
  await loadChannels()
  await loadContents()
  await loadRecommendedVenues()
})
</script>

<template>
  <div>
    <PageHeaderBar title="官网投放（CMS）" />

    <el-card style="margin-top: 12px">
      <el-tabs v-model="tab">
        <el-tab-pane label="栏目" name="channels">
          <div style="margin-bottom: 12px">
            <el-button type="primary" @click="openCreateChannel">新增栏目</el-button>
            <el-button :loading="channelLoading" @click="loadChannels">刷新</el-button>
          </div>

          <PageErrorState
            v-if="!channelLoading && channelError"
            :message="channelError"
            :code="channelErrorCode"
            :requestId="channelErrorRequestId"
            @retry="loadChannels"
          />
          <PageEmptyState v-else-if="!channelLoading && channels.length === 0" title="暂无栏目" />
          <el-table v-else :data="channels" :loading="channelLoading" style="width: 100%">
            <el-table-column prop="id" label="栏目ID" width="260" />
            <el-table-column prop="name" label="名称" min-width="220" />
            <el-table-column prop="sort" label="排序" width="100" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="操作" width="140">
              <template #default="scope">
                <el-button type="primary" size="small" @click="openEditChannel(scope.row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="内容投放" name="contents">
          <el-form :inline="true" label-width="90px" style="margin-bottom: 12px">
            <el-form-item label="栏目">
              <el-select v-model="contentFilters.channelId" placeholder="全部" style="width: 220px">
                <el-option label="全部" value="" />
                <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="contentFilters.status" placeholder="全部" style="width: 180px">
                <el-option label="全部" value="" />
                <el-option label="草稿（DRAFT）" value="DRAFT" />
                <el-option label="已发布（PUBLISHED）" value="PUBLISHED" />
                <el-option label="已下线（OFFLINE）" value="OFFLINE" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键字">
              <el-input v-model="contentFilters.keyword" placeholder="标题/摘要" style="width: 220px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="contentsLoading" @click="page = 1; loadContents()">查询</el-button>
              <el-button @click="contentFilters.channelId='';contentFilters.status='';contentFilters.keyword='';page=1;loadContents()">重置</el-button>
              <el-button @click="loadContents">刷新</el-button>
            </el-form-item>
          </el-form>

          <PageErrorState
            v-if="!contentsLoading && contentsError"
            :message="contentsError"
            :code="contentsErrorCode"
            :requestId="contentsErrorRequestId"
            @retry="loadContents"
          />
          <PageEmptyState v-else-if="!contentsLoading && contents.length === 0" title="暂无内容" />
          <el-table v-else :data="contents" :loading="contentsLoading" style="width: 100%">
            <el-table-column prop="id" label="内容ID" width="260" />
            <el-table-column prop="title" label="标题" min-width="260" />
            <el-table-column label="栏目" width="220">
              <template #default="scope">{{ _channelName(scope.row.channelId) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="官网状态" width="120" />
            <el-table-column prop="updatedAt" label="更新时间" width="200" />
            <el-table-column label="操作" width="520">
              <template #default="scope">
                <el-button size="small" @click="goEditInContentCenter(scope.row.id)">去内容中心编辑</el-button>
                <el-button size="small" @click="openAssignChannel(scope.row)">设置栏目</el-button>
                <el-divider direction="vertical" />
                <el-button v-if="scope.row.status !== 'PUBLISHED'" type="success" size="small" @click="publishWeb(scope.row)">发布到官网</el-button>
                <el-button v-if="scope.row.status === 'PUBLISHED'" type="warning" size="small" @click="offlineWeb(scope.row.id)">官网下线</el-button>
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
              @change="loadContents"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="推荐场所" name="recommendedVenues">
          <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
            <template #title>官网首页「推荐场所」</template>
            <div style="line-height: 1.7">
              <div>这里控制官网首页推荐场所模块的展示/不展示，以及推荐列表（仅允许选择已发布场所）。</div>
            </div>
          </el-alert>

          <el-card :loading="recLoading" class="lh-card">
            <PageErrorState v-if="!recLoading && recError" :message="recError" :code="recErrorCode" :requestId="recErrorRequestId" @retry="loadRecommendedVenues" />
            <div v-else>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px">
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
                  <el-switch v-model="recEnabled" active-text="对外展示" inactive-text="不展示" />
                  <span style="font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ recVersion }}</span>
                </div>
                <div style="display: flex; gap: 8px">
                  <el-button :disabled="recLoading" @click="loadRecommendedVenues">刷新</el-button>
                  <el-button type="primary" :loading="recSaving" @click="saveRecommendedVenues">保存</el-button>
                </div>
              </div>

              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px">
                <el-select
                  v-model="recNewVenueId"
                  filterable
                  remote
                  clearable
                  reserve-keyword
                  :remote-method="searchRecommendedVenueOptions"
                  :loading="recVenueSearchLoading"
                  placeholder="搜索并选择场所（仅 PUBLISHED）"
                  style="max-width: 520px; width: 100%"
                >
                  <el-option v-for="opt in recVenueOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
                <el-button type="primary" @click="addRecommendedVenue">添加</el-button>
              </div>

              <el-table :data="recItems" row-key="venueId" border style="width: 100%">
                <el-table-column type="index" width="60" label="#" />
                <el-table-column prop="venueId" label="场所ID" min-width="220" />
                <el-table-column prop="name" label="场所名称（回显）" min-width="220" />
                <el-table-column prop="publishStatus" label="发布状态（回显）" width="160" />
                <el-table-column label="操作" width="220">
                  <template #default="{ $index }">
                    <el-button size="small" @click="moveRecommendedVenueUp($index)">上移</el-button>
                    <el-button size="small" @click="moveRecommendedVenueDown($index)">下移</el-button>
                    <el-button size="small" type="danger" @click="removeRecommendedVenueAt($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="channelDialogOpen" :title="channelEditingId ? '编辑栏目' : '新增栏目'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="channelForm.name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="channelForm.sort" />
        </el-form-item>
        <el-form-item v-if="channelEditingId" label="状态">
          <el-select v-model="channelForm.status" style="width: 180px">
            <el-option label="启用（ENABLED）" value="ENABLED" />
            <el-option label="停用（DISABLED）" value="DISABLED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="channelDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="saveChannel">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="assignDialogOpen" title="设置栏目（官网）" width="520px">
      <el-form label-width="90px">
        <el-form-item label="栏目">
          <el-select v-model="assignChannelId" placeholder="请选择栏目" style="width: 320px">
            <el-option label="（不分配）" value="" />
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="saveAssignChannel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>



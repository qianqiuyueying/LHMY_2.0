<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { uploadImage } from '../../lib/uploads'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import MarkdownIt from 'markdown-it'
import { fmtBeijingDateTime } from '../../lib/time'

type CmsChannel = {
  id: string
  name: string
  sort: number
  status: 'ENABLED' | 'DISABLED'
}

type CmsContentListItem = {
  id: string
  channelId: string
  title: string
  coverImageUrl?: string | null
  summary?: string | null
  status: 'DRAFT' | 'PUBLISHED' | 'OFFLINE'
  publishedAt?: string | null
  mpStatus?: 'DRAFT' | 'PUBLISHED' | 'OFFLINE' | null
  mpPublishedAt?: string | null
  effectiveFrom?: string | null
  effectiveUntil?: string | null
  createdAt: string
  updatedAt: string
  contentHtml?: string | null
  contentMd?: string | null
}

const tab = ref<'channels' | 'contents'>('channels')
const router = useRouter()

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
  scope: '' as '' | 'WEB' | 'MINI_PROGRAM',
  status: '' as '' | CmsContentListItem['status'],
  keyword: '',
})
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const contentDialogOpen = ref(false)
const contentEditingId = ref<string | null>(null)
const contentForm = reactive({
  channelId: '',
  title: '',
  coverImageUrl: '',
  summary: '',
  contentMd: '',
  legacyHtml: '',
  effectiveFrom: '',
  effectiveUntil: '',
})

const contentMdInputRef = ref<any>(null)
const contentBodyUploading = ref(false)
const contentBodyTab = ref<'edit' | 'preview'>('edit')

function _getContentMdTextarea(): HTMLTextAreaElement | null {
  const inst: any = contentMdInputRef.value
  return (inst?.textarea as HTMLTextAreaElement | undefined) ?? (inst?.$refs?.textarea as HTMLTextAreaElement | undefined) ?? null
}

function insertIntoMarkdown(md: string): void {
  const v = String(contentForm.contentMd || '')
  const ta = _getContentMdTextarea()
  if (!ta) {
    contentForm.contentMd = v + md
    return
  }

  const start = typeof ta.selectionStart === 'number' ? ta.selectionStart : v.length
  const end = typeof ta.selectionEnd === 'number' ? ta.selectionEnd : start
  contentForm.contentMd = v.slice(0, start) + md + v.slice(end)
  void nextTick(() => {
    try {
      ta.focus()
      const pos = start + md.length
      ta.selectionStart = pos
      ta.selectionEnd = pos
    } catch {
      // ignore
    }
  })
}

async function uploadAndInsertContentImage(raw: any) {
  const f = raw?.raw as File | undefined
  if (!f) return

  // 避免“当前是历史 HTML，但上传动作会悄悄切到 Markdown”造成困惑
  const hasMd = !!String(contentForm.contentMd || '').trim()
  const hasLegacy = !!String(contentForm.legacyHtml || '').trim()
  if (!hasMd && hasLegacy) {
    ElMessage.warning('当前正文为“历史HTML模式”。如需插入图片，请先将正文迁移为 Markdown 再保存。')
    return
  }

  contentBodyUploading.value = true
  try {
    const url = await uploadImage(f)
    const alt = '图片'
    const snippet = `\n\n![${alt}](${url})\n\n`
    insertIntoMarkdown(snippet)
    ElMessage.success('已上传并插入到正文（Markdown）')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? '上传失败'))
  } finally {
    contentBodyUploading.value = false
  }
}

function _isSafeUrl(raw: string): boolean {
  const s = String(raw || '').trim()
  if (!s) return false
  const lower = s.toLowerCase()
  if (lower.startsWith('javascript:') || lower.startsWith('vbscript:') || lower.startsWith('file:')) return false
  // 允许：相对路径、http(s)、协议相对
  if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('//')) return true
  if (lower.startsWith('/')) return true
  // 其他无协议链接（如 a/b.png）也允许
  if (!lower.includes(':')) return true
  return false
}

const _md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
})

// 安全：过滤不安全 href/src（与小程序配置中心同口径）
_md.renderer.rules.link_open = (tokens: any[], idx: number, options: any, _env: any, self: any) => {
  const t = tokens[idx]
  const href = t.attrGet('href') || ''
  if (!_isSafeUrl(href)) t.attrSet('href', '#')
  t.attrSet('rel', 'nofollow noopener noreferrer')
  return self.renderToken(tokens, idx, options)
}
_md.renderer.rules.image = (tokens: any[], idx: number, options: any, _env: any, self: any) => {
  const t = tokens[idx]
  const src = t.attrGet('src') || ''
  if (!_isSafeUrl(src)) t.attrSet('src', '')
  return self.renderToken(tokens, idx, options)
}

const contentPreviewHtml = computed(() => {
  const md = String(contentForm.contentMd || '')
  if (!md.trim()) return '<p style="color: rgba(0,0,0,.6)">暂无正文（Markdown）</p>'
  try {
    return _md.render(md)
  } catch {
    return `<p>${md}</p>`
  }
})

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
      await apiRequest<CmsChannel>('/admin/cms/channels', {
        method: 'POST',
        body: { name: channelForm.name, sort: channelForm.sort },
      })
      ElMessage.success('已创建')
    } else {
      await apiRequest<CmsChannel>(`/admin/cms/channels/${channelEditingId.value}`, {
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
        channelId: contentFilters.channelId || null,
        scope: contentFilters.scope || null,
        status: contentFilters.status || null,
        keyword: contentFilters.keyword || null,
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

function openCreateContent() {
  contentEditingId.value = null
  contentForm.channelId = channels.value[0]?.id ?? ''
  contentForm.title = ''
  contentForm.coverImageUrl = ''
  contentForm.summary = ''
  contentForm.contentMd = ''
  contentForm.legacyHtml = ''
  contentForm.effectiveFrom = ''
  contentForm.effectiveUntil = ''
  contentBodyTab.value = 'edit'
  contentDialogOpen.value = true
}

async function openEditContent(row: CmsContentListItem) {
  contentEditingId.value = row.id
  contentForm.channelId = row.channelId
  contentForm.title = row.title
  contentForm.coverImageUrl = row.coverImageUrl ?? ''
  contentForm.summary = row.summary ?? ''
  contentForm.contentMd = row.contentMd ?? ''
  contentForm.legacyHtml = row.contentHtml ?? ''
  contentForm.effectiveFrom = row.effectiveFrom ?? ''
  contentForm.effectiveUntil = row.effectiveUntil ?? ''
  contentBodyTab.value = 'edit'
  contentDialogOpen.value = true
}

async function saveContent() {
  try {
    if (!contentForm.channelId) {
      ElMessage.error('请选择栏目')
      return
    }
    if (!contentForm.title.trim()) {
      ElMessage.error('标题不能为空')
      return
    }
    const hasMd = !!contentForm.contentMd.trim()
    const hasLegacyHtml = !!contentForm.legacyHtml.trim()
    if (!hasMd && !hasLegacyHtml) {
      ElMessage.error('正文不能为空（推荐 Markdown）')
      return
    }

    const body = {
      channelId: contentForm.channelId,
      title: contentForm.title,
      coverImageUrl: contentForm.coverImageUrl || undefined,
      summary: contentForm.summary || undefined,
      contentMd: hasMd ? contentForm.contentMd : undefined,
      contentHtml: !hasMd && hasLegacyHtml ? contentForm.legacyHtml : undefined,
      effectiveFrom: contentForm.effectiveFrom || undefined,
      effectiveUntil: contentForm.effectiveUntil || undefined,
    }

    if (!contentEditingId.value) {
      await apiRequest('/admin/cms/contents', { method: 'POST', body })
      ElMessage.success('已创建')
    } else {
      await apiRequest(`/admin/cms/contents/${contentEditingId.value}`, { method: 'PUT', body })
      ElMessage.success('已保存')
    }

    contentDialogOpen.value = false
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

async function publishContent(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/publish`, { method: 'POST', query: { scope: 'WEB' } })
    ElMessage.success('已发布到官网')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineContent(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/offline`, { method: 'POST', query: { scope: 'WEB' } })
    ElMessage.success('官网已下线')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

async function publishContentMp(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/publish`, { method: 'POST', query: { scope: 'MINI_PROGRAM' } })
    ElMessage.success('已发布到小程序')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineContentMp(id: string) {
  try {
    await apiRequest(`/admin/cms/contents/${id}/offline`, { method: 'POST', query: { scope: 'MINI_PROGRAM' } })
    ElMessage.success('小程序已下线')
    await loadContents()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

onMounted(async () => {
  await loadChannels()
  await loadContents()
})
</script>

<template>
  <div>
    <PageHeaderBar title="CMS 内容管理" />

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

        <el-tab-pane label="内容" name="contents">
          <el-form :inline="true" label-width="90px" style="margin-bottom: 12px">
            <el-form-item label="栏目">
              <el-select v-model="contentFilters.channelId" placeholder="全部" style="width: 220px">
                <el-option label="全部" value="" />
                <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="投放端">
              <el-select v-model="contentFilters.scope" placeholder="全部" style="width: 180px">
                <el-option label="全部" value="" />
                <el-option label="官网（WEB）" value="WEB" />
                <el-option label="小程序（MINI_PROGRAM）" value="MINI_PROGRAM" />
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
              <el-button @click="contentFilters.channelId='';contentFilters.scope='';contentFilters.status='';contentFilters.keyword='';page=1;loadContents()">重置</el-button>
              <el-button type="success" @click="openCreateContent">新增内容</el-button>
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
            <el-table-column prop="channelId" label="栏目" width="240" />
            <el-table-column v-if="contentFilters.scope !== 'MINI_PROGRAM'" prop="status" label="官网发布" width="120" />
            <el-table-column v-if="contentFilters.scope !== 'WEB'" prop="mpStatus" label="小程序发布" width="120" />
            <el-table-column prop="updatedAt" label="更新时间" width="200" :formatter="fmtBeijingDateTime" />
            <el-table-column label="操作" width="420">
              <template #default="scope">
                <el-button type="primary" size="small" @click="openEditContent(scope.row)">编辑</el-button>
                <el-button
                  v-if="contentFilters.scope !== 'MINI_PROGRAM' && scope.row.status !== 'PUBLISHED'"
                  type="success"
                  size="small"
                  @click="publishContent(scope.row.id)"
                >
                  发布到官网
                </el-button>
                <el-button
                  v-if="contentFilters.scope !== 'MINI_PROGRAM' && scope.row.status === 'PUBLISHED'"
                  type="warning"
                  size="small"
                  @click="offlineContent(scope.row.id)"
                >
                  官网下线
                </el-button>
                <el-divider v-if="contentFilters.scope === ''" direction="vertical" />
                <el-button
                  v-if="contentFilters.scope !== 'WEB' && scope.row.mpStatus !== 'PUBLISHED'"
                  type="success"
                  size="small"
                  plain
                  @click="publishContentMp(scope.row.id)"
                >
                  发布到小程序
                </el-button>
                <el-button
                  v-if="contentFilters.scope !== 'WEB' && scope.row.mpStatus === 'PUBLISHED'"
                  type="warning"
                  size="small"
                  plain
                  @click="offlineContentMp(scope.row.id)"
                >
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
              @change="loadContents"
            />
          </div>
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

    <el-dialog v-model="contentDialogOpen" :title="contentEditingId ? '编辑内容' : '新增内容'" width="760px">
      <el-form label-width="110px">
        <el-form-item label="栏目">
          <el-select v-model="contentForm.channelId" style="width: 320px">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="contentForm.title" />
        </el-form-item>
        <el-form-item label="封面URL">
          <el-input v-model="contentForm.coverImageUrl" placeholder="可选" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="contentForm.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="正文(Markdown)">
          <el-tabs v-model="contentBodyTab" type="border-card">
            <el-tab-pane label="编辑" name="edit">
              <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap">
                <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="uploadAndInsertContentImage">
                  <el-button size="small" type="primary" plain :loading="contentBodyUploading">上传图片并插入</el-button>
                </el-upload>
                <span style="font-size: 12px; color: rgba(0,0,0,.6)">
                  插图语法：<code>![alt](/static/uploads/...)</code>（保存时后台会将 Markdown 转为安全 HTML）
                </span>
              </div>
              <el-input
                ref="contentMdInputRef"
                v-model="contentForm.contentMd"
                type="textarea"
                :rows="12"
                placeholder="推荐：Markdown（支持图片/列表/标题等）"
              />
              <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">
                小程序侧渲染使用 HTML；后台会在保存时把 Markdown 转为安全 HTML。
              </div>
            </el-tab-pane>

            <el-tab-pane label="预览" name="preview">
              <el-alert type="info" show-icon :closable="false" style="margin-bottom: 10px">
                <template #title>本地预览</template>
                <div style="line-height: 1.7">
                  这里的预览用于编辑辅助；后台保存时会将 Markdown 转为安全 HTML，最终渲染以保存结果为准。
                </div>
              </el-alert>
              <div class="cms-md-preview" v-html="contentPreviewHtml" />
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        <el-form-item v-if="!contentForm.contentMd.trim() && contentForm.legacyHtml.trim()" label="历史HTML（只读）">
          <el-input v-model="contentForm.legacyHtml" type="textarea" :rows="8" readonly />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">
            这是历史版本的 HTML 内容（不建议继续编辑）。如需迁移为 Markdown，请复制后手动改写为 Markdown 再保存。
          </div>
        </el-form-item>
        <el-form-item label="生效起">
          <el-input v-model="contentForm.effectiveFrom" placeholder="ISO8601 或 YYYY-MM-DD（可选）" />
        </el-form-item>
        <el-form-item label="生效止">
          <el-input v-model="contentForm.effectiveUntil" placeholder="ISO8601 或 YYYY-MM-DD（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="contentDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="saveContent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cms-md-preview {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.75);
  max-height: 420px;
  overflow: auto;
  line-height: 1.75;
}

.cms-md-preview :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
  margin: 10px 0;
}

.cms-md-preview :deep(h1),
.cms-md-preview :deep(h2),
.cms-md-preview :deep(h3) {
  margin: 14px 0 8px;
  font-weight: 800;
}

.cms-md-preview :deep(p) {
  margin: 0 0 10px;
}

.cms-md-preview :deep(ul),
.cms-md-preview :deep(ol) {
  margin: 0 0 10px 20px;
}

.cms-md-preview :deep(pre) {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.04);
  overflow: auto;
}
</style>

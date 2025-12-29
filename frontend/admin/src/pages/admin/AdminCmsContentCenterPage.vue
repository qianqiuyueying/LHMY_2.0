<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { uploadImage } from '../../lib/uploads'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import MarkdownIt from 'markdown-it'

type CmsContentItem = {
  id: string
  channelId?: string | null
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

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const items = ref<CmsContentItem[]>([])
const error = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const filters = reactive({
  keyword: '',
})
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const editorOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
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
const coverUploading = ref(false)
const contentBodyTab = ref<'edit' | 'preview'>('edit')

type AssetRow = { id: string; url: string; originalFilename?: string | null; createdAt?: string | null }
const assetPickerOpen = ref(false)
const assetPickerTarget = ref<'cover' | 'body'>('cover')
const assetKeyword = ref('')
const assetRows = ref<AssetRow[]>([])
const assetLoading = ref(false)
const assetSelectedId = ref<string | null>(null)

async function loadAssets() {
  assetLoading.value = true
  try {
    const data = await apiRequest<{ items: AssetRow[] }>('/admin/assets', { query: { kind: 'IMAGE', keyword: assetKeyword.value || undefined, page: 1, pageSize: 50 } })
    assetRows.value = data.items || []
  } catch (e: any) {
    ElMessage.error(String(e?.apiError?.message ?? '加载资产失败'))
    assetRows.value = []
  } finally {
    assetLoading.value = false
  }
}

function openAssetPicker(target: 'cover' | 'body') {
  assetPickerTarget.value = target
  assetKeyword.value = ''
  assetSelectedId.value = null
  assetPickerOpen.value = true
  loadAssets()
}

function confirmAssetPick() {
  const id = String(assetSelectedId.value || '').trim()
  if (!id) return ElMessage.error('请选择一张图片')
  const row = assetRows.value.find((x) => x.id === id) || null
  if (!row?.url) return ElMessage.error('图片 url 为空')
  if (assetPickerTarget.value === 'cover') {
    form.coverImageUrl = row.url
    assetPickerOpen.value = false
    return
  }
  insertIntoMarkdown(`\n\n![图片](${row.url})\n\n`)
  assetPickerOpen.value = false
}

function _getContentMdTextarea(): HTMLTextAreaElement | null {
  const inst: any = contentMdInputRef.value
  return (inst?.textarea as HTMLTextAreaElement | undefined) ?? (inst?.$refs?.textarea as HTMLTextAreaElement | undefined) ?? null
}

function insertIntoMarkdown(md: string): void {
  const v = String(form.contentMd || '')
  const ta = _getContentMdTextarea()
  if (!ta) {
    form.contentMd = v + md
    return
  }

  const start = typeof ta.selectionStart === 'number' ? ta.selectionStart : v.length
  const end = typeof ta.selectionEnd === 'number' ? ta.selectionEnd : start
  form.contentMd = v.slice(0, start) + md + v.slice(end)
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

async function uploadAndInsertImage(raw: any) {
  const f = raw?.raw as File | undefined
  if (!f) return

  const hasMd = !!String(form.contentMd || '').trim()
  const hasLegacy = !!String(form.legacyHtml || '').trim()
  if (!hasMd && hasLegacy) {
    ElMessage.warning('当前正文为“历史HTML模式”。如需插入图片，请先将正文迁移为 Markdown 再保存。')
    return
  }

  contentBodyUploading.value = true
  try {
    const url = await uploadImage(f)
    insertIntoMarkdown(`\n\n![图片](${url})\n\n`)
    ElMessage.success('已上传并插入到正文（Markdown）')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? '上传失败'))
  } finally {
    contentBodyUploading.value = false
  }
}

async function uploadCoverImage(raw: any) {
  const f = raw?.raw as File | undefined
  if (!f) return
  coverUploading.value = true
  try {
    const url = await uploadImage(f)
    form.coverImageUrl = url
    ElMessage.success('封面已上传')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? '上传失败'))
  } finally {
    coverUploading.value = false
  }
}

function _isSafeUrl(raw: string): boolean {
  const s = String(raw || '').trim()
  if (!s) return false
  const lower = s.toLowerCase()
  if (lower.startsWith('javascript:') || lower.startsWith('vbscript:') || lower.startsWith('file:')) return false
  if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('//')) return true
  if (lower.startsWith('/')) return true
  if (!lower.includes(':')) return true
  return false
}

const _md = new MarkdownIt({ html: false, linkify: true, breaks: true, typographer: true })
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

const previewHtml = computed(() => {
  const md = String(form.contentMd || '')
  if (!md.trim()) return '<p style="color: rgba(0,0,0,.6)">暂无正文（Markdown）</p>'
  try {
    return _md.render(md)
  } catch {
    return `<p>${md}</p>`
  }
})

async function loadList() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<CmsContentItem>>('/admin/cms/contents', {
      query: { keyword: filters.keyword || null, page: page.value, pageSize: pageSize.value, includeContent: false },
    })
    items.value = data.items
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

function openCreate() {
  editingId.value = null
  form.title = ''
  form.coverImageUrl = ''
  form.summary = ''
  form.contentMd = ''
  form.legacyHtml = ''
  form.effectiveFrom = ''
  form.effectiveUntil = ''
  contentBodyTab.value = 'edit'
  editorOpen.value = true
}

async function openEditById(id: string) {
  try {
    const data = await apiRequest<CmsContentItem>(`/admin/cms/contents/${id}`)
    editingId.value = data.id
    form.title = data.title ?? ''
    form.coverImageUrl = data.coverImageUrl ?? ''
    form.summary = data.summary ?? ''
    form.contentMd = data.contentMd ?? ''
    form.legacyHtml = data.contentHtml ?? ''
    form.effectiveFrom = data.effectiveFrom ?? ''
    form.effectiveUntil = data.effectiveUntil ?? ''
    contentBodyTab.value = 'edit'
    editorOpen.value = true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '打开编辑失败' })
  }
}

async function save() {
  try {
    if (!form.title.trim()) {
      ElMessage.error('标题不能为空')
      return
    }
    const hasMd = !!form.contentMd.trim()
    const hasLegacyHtml = !!form.legacyHtml.trim()
    if (!hasMd && !hasLegacyHtml) {
      ElMessage.error('正文不能为空（推荐 Markdown）')
      return
    }

    const body = {
      title: form.title,
      coverImageUrl: form.coverImageUrl || undefined,
      summary: form.summary || undefined,
      contentMd: hasMd ? form.contentMd : undefined,
      contentHtml: !hasMd && hasLegacyHtml ? form.legacyHtml : undefined,
      effectiveFrom: form.effectiveFrom || undefined,
      effectiveUntil: form.effectiveUntil || undefined,
    }

    if (!editingId.value) {
      await apiRequest('/admin/cms/contents', { method: 'POST', body })
      ElMessage.success('已创建')
    } else {
      await apiRequest(`/admin/cms/contents/${editingId.value}`, { method: 'PUT', body })
      ElMessage.success('已保存')
    }
    editorOpen.value = false
    await loadList()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

function goWebsiteDelivery() {
  void router.push('/admin/cms/website')
}
function goMiniProgramDelivery() {
  void router.push('/admin/cms/mini-program')
}

onMounted(async () => {
  await loadList()
  const editId = String(route.query.editId || '').trim()
  if (editId) await openEditById(editId)
})
</script>

<template>
  <div>
    <PageHeaderBar title="内容中心（CMS）" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="80px" style="margin-bottom: 12px">
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="标题/摘要" style="width: 260px" @keyup.enter="page=1;loadList()" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; loadList()">查询</el-button>
          <el-button @click="filters.keyword='';page=1;loadList()">重置</el-button>
          <el-button type="success" @click="openCreate">新增内容</el-button>
          <el-button @click="goWebsiteDelivery">去官网投放</el-button>
          <el-button @click="goMiniProgramDelivery">去小程序投放</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && error" :message="error" :code="errorCode" :requestId="errorRequestId" @retry="loadList" />
      <PageEmptyState v-else-if="!loading && items.length === 0" title="暂无内容" />
      <el-table v-else :data="items" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="内容ID" width="260" />
        <el-table-column prop="title" label="标题" min-width="260" />
        <el-table-column prop="status" label="官网状态" width="120" />
        <el-table-column prop="mpStatus" label="小程序状态" width="120" />
        <el-table-column prop="updatedAt" label="更新时间" width="200" />
        <el-table-column label="操作" width="160">
          <template #default="scope">
            <el-button type="primary" size="small" @click="openEditById(scope.row.id)">编辑</el-button>
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

    <el-dialog v-model="editorOpen" :title="editingId ? '编辑内容（内容中心）' : '新增内容（内容中心）'" width="820px">
      <el-form label-width="110px">
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="封面URL">
          <div style="width: 100%">
            <div style="display:flex; gap:8px; align-items:center; flex-wrap: wrap">
              <el-input v-model="form.coverImageUrl" placeholder="可选（/static/uploads/... 或 https://...）" style="flex: 1; min-width: 320px" />
              <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="uploadCoverImage">
                <el-button size="small" type="primary" plain :loading="coverUploading">上传封面</el-button>
              </el-upload>
              <el-button size="small" @click="openAssetPicker('cover')">从资产库选择</el-button>
            </div>
            <div v-if="form.coverImageUrl" style="margin-top: 10px">
              <img :src="form.coverImageUrl" alt="cover" style="max-width: 220px; max-height: 140px; border-radius: 10px; border: 1px solid rgba(0,0,0,.08)" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="正文(Markdown)">
          <el-tabs v-model="contentBodyTab" type="border-card">
            <el-tab-pane label="编辑" name="edit">
              <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap">
                <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="uploadAndInsertImage">
                  <el-button size="small" type="primary" plain :loading="contentBodyUploading">上传图片并插入</el-button>
                </el-upload>
                <el-button size="small" @click="openAssetPicker('body')">从资产库选择插图</el-button>
                <span style="font-size: 12px; color: rgba(0,0,0,.6)">
                  插图语法：<code>![alt](/static/uploads/...)</code>（保存时后台会将 Markdown 转为安全 HTML）
                </span>
              </div>
              <el-input ref="contentMdInputRef" v-model="form.contentMd" type="textarea" :rows="12" placeholder="推荐：Markdown（支持图片/列表/标题等）" />
              <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">
                说明：内容中心只负责编辑与存储；发布到官网/小程序请到“投放”页面操作。
              </div>
            </el-tab-pane>
            <el-tab-pane label="预览" name="preview">
              <el-alert type="info" show-icon :closable="false" style="margin-bottom: 10px">
                <template #title>本地预览</template>
                <div style="line-height: 1.7">后台保存时会将 Markdown 转为安全 HTML，最终渲染以保存结果为准。</div>
              </el-alert>
              <div class="cms-md-preview" v-html="previewHtml" />
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        <el-form-item v-if="!form.contentMd.trim() && form.legacyHtml.trim()" label="历史HTML（只读）">
          <el-input v-model="form.legacyHtml" type="textarea" :rows="8" readonly />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">这是历史版本的 HTML 内容（不建议继续编辑）。</div>
        </el-form-item>
        <el-form-item label="生效起">
          <el-input v-model="form.effectiveFrom" placeholder="ISO8601 或 YYYY-MM-DD（可选）" />
        </el-form-item>
        <el-form-item label="生效止">
          <el-input v-model="form.effectiveUntil" placeholder="ISO8601 或 YYYY-MM-DD（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="assetPickerOpen" title="选择图片（资产库）" width="860px">
      <div style="display:flex; gap:8px; align-items:center; margin-bottom: 10px">
        <el-input v-model="assetKeyword" placeholder="按文件名/url/sha256 搜索" style="flex: 1" @keyup.enter="loadAssets" />
        <el-button :loading="assetLoading" @click="loadAssets">搜索</el-button>
      </div>
      <el-table :data="assetRows" :loading="assetLoading" height="420">
        <el-table-column width="50">
          <template #default="scope">
            <el-radio v-model="assetSelectedId" :label="scope.row.id"><span></span></el-radio>
          </template>
        </el-table-column>
        <el-table-column label="预览" width="120">
          <template #default="scope">
            <img :src="scope.row.url" alt="img" style="width: 96px; height: 64px; object-fit: cover; border-radius: 8px; border: 1px solid rgba(0,0,0,.08)" />
          </template>
        </el-table-column>
        <el-table-column prop="originalFilename" label="文件名" min-width="220" />
        <el-table-column prop="url" label="URL" min-width="320" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
      </el-table>
      <template #footer>
        <el-button @click="assetPickerOpen = false">取消</el-button>
        <el-button type="primary" @click="confirmAssetPick">确定</el-button>
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
</style>



<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type RegionItem = { code: string; name: string; sort: number; enabled: boolean; published?: boolean }

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')

const keyword = ref('')
const debouncedKeyword = ref('')
const page = ref(1)
const pageSize = ref(50)

const items = ref<RegionItem[]>([])
const version = ref('0')
const router = useRouter()

watch(
  () => keyword.value,
  () => {
    // 简单防抖：避免大数据量下每次输入都触发全量 filter + 表格渲染
    const v = String(keyword.value || '')
    const t = setTimeout(() => {
      debouncedKeyword.value = v
      page.value = 1
    }, 180)
    return () => clearTimeout(t)
  },
)

const filteredAll = computed(() => {
  const kw = debouncedKeyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((x) => {
    const c = String(x.code || '').toLowerCase()
    const n = String(x.name || '').toLowerCase()
    return c.includes(kw) || n.includes(kw)
  })
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredAll.value.slice(start, start + pageSize.value)
})

const publishedCount = computed(() => items.value.filter((x) => !!x.published).length)
const enabledCount = computed(() => items.value.filter((x) => !!x.enabled).length)
const publishedEnabledCount = computed(() => items.value.filter((x) => !!x.published && !!x.enabled).length)

function getRowStatus(row: RegionItem): { online: 'PUBLISHED' | 'DRAFT'; visibility: 'ENABLED' | 'DISABLED' } {
  return { online: row?.published ? 'PUBLISHED' : 'DRAFT', visibility: row?.enabled ? 'ENABLED' : 'DISABLED' }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: RegionItem[]; version: string }>('/admin/regions/cities')
    items.value = (data.items || []).slice().sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0))
    version.value = data.version || '0'
    debouncedKeyword.value = keyword.value
    page.value = 1
    loadError.value = ''
    loadErrorCode.value = ''
    loadErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    loadError.value = msg
    loadErrorCode.value = e?.apiError?.code ?? ''
    loadErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

function validateDraft(): string | null {
  for (const [idx, x] of items.value.entries()) {
    const code = String(x?.code || '').trim()
    const name = String(x?.name || '').trim()
    if (!code) return `第 ${idx + 1} 行 code 不能为空`
    if (!name) return `第 ${idx + 1} 行 name 不能为空`
    if (!/^(CITY|PROVINCE):\d{6}$/.test(code)) return `第 ${idx + 1} 行 code 不合法：${code}`
  }
  // code 唯一性（后端也会兜底）
  const set = new Set<string>()
  for (const x of items.value) {
    const code = String(x.code || '').trim()
    if (set.has(code)) return `code 重复：${code}`
    set.add(code)
  }
  return null
}

async function saveDraft() {
  const err = validateDraft()
  if (err) return ElMessage.error(err)
  saving.value = true
  try {
    await apiRequest('/admin/regions/cities', { method: 'PUT', body: { items: items.value } })
    ElMessage.success('已保存草稿')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    saving.value = false
  }
}

async function publishAll() {
  try {
    await ElMessageBox.confirm('确认发布当前草稿？发布后各端（H5/官网/小程序/Provider）读侧将读取到最新版本。', '发布', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiRequest('/admin/regions/cities/publish', { method: 'POST' })
    ElMessage.success('已发布')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineAll() {
  try {
    await ElMessageBox.confirm('确认下线所有区域配置？下线后读侧将返回空列表（可能影响端侧下拉选择）。', '下线', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiRequest('/admin/regions/cities/offline', { method: 'POST' })
    ElMessage.success('已下线')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

async function importCn() {
  try {
    await ElMessageBox.confirm('将一键导入“全国省级 + 地级（不含区县）”列表到草稿中（默认覆盖现有草稿）。导入后需要点击“发布”。', '一键导入', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiRequest('/admin/regions/cities/import-cn', { method: 'POST' })
    ElMessage.success('已导入到草稿（未发布）')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '导入失败' })
  }
}

function addRow() {
  items.value.unshift({ code: 'CITY:110100', name: '北京', sort: 0, enabled: true, published: false })
}

function removeRow(row: RegionItem) {
  items.value = items.value.filter((x) => x !== row)
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="区域/城市配置（REGION_CITIES）">
      <template #extra>
        <el-button :disabled="loading" @click="load">刷新</el-button>
        <el-button :disabled="loading" @click="addRow">新增一行</el-button>
        <el-button :disabled="loading" @click="importCn">一键导入全国省市</el-button>
        <el-button type="primary" :loading="saving" @click="saveDraft">保存草稿</el-button>
        <el-button type="success" :disabled="loading" @click="publishAll">发布</el-button>
        <el-button type="warning" :disabled="loading" @click="offlineAll">下线</el-button>
      </template>
    </PageHeaderBar>

    <el-card :loading="loading">
      <PageErrorState v-if="!loading && loadError" :message="loadError" :code="loadErrorCode" :requestId="loadErrorRequestId" @retry="load" />

      <template v-else>
        <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 12px">
          <el-input v-model="keyword" placeholder="搜索 code / name" style="max-width: 320px" clearable />
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.55)">
            version={{ version || '0' }}，草稿项={{ items.length }}，草稿启用={{ enabledCount }}，线上已发布={{ publishedCount }}，线上可见={{ publishedEnabledCount }}
          </div>
        </div>

        <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
          <template #title>状态说明（避免草稿/线上混淆）</template>
          <div style="line-height: 1.7">
            <div><b>保存草稿</b>：只更新“草稿表”（不影响线上）。</div>
            <div><b>发布</b>：把当前草稿发布到线上；线上读侧会返回“已发布 + 启用”的城市项。</div>
            <div style="color: var(--lh-muted); margin-top: 6px">
              字段口径：<b>enabled</b>=发布后是否对外可见；<b>published</b>=该条是否在当前线上版本中（新加草稿项发布前为否）。
            </div>
            <div style="color: var(--lh-muted); margin-top: 4px">
              提示：H5 会按 regionLevel 过滤 PROVINCE:* / CITY:*；官网/小程序/Provider 默认仅用 CITY:*。
            </div>
          </div>
        </el-alert>

        <el-table :data="paged" size="small" border style="width: 100%">
          <el-table-column label="状态" width="180">
            <template #default="{ row }">
              <div style="display: flex; gap: 6px; flex-wrap: wrap">
                <el-tag v-if="getRowStatus(row).online === 'PUBLISHED'" type="success" size="small">线上已发布</el-tag>
                <el-tag v-else type="info" size="small">草稿未发布</el-tag>
                <el-tag v-if="getRowStatus(row).visibility === 'ENABLED'" type="success" plain size="small">对外可见</el-tag>
                <el-tag v-else type="warning" plain size="small">对外隐藏</el-tag>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="code" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.code" placeholder="CITY:110100 / PROVINCE:110000" />
            </template>
          </el-table-column>

          <el-table-column label="name" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.name" placeholder="名称" />
            </template>
          </el-table-column>

          <el-table-column label="sort" width="90">
            <template #default="{ row }">
              <el-input v-model.number="row.sort" />
            </template>
          </el-table-column>

          <el-table-column label="对外可见（enabled）" width="150">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>

          <el-table-column label="线上已发布（published）" width="160">
            <template #default="{ row }">
              <el-tag v-if="row.published" type="success">已发布</el-tag>
              <el-tag v-else type="info">未发布</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" link @click="removeRow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="display: flex; justify-content: flex-end; margin-top: 12px">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :total="filteredAll.length"
            layout="total, sizes, prev, pager, next, jumper"
            background
          />
        </div>
      </template>
    </el-card>
  </div>
</template>



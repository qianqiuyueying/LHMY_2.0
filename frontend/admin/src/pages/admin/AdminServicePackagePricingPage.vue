<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

// v2 口径：不再使用“阶梯价格配置”作为健行天下 SERVICE_PACKAGE 的计价来源
const deprecated = true

type PriceObj = { original: number; employee?: number | null; member?: number | null; activity?: number | null }
type RuleItem = {
  id: string
  templateId: string
  regionScope: string
  tier: string
  price: PriceObj
  enabled: boolean
  published?: boolean | null
}

type TemplateItem = { id: string; name: string; regionLevel: string; tier: string }
type TemplatePageResp = { items: TemplateItem[]; page: number; pageSize: number; total: number }

const loading = ref(false)
const items = ref<RuleItem[]>([])
const version = ref('0')
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const templatesLoading = ref(false)
const templates = ref<TemplateItem[]>([])

const templateNameById = computed(() => {
  const m = new Map<string, string>()
  for (const t of templates.value) m.set(t.id, t.name)
  return m
})

const editorOpen = ref(false)
const editorMode = ref<'CREATE' | 'EDIT'>('CREATE')

const form = reactive({
  id: '',
  templateId: '',
  regionScope: '',
  tier: '',
  original: 0,
  enabled: true,
})

function newId(): string {
  // 最小可执行：优先 randomUUID
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function loadTemplates() {
  templatesLoading.value = true
  try {
    const data = await apiRequest<TemplatePageResp>('/admin/service-packages', { query: { page: 1, pageSize: 200 } })
    templates.value = (data.items || []).map((x) => ({ id: x.id, name: x.name, regionLevel: x.regionLevel, tier: x.tier }))
  } catch {
    templates.value = []
  } finally {
    templatesLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: RuleItem[]; version: string }>('/admin/service-package-pricing')
    items.value = (data.items || []) as any
    version.value = String(data.version || '0')
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

function openCreate() {
  editorMode.value = 'CREATE'
  form.id = newId()
  form.templateId = templates.value[0]?.id || ''
  form.regionScope = ''
  form.tier = ''
  form.original = 0
  form.enabled = true
  editorOpen.value = true
}

function openEdit(row: RuleItem) {
  editorMode.value = 'EDIT'
  form.id = row.id
  form.templateId = row.templateId
  form.regionScope = row.regionScope
  form.tier = row.tier
  form.original = Number(row.price?.original ?? 0)
  form.enabled = !!row.enabled
  editorOpen.value = true
}

function validateBeforeSaveRule(): string | null {
  if (!String(form.id || '').trim()) return '规则ID 不能为空'
  if (!String(form.templateId || '').trim()) return '服务包模板不能为空'
  if (!String(form.regionScope || '').trim()) return '区域范围（regionScope）不能为空（例如 CITY:110100）'
  if (!String(form.tier || '').trim()) return '等级/阶梯（tier）不能为空'
  const o = Number(form.original)
  if (!Number.isFinite(o) || o < 0) return '原价必须为 >= 0 的数字'
  return null
}

function upsertRuleIntoList() {
  const idx = items.value.findIndex((x) => x.id === form.id)
  const rule: RuleItem = {
    id: String(form.id).trim(),
    templateId: String(form.templateId).trim(),
    regionScope: String(form.regionScope).trim(),
    tier: String(form.tier).trim(),
    enabled: !!form.enabled,
    price: {
      original: Number(form.original),
      employee: null,
      member: null,
      activity: null,
    },
    published: idx >= 0 ? items.value[idx]?.published : false,
  }
  if (idx >= 0) items.value.splice(idx, 1, rule)
  else items.value.unshift(rule)
}

async function saveRule() {
  const err = validateBeforeSaveRule()
  if (err) return ElMessage.error(err)

  // 本地先保证唯一性（后端也会校验）
  const key = `${String(form.templateId).trim()}|${String(form.regionScope).trim()}|${String(form.tier).trim()}`
  const duplicated = items.value.some((x) => `${x.templateId}|${x.regionScope}|${x.tier}` === key && x.id !== form.id)
  if (duplicated) return ElMessage.error('重复规则：同一 templateId + regionScope + tier 只能存在 1 条')

  upsertRuleIntoList()
  editorOpen.value = false
}

async function removeRule(row: RuleItem) {
  try {
    await ElMessageBox.confirm('确认删除该规则？（仅删除草稿，需点“保存草稿”才会写入）', '删除规则', { type: 'warning' })
  } catch {
    return
  }
  items.value = items.value.filter((x) => x.id !== row.id)
}

async function saveDraft() {
  try {
    await apiRequest('/admin/service-package-pricing', { method: 'PUT', body: { items: items.value } })
    ElMessage.success('已保存草稿')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '保存失败')
  }
}

async function publishAll() {
  try {
    await apiRequest('/admin/service-package-pricing/publish', { method: 'POST' })
    ElMessage.success('已发布')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '发布失败')
  }
}

async function offlineAll() {
  try {
    await apiRequest('/admin/service-package-pricing/offline', { method: 'POST' })
    ElMessage.success('已下线')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '下线失败')
  }
}

onMounted(async () => {
  await loadTemplates()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="阶梯价格配置（服务包）" />

    <el-card style="margin-top: 12px">
      <el-alert type="warning" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>已废弃（v2 口径）</template>
        <div style="line-height: 1.7">
          <div>健行天下 SERVICE_PACKAGE 下单计价已改为：使用“计价商品（Product）”的 <b>price.original</b>。</div>
          <div style="margin-top: 4px; color: rgba(0, 0, 0, 0.65)">
            本页仅保留历史规则查看（留档），不再建议新增/发布/下线。
          </div>
        </div>
      </el-alert>

      <el-alert
        title="说明：本页配置的是「健行天下 · 服务包（SERVICE_PACKAGE）」下单计价规则。v1 口径：服务包仅有“一个售价（原价）”；employee/member/activity 等差异化价格不在健行天下启用（保留字段仅为结构兼容）。"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />
      <el-alert type="warning" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>regionScope 是什么？</template>
        <div style="line-height: 1.7">
          <div>regionScope 用统一编码表示“该规则适用的区域范围”，格式固定为：<b>{LEVEL}:{CODE}</b></div>
          <div style="margin-top: 4px; color: rgba(0, 0, 0, 0.65)">
            示例：CITY:110100（市） / PROVINCE:440000（省） / COUNTRY:CN（国）。LEVEL 必须与服务包模板的 regionLevel 一致。
          </div>
        </div>
      </el-alert>

      <div style="margin-bottom: 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="success" :loading="templatesLoading" :disabled="deprecated" @click="openCreate">新增规则</el-button>
        <el-button type="primary" :disabled="deprecated" @click="saveDraft">保存草稿</el-button>
        <el-button type="success" :disabled="deprecated" @click="publishAll">发布</el-button>
        <el-button type="warning" :disabled="deprecated" @click="offlineAll">下线</el-button>
        <el-tag type="info">version={{ version }}</el-tag>
      </div>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && items.length === 0" title="暂无阶梯价格规则" />

      <el-table v-else :data="items" :loading="loading" style="width: 100%">
        <el-table-column label="服务包模板" min-width="260">
          <template #default="scope">
            <div style="font-weight: 700">{{ templateNameById.get(scope.row.templateId) || '（未知模板）' }}</div>
            <div style="margin-top: 4px; font-size: 12px; color: rgba(0, 0, 0, 0.6)">{{ scope.row.templateId }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="regionScope" label="区域范围（regionScope）" width="220" />
        <el-table-column prop="tier" label="等级/阶梯（tier）" width="160" />
        <el-table-column label="价格（元）" min-width="280">
          <template #default="scope">
            <div style="font-weight: 700">售价：{{ scope.row.price?.original ?? '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="90" />
        <el-table-column prop="published" label="已发布" width="100" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" type="primary" :disabled="deprecated" @click="openEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" :disabled="deprecated" @click="removeRule(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editorOpen" :title="editorMode === 'CREATE' ? '新增规则（草稿）' : '编辑规则（草稿）'" width="760px">
      <el-form label-width="130px">
        <el-form-item label="规则ID">
          <el-input v-model="form.id" disabled />
        </el-form-item>
        <el-form-item label="服务包模板">
          <el-select v-model="form.templateId" filterable style="width: 420px" placeholder="选择服务包模板">
            <el-option v-for="t in templates" :key="t.id" :label="`${t.name} (${t.regionLevel}/${t.tier})`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域范围（regionScope）">
          <el-input v-model="form.regionScope" placeholder="例如：CITY:110100 / PROVINCE:440000 / COUNTRY:CN" style="width: 420px" />
        </el-form-item>
        <el-form-item label="等级/阶梯（tier）">
          <el-input v-model="form.tier" placeholder="例如：DEFAULT / T1 / T2" style="width: 240px" />
        </el-form-item>
        <el-form-item label="原价">
          <el-input-number v-model="form.original" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存到草稿列表</el-button>
      </template>
    </el-dialog>
  </div>
</template>


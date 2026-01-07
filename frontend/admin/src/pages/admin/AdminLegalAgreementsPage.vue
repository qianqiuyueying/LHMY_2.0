<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import { formatBeijingDateTime } from '../../lib/time'

type AgreementCode = 'PROVIDER_INFRA_APPLY' | 'PROVIDER_HEALTH_CARD_APPLY' | 'H5_BUY_AGREEMENT' | 'MP_LOGIN_AGREEMENT'
type AgreementStatus = 'DRAFT' | 'PUBLISHED' | 'OFFLINE' | string

type AgreementDto = {
  id?: string
  code: AgreementCode
  title: string
  contentHtml: string
  contentMd?: string | null
  version: string
  status: AgreementStatus
  publishedAt?: string | null
  updatedAt?: string | null
}

const codes: Array<{ code: AgreementCode; label: string; hint: string }> = [
  { code: 'PROVIDER_INFRA_APPLY', label: 'Provider 基建联防申请协议', hint: 'Provider 开通基建联防（电商）前展示' },
  { code: 'PROVIDER_HEALTH_CARD_APPLY', label: 'Provider 健行天下申请协议', hint: 'Provider 提交健行天下开通审核前展示' },
  { code: 'H5_BUY_AGREEMENT', label: 'H5 购买协议', hint: 'H5 购买页“服务协议”内容来源' },
  { code: 'MP_LOGIN_AGREEMENT', label: '小程序登录服务协议', hint: '小程序个人中心登录提示区提供入口' },
]

const active = ref<AgreementCode>('H5_BUY_AGREEMENT')
const loading = ref(false)
const saving = ref(false)

const state = reactive({
  title: '',
  contentMd: '',
  legacyHtml: '',
  version: '',
  status: 'DRAFT' as AgreementStatus,
  publishedAt: '' as string,
  updatedAt: '' as string,
})

const publishedAtBeijing = computed(() => (state.publishedAt ? formatBeijingDateTime(state.publishedAt) : ''))
const updatedAtBeijing = computed(() => (state.updatedAt ? formatBeijingDateTime(state.updatedAt) : ''))

const activeMeta = computed(() => codes.find((x) => x.code === active.value))

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<AgreementDto>(`/admin/legal/agreements/${active.value}`)
    state.title = String(data.title || '')
    state.contentMd = String(data.contentMd || '')
    state.legacyHtml = String((!data.contentMd && data.contentHtml) ? data.contentHtml : '')
    state.version = String(data.version || '0')
    state.status = String(data.status || 'DRAFT')
    state.publishedAt = String(data.publishedAt || '')
    state.updatedAt = String(data.updatedAt || '')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

async function saveDraft(): Promise<boolean> {
  const title = String(state.title || '').trim()
  if (!title) {
    ElMessage.error('标题不能为空')
    return false
  }
  saving.value = true
  try {
    const data = await apiRequest<AgreementDto>(`/admin/legal/agreements/${active.value}`, {
      method: 'PUT',
      // v2：version 由后端自动生成（时间戳），确保每次内容变更都会触发 version 更新，便于小程序“按版本重新同意协议”
      body: { title, contentMd: state.contentMd || '', version: null },
    })
    state.version = String(data.version || state.version || '0')
    state.status = String(data.status || state.status)
    state.publishedAt = String(data.publishedAt || '')
    state.updatedAt = String(data.updatedAt || '')
    ElMessage.success('已保存草稿')
    return true
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '保存失败')
    return false
  } finally {
    saving.value = false
  }
}

async function publish() {
  saving.value = true
  try {
    // v2：发布前自动保存草稿（避免“协议不存在” 404，也符合运营的一键发布习惯）
    const ok = await saveDraft()
    if (!ok) return
    const data = await apiRequest<AgreementDto>(`/admin/legal/agreements/${active.value}/publish`, { method: 'POST' })
    state.status = String(data.status || state.status)
    state.publishedAt = String(data.publishedAt || '')
    state.updatedAt = String(data.updatedAt || '')
    ElMessage.success('已发布')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '发布失败')
  } finally {
    saving.value = false
  }
}

async function offline() {
  saving.value = true
  try {
    const data = await apiRequest<AgreementDto>(`/admin/legal/agreements/${active.value}/offline`, { method: 'POST' })
    state.status = String(data.status || state.status)
    state.updatedAt = String(data.updatedAt || '')
    ElMessage.success('已下线')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '下线失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="协议/条款管理" />

    <el-card class="lh-card" style="margin-top: 12px" :loading="loading">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>使用说明（v1 最小）</template>
        <div style="line-height: 1.7">
          <div>协议流程：编辑草稿 → 保存草稿 → 发布（各端仅读已发布版本）。</div>
          <div style="color: var(--lh-muted); margin-top: 4px">支持多类别：Provider 申请协议 / H5 购买协议 / 小程序登录协议。</div>
        </div>
      </el-alert>

      <el-form label-width="120px" style="max-width: 980px">
        <el-form-item label="协议类别">
          <el-select v-model="active" style="width: 360px" @change="load">
            <el-option v-for="x in codes" :key="x.code" :label="x.label" :value="x.code" />
          </el-select>
          <span style="margin-left: 10px; color: var(--lh-muted)">{{ activeMeta?.hint }}</span>
        </el-form-item>

        <el-form-item label="状态">
          <el-tag :type="state.status === 'PUBLISHED' ? 'success' : state.status === 'OFFLINE' ? 'warning' : 'info'">
            {{ state.status }}
          </el-tag>
          <span style="margin-left: 10px; color: var(--lh-muted)">版本：{{ state.version || '0' }}</span>
          <span style="margin-left: 10px; color: var(--lh-muted)">发布时间：{{ publishedAtBeijing || '—' }}</span>
          <span style="margin-left: 10px; color: var(--lh-muted)">更新时间：{{ updatedAtBeijing || '—' }}</span>
        </el-form-item>

        <el-form-item label="标题">
          <el-input v-model="state.title" placeholder="例如：服务协议" />
        </el-form-item>

        <el-form-item label="内容（Markdown）">
          <el-input v-model="state.contentMd" type="textarea" :rows="14" placeholder="推荐：Markdown（支持图片/列表/标题等）" />
          <div style="margin-top: 6px; font-size: 12px; color: var(--lh-muted)">
            发布时后台会把 Markdown 转为安全 HTML，供 H5/小程序富文本渲染。
          </div>
        </el-form-item>

        <el-form-item v-if="!state.contentMd.trim() && state.legacyHtml.trim()" label="历史HTML（只读）">
          <el-input v-model="state.legacyHtml" type="textarea" :rows="10" readonly />
          <div style="margin-top: 6px; font-size: 12px; color: var(--lh-muted)">
            这是历史版本的 HTML 内容（不建议继续编辑）。如需迁移为 Markdown，请复制后手动改写为 Markdown 再保存。
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveDraft">保存草稿</el-button>
          <el-button type="success" :loading="saving" @click="publish">发布</el-button>
          <el-button type="warning" :loading="saving" @click="offline">下线</el-button>
          <el-button :loading="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>



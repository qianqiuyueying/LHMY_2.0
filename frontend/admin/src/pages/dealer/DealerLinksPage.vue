<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiException, apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError as handleApiErrorGlobal } from '../../lib/error-handling'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import { useRouter } from 'vue-router'

function formatYmd(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

type DealerLink = {
  id: string
  dealerId: string
  productId: string
  sellableCardId?: string | null
  campaign?: string | null
  status: 'ENABLED' | 'DISABLED' | 'EXPIRED'
  validFrom?: string | null
  validUntil?: string | null
  url: string
  uv?: number | null
  paidCount?: number | null
  createdAt: string
}

type SellableCard = {
  id: string
  name: string
  servicePackageTemplateId: string
  regionLevel: 'CITY' | 'PROVINCE' | 'COUNTRY'
  priceOriginal: number
}

const LINK_STATUS_LABEL: Record<DealerLink['status'], string> = {
  ENABLED: '启用',
  DISABLED: '停用',
  EXPIRED: '已过期',
}

const filters = reactive({
  status: '' as '' | DealerLink['status'],
  sellableCardId: '',
  keyword: '',
  dateFrom: '',
  dateTo: '',
})

// 口径调整：不再暴露“链接类型”概念给经销商
// - 生成“经销商入口链接”（sellableCardId=null）：用于 H5 查看该经销商全部可售卡
// - “某卡直达购卡页”通过入口链接 + sellableCardId 组合得到

const createForm = reactive({
  sellableCardId: '',
  campaign: '',
  validFrom: '',
  validUntil: '',
})

const loading = ref(false)
const rows = ref<DealerLink[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

const sellableCardsLoading = ref(false)
const sellableCards = ref<SellableCard[]>([])
const sellableCardById = ref(new Map<string, SellableCard>())

async function loadSellableCards() {
  sellableCardsLoading.value = true
  try {
    const data = await apiRequest<{ items: SellableCard[]; total: number }>('/dealer/sellable-cards')
    sellableCards.value = data.items || []
    sellableCardById.value = new Map((sellableCards.value || []).map((x) => [x.id, x]))
    if (!createForm.sellableCardId && sellableCards.value[0]?.id) createForm.sellableCardId = sellableCards.value[0].id
  } catch {
    sellableCards.value = []
    sellableCardById.value = new Map()
  } finally {
    sellableCardsLoading.value = false
  }
}

function handleApiError(e: unknown, fallbackMessage: string): void {
  // 统一口径（过渡期）：优先使用全局错误处理；保留本地旧逻辑作为兜底
  try {
    handleApiErrorGlobal(e, { router, fallbackMessage, preferRefreshHintOn409: true })
    return
  } catch {
    // ignore
  }

  if (e instanceof ApiException) {
    const code = e.apiError.code
    // 401：apiRequest 已统一跳转登录
    if (e.status === 401) return
    if (e.status === 403 || code === 'FORBIDDEN') {
      try {
        router.push('/403')
      } catch {
        // ignore
      }
      return
    }
    if (e.status === 409 && (code === 'STATE_CONFLICT' || code === 'INVALID_STATE_TRANSITION')) {
      ElMessage.warning('状态已变化，请刷新后重试')
      return
    }
    if (e.status === 400 || e.status === 404) {
      ElMessage.error(
        `${e.apiError.message}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
      )
      return
    }
    ElMessage.error(
      `${e.apiError.message || fallbackMessage}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
    )
    return
  }
  ElMessage.error(fallbackMessage)
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<DealerLink>>('/dealer-links', {
      query: {
        status: filters.status || null,
        sellableCardId: filters.sellableCardId || null,
        keyword: filters.keyword || null,
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    // 页面口径：列表只展示“已授权可售卡”（sellableCardId 非空）的记录；
    // 经销商入口链接单独在上方 alert 展示，避免出现“同一张卡两条 URL”的误解。
    rows.value = (data.items || []).filter((x) => String(x.sellableCardId || '').trim())
    total.value = data.total
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

const entryLinkLoading = ref(false)
const entryLink = ref<DealerLink | null>(null)

async function ensureEntryLink() {
  if (!String(createForm.validUntil || '').trim()) {
    ElMessage.warning('请先填写有效期止（入口链接也需要有效期）')
    return
  }
  entryLinkLoading.value = true
  try {
    // 先查是否已有入口链接（sellableCardId 为空）避免每次刷新都生成一条新记录
    const list = await apiRequest<PageResp<DealerLink>>('/dealer-links', {
      query: { status: 'ENABLED', page: 1, pageSize: 50 },
    })
    const found = (list.items || []).find((x) => !String(x.sellableCardId || '').trim())
    if (found) {
      entryLink.value = found
      return
    }
    // 没有则创建：sellableCardId=null 表示“经销商入口链接”
    entryLink.value = await apiRequest<DealerLink>('/dealer-links', {
      method: 'POST',
      idempotencyKey: `dealer-entry-${createForm.validUntil || 'na'}`,
      body: { sellableCardId: null, campaign: null, validFrom: null, validUntil: createForm.validUntil || null },
    })
  } catch (e: any) {
    entryLink.value = null
    handleApiError(e, '生成入口链接失败')
  } finally {
    entryLinkLoading.value = false
  }
}

function cardDeepLink(cardId: string): string {
  const base = entryLink.value?.url || ''
  if (!base) return ''
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}sellableCardId=${encodeURIComponent(cardId)}`
}

async function createLink() {
  try {
    if (!createForm.sellableCardId.trim()) {
      ElMessage.error('请选择可售卡')
      return
    }

    if (!String(createForm.validUntil || '').trim()) {
      ElMessage.error('请填写有效期止')
      return
    }

    if (createForm.validFrom && createForm.validUntil && String(createForm.validFrom) > String(createForm.validUntil)) {
      ElMessage.error('有效期起不可晚于有效期止')
      return
    }

    const data = await apiRequest<DealerLink>('/dealer-links', {
      method: 'POST',
      idempotencyKey: `dealer-link-${createForm.sellableCardId}-${createForm.validFrom || 'na'}-${createForm.validUntil || 'na'}-${createForm.campaign || 'na'}`,
      body: {
        sellableCardId: createForm.sellableCardId,
        campaign: createForm.campaign || null,
        validFrom: createForm.validFrom || null,
        validUntil: createForm.validUntil || null,
      },
    })

    ElMessage.success('已生成')
    // 将生成结果回填，便于复用
    if (data.sellableCardId) createForm.sellableCardId = data.sellableCardId
    createForm.campaign = data.campaign ?? ''
    await load()
  } catch (e: any) {
    handleApiError(e, '生成失败')
  }
}

async function disableLink(id: string) {
  try {
    await ElMessageBox.confirm('确认停用该链接？停用后该链接将无法继续导流下单。', '确认停用', {
      type: 'warning',
      confirmButtonText: '停用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/dealer-links/${id}/disable`, { method: 'POST' })
    ElMessage.success('已停用')
    await load()
  } catch (e: any) {
    handleApiError(e, '操作失败')
  }
}

// 复制兜底：安卓 WebView / 非 https / 权限限制下，navigator.clipboard 可能失败且无控制台报错
const manualCopyOpen = ref(false)
const manualCopyText = ref('')

async function copy(text: string) {
  const v = String(text || '').trim()
  if (!v) return
  try {
    await navigator.clipboard.writeText(v)
    ElMessage.success('已复制')
  } catch {
    // fallback 1：execCommand（旧浏览器/部分 WebView 可用）
    try {
      const ta = document.createElement('textarea')
      ta.value = v
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.top = '0'
      ta.style.left = '0'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (ok) {
        ElMessage.success('已复制')
        return
      }
    } catch {
      // ignore
    }

    // fallback 2：弹窗手动复制
    manualCopyText.value = v
    manualCopyOpen.value = true
    ElMessage.warning('系统限制导致无法自动复制：请在弹窗中长按/全选后复制')
  }
}

onMounted(async () => {
  // 体验优化：默认给一个 30 天后有效期止（仍可手动修改）
  if (!String(createForm.validUntil || '').trim()) {
    const d = new Date()
    d.setDate(d.getDate() + 30)
    createForm.validUntil = formatYmd(d)
  }
  await loadSellableCards()
  await ensureEntryLink()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="链接/参数管理" />

    <el-alert
      title="v1 口径：二维码图片不由后端返回，前端可对 DealerLink.url 自行生成二维码图像。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <div style="font-weight: 600; margin-bottom: 8px">生成新链接</div>
      <el-form :inline="true" label-width="90px">
        <el-form-item label="选择可售卡">
          <el-select
            v-model="createForm.sellableCardId"
            filterable
            placeholder="请选择"
            style="width: 360px"
            :loading="sellableCardsLoading"
          >
            <el-option
              v-for="c in sellableCards"
              :key="c.id"
              :label="`${c.name}（${c.regionLevel}｜¥${Number(c.priceOriginal ?? 0).toFixed(2)}）`"
              :value="c.id"
            />
          </el-select>
          <div v-if="createForm.sellableCardId && sellableCardById.get(createForm.sellableCardId)" style="margin-top: 6px; font-size: 12px; color: var(--lh-muted)">
            模板ID：{{ sellableCardById.get(createForm.sellableCardId)?.servicePackageTemplateId }}；售价：¥{{
              Number(sellableCardById.get(createForm.sellableCardId)?.priceOriginal ?? 0).toFixed(2)
            }}
          </div>
        </el-form-item>
        <el-form-item label="活动/批次">
          <el-input v-model="createForm.campaign" placeholder="可选" style="width: 200px" />
        </el-form-item>
        <el-form-item label="有效期起">
          <el-date-picker v-model="createForm.validFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="有效期止">
          <el-date-picker v-model="createForm.validUntil" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createLink">生成链接</el-button>
          <el-button :loading="entryLinkLoading" @click="ensureEntryLink">刷新入口链接</el-button>
        </el-form-item>
      </el-form>

      <div style="margin-top: 6px; font-size: 12px; color: rgba(0, 0, 0, 0.55)">
        说明：dealerId 由登录会话自动识别（无需手填）。
      </div>

      <el-alert
        v-if="entryLink?.url"
        type="success"
        :closable="false"
        style="margin-top: 10px"
      >
        <template #title>经销商入口链接（H5 可查看该经销商全部可售卡）</template>
        <div style="margin-top: 6px">
          <el-link type="primary" :underline="false" @click="copy(entryLink?.url || '')">{{ entryLink?.url }}</el-link>
        </div>
      </el-alert>
    </el-card>

    <el-card class="lh-card" style="margin-top: 12px">
      <div style="font-weight: 600; margin-bottom: 8px">链接列表</div>

      <el-form :inline="true" label-width="90px" style="margin-bottom: 10px">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="启用（ENABLED）" value="ENABLED" />
            <el-option label="停用（DISABLED）" value="DISABLED" />
            <el-option label="已过期（EXPIRED）" value="EXPIRED" />
          </el-select>
        </el-form-item>
        <el-form-item label="可售卡ID">
          <el-input v-model="filters.sellableCardId" placeholder="可选（精确）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="链接ID / 可售卡ID / URL / 批次" style="width: 260px" />
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.status='';filters.sellableCardId='';filters.keyword='';filters.dateFrom='';filters.dateTo='';page=1;load()">重置</el-button>
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
        v-else-if="!loading && rows.length === 0"
        title="暂无链接"
        description="可先在上方“生成新链接”，或清空筛选条件后重试。"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="链接ID" width="240" />
        <el-table-column label="可售卡" min-width="220">
          <template #default="scope">
            <div style="font-weight: 600">
              {{ sellableCardById.get(scope.row.sellableCardId || '')?.name || (scope.row.sellableCardId ? '（已删除/不可见）' : '（旧链接）') }}
            </div>
            <div style="font-size: 12px; color: var(--lh-muted)">
              sellableCardId：{{ scope.row.sellableCardId || '-' }}；productId：{{ scope.row.productId }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="campaign" label="批次" width="160" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ LINK_STATUS_LABEL[scope.row.status as keyof typeof LINK_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="URL" min-width="280">
          <template #default="scope">
            <el-link
              v-if="scope.row.sellableCardId && entryLink?.url"
              type="primary"
              :underline="false"
              @click="copy(cardDeepLink(scope.row.sellableCardId))"
            >
              {{ cardDeepLink(scope.row.sellableCardId) }}
            </el-link>
            <span v-else style="color: var(--lh-muted)">请先刷新入口链接</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" :disabled="!(scope.row.sellableCardId && entryLink?.url)" @click="copy(cardDeepLink(scope.row.sellableCardId))">复制</el-button>
            <el-button v-if="scope.row.status === 'ENABLED'" type="warning" size="small" @click="disableLink(scope.row.id)">停用</el-button>
            <el-tag v-else size="small" type="info">只读</el-tag>
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
  </div>

  <el-dialog v-model="manualCopyOpen" title="手动复制" width="720px">
    <el-alert type="warning" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>系统限制导致无法自动复制</template>
      <div style="line-height: 1.7">请在下方输入框中长按/全选后复制。</div>
    </el-alert>
    <el-input v-model="manualCopyText" type="textarea" :rows="4" readonly />
    <template #footer>
      <el-button type="primary" @click="manualCopyOpen = false">知道了</el-button>
    </template>
  </el-dialog>
</template>

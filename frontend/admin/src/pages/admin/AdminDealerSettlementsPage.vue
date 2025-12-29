<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiException, apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError as handleApiErrorGlobal } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { useRouter } from 'vue-router'

type SettlementStatus = 'PENDING_CONFIRM' | 'SETTLED' | 'FROZEN'
type SettlementRow = {
  id: string
  dealerId: string
  cycle: string
  orderCount: number
  amount: number
  status: SettlementStatus
  createdAt?: string | null
  settledAt?: string | null
  payoutMethod?: string | null
  payoutAccount?: any | null
  payoutReferenceLast4?: string | null
  payoutNote?: string | null
  payoutMarkedAt?: string | null
}

type CommissionCfg = { defaultRate: number; dealerOverrides: Record<string, number>; updatedAt?: string | null }

const activeTab = ref<'commission' | 'settlements'>('commission')
const router = useRouter()

const cfgLoading = ref(false)
const cfg = ref<CommissionCfg | null>(null)

type DealerOverrideRow = { dealerId: string; rate: number }

const cfgForm = reactive({
  defaultRate: 0.1,
  overrides: [] as DealerOverrideRow[],
})

function overridesToMap(): Record<string, number> | null {
  const out: Record<string, number> = {}
  for (const row of cfgForm.overrides) {
    const dealerId = String(row.dealerId || '').trim()
    const rate = Number(row.rate)
    if (!dealerId) return null
    if (!Number.isFinite(rate) || rate < 0 || rate > 1) return null
    if (out[dealerId] !== undefined) return null
    out[dealerId] = rate
  }
  return out
}

function addOverrideRow() {
  cfgForm.overrides.unshift({ dealerId: '', rate: Number(cfgForm.defaultRate || 0) })
}

function removeOverrideRow(row: DealerOverrideRow) {
  cfgForm.overrides = cfgForm.overrides.filter((x) => x !== row)
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
    // 401：apiRequest 已统一跳转登录；这里不重复弹窗避免噪声
    if (e.status === 401) return
    // 403：前端路由有门禁，但仍兜底跳 403
    if (e.status === 403 || code === 'FORBIDDEN') {
      try {
        router.push('/403')
      } catch {
        // ignore
      }
      return
    }
    // 409：状态冲突/非法迁移 -> 提示刷新
    if (e.status === 409 && (code === 'STATE_CONFLICT' || code === 'INVALID_STATE_TRANSITION')) {
      ElMessage.warning('状态已变化，请刷新后重试')
      return
    }
    // 400/404：按后端 message 展示（配合 code/requestId 更易排障）
    if (e.status === 400 || e.status === 404) {
      ElMessage.error(
        `${e.apiError.message}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
      )
      return
    }
    // 兜底：保留 message + code + requestId
    ElMessage.error(
      `${e.apiError.message || fallbackMessage}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
    )
    return
  }
  ElMessage.error(fallbackMessage)
}

async function loadCfg() {
  cfgLoading.value = true
  try {
    const data = await apiRequest<CommissionCfg>('/admin/dealer-commission')
    cfg.value = data
    cfgForm.defaultRate = Number(data.defaultRate ?? 0.1)
    const m = data.dealerOverrides ?? {}
    cfgForm.overrides = Object.entries(m).map(([dealerId, rate]) => ({
      dealerId: String(dealerId),
      rate: Number(rate),
    }))
  } catch (e: any) {
    cfg.value = null
    handleApiError(e, '加载失败')
  } finally {
    cfgLoading.value = false
  }
}

async function saveCfg() {
  const overrides = overridesToMap()
  if (!overrides) return ElMessage.error('经销商覆盖比例表单不合法：dealerId 不能为空、比例需在 0~1、且 dealerId 不可重复')
  const r = Number(cfgForm.defaultRate)
  if (!Number.isFinite(r) || r < 0 || r > 1) return ElMessage.error('默认比例必须在 0~1 之间')
  try {
    const data = await apiRequest<CommissionCfg>('/admin/dealer-commission', {
      method: 'PUT',
      body: { defaultRate: r, dealerOverrides: overrides },
    })
    cfg.value = data
    ElMessage.success('已保存')
  } catch (e: any) {
    handleApiError(e, '保存失败')
  }
}

const genLoading = ref(false)
const genForm = reactive({
  cycle: '',
})

async function generate() {
  if (!String(genForm.cycle || '').trim()) return ElMessage.error('cycle 不能为空（YYYY-MM）')
  genLoading.value = true
  try {
    const data = await apiRequest<{ cycle: string; created: number; existing: number; items: any[] }>(
      '/admin/dealer-settlements/generate',
      { method: 'POST', body: { cycle: String(genForm.cycle).trim() } },
    )
    ElMessage.success(`已生成：新增 ${data.created}，已存在 ${data.existing}`)
    await loadSettlements()
  } catch (e: any) {
    handleApiError(e, '生成失败')
  } finally {
    genLoading.value = false
  }
}

const loading = ref(false)
const rows = ref<SettlementRow[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const filters = reactive({
  dealerId: '',
  cycle: '',
  status: '' as '' | SettlementStatus,
})

const statusLabel: Record<SettlementStatus, string> = {
  PENDING_CONFIRM: '待确认',
  SETTLED: '已结算',
  FROZEN: '冻结',
}

const settleDialogOpen = ref(false)
const settling = ref(false)
const settleRow = ref<SettlementRow | null>(null)
const settleForm = reactive({
  payoutReference: '',
  payoutNote: '',
})

function openSettle(row: SettlementRow) {
  settleRow.value = row
  // 规格（TASK-P0-006）：列表不返回打款参考号明文，避免回显；需要结算时由运营输入
  settleForm.payoutReference = ''
  settleForm.payoutNote = String(row.payoutNote || '')
  settleDialogOpen.value = true
}

async function markSettled() {
  if (!settleRow.value?.id) return
  settling.value = true
  try {
    await apiRequest(`/admin/dealer-settlements/${settleRow.value.id}/mark-settled`, {
      method: 'POST',
      body: { payoutReference: settleForm.payoutReference || null, payoutNote: settleForm.payoutNote || null },
    })
    ElMessage.success('已标记为已结算/已打款')
    settleDialogOpen.value = false
    await loadSettlements()
  } catch (e: any) {
    handleApiError(e, '操作失败')
  } finally {
    settling.value = false
  }
}

async function loadSettlements() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<SettlementRow>>('/admin/dealer-settlements', {
      query: {
        dealerId: filters.dealerId || null,
        cycle: filters.cycle || null,
        status: filters.status || null,
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
    // 列表页：错误详情展示在 PageErrorState；同时按 code 做必要跳转/提示
    handleApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

const activeTabTitle = computed(() => (activeTab.value === 'commission' ? '分账比例配置' : '结算单生成/查询'))

onMounted(async () => {
  await loadCfg()
  await loadSettlements()
})
</script>

<template>
  <div>
    <PageHeaderBar title="经销商分账与结算" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>说明（v1 最小）</template>
      <div style="line-height: 1.7">
        <div>本页提供：分账比例配置 + 经销商结算账户/打款信息 + 按月生成结算单（YYYY-MM） + 标记打款。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">结算统计口径：仅统计当月 paidAt 落在周期内的“健行天下已支付订单”。</div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap">
        <div style="font-weight: 800">{{ activeTabTitle }}</div>
        <el-segmented v-model="activeTab" :options="[{ label: '分账比例', value: 'commission' }, { label: '结算单', value: 'settlements' }]" />
      </div>

      <div v-if="activeTab === 'commission'" style="margin-top: 12px">
        <el-form label-width="140px">
          <el-form-item label="默认分账比例（0~1）">
            <el-input-number v-model="cfgForm.defaultRate" :min="0" :max="1" :step="0.01" :precision="2" />
            <div style="margin-left: 10px; font-size: 12px; color: var(--lh-muted)">示例：0.10 表示 10%</div>
          </el-form-item>
          <el-form-item label="经销商覆盖比例（可选）">
            <div style="width: 820px">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px">
                <div style="font-size: 12px; color: var(--lh-muted)">
                  说明：为个别经销商覆盖默认分账比例（0~1）。未配置则使用默认比例。
                </div>
                <el-button size="small" @click="addOverrideRow">新增覆盖</el-button>
              </div>
              <el-table :data="cfgForm.overrides" size="small" border style="width: 100%">
                <el-table-column label="经销商ID" min-width="280">
                  <template #default="{ row }">
                    <el-input v-model="row.dealerId" placeholder="经销商ID（精确）" />
                  </template>
                </el-table-column>
                <el-table-column label="分账比例（0~1）" width="220">
                  <template #default="{ row }">
                    <el-input-number v-model="row.rate" :min="0" :max="1" :step="0.01" :precision="2" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button type="danger" link @click="removeOverrideRow(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="cfgLoading" @click="saveCfg">保存</el-button>
            <el-button :loading="cfgLoading" @click="loadCfg">刷新</el-button>
            <span style="margin-left: 10px; font-size: 12px; color: var(--lh-muted)">updatedAt：{{ cfg?.updatedAt ?? '—' }}</span>
          </el-form-item>
        </el-form>
      </div>

      <div v-else style="margin-top: 12px">
        <el-form :inline="true" label-width="90px" style="margin-bottom: 10px">
          <el-form-item label="生成周期">
            <el-date-picker
              v-model="genForm.cycle"
              type="month"
              value-format="YYYY-MM"
              format="YYYY-MM"
              placeholder="选择月份（YYYY-MM）"
              style="width: 220px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="genLoading" @click="generate">生成结算单</el-button>
          </el-form-item>
        </el-form>

        <el-divider />

        <el-form :inline="true" label-width="90px">
          <el-form-item label="经销商ID">
            <el-input v-model="filters.dealerId" placeholder="可选（精确）" style="width: 260px" />
          </el-form-item>
          <el-form-item label="结算周期">
            <el-date-picker
              v-model="filters.cycle"
              type="month"
              value-format="YYYY-MM"
              format="YYYY-MM"
              placeholder="选择月份"
              style="width: 160px"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" placeholder="全部" style="width: 160px">
              <el-option label="全部" value="" />
              <el-option label="待确认（PENDING_CONFIRM）" value="PENDING_CONFIRM" />
              <el-option label="已结算（SETTLED）" value="SETTLED" />
              <el-option label="冻结（FROZEN）" value="FROZEN" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              @click="
                page = 1;
                loadSettlements()
              "
            >
              查询
            </el-button>
            <el-button
              @click="
                filters.dealerId = '';
                filters.cycle = '';
                filters.status = '';
                page = 1;
                loadSettlements()
              "
            >
              重置
            </el-button>
            <el-button :loading="loading" @click="loadSettlements">刷新</el-button>
          </el-form-item>
        </el-form>

        <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="loadSettlements" />
        <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无结算单" description="可先生成一个周期的结算单，或清空筛选条件后重试。" style="margin-top: 12px" />

        <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
          <el-table-column prop="id" label="结算单号" width="240" />
          <el-table-column prop="dealerId" label="经销商ID" width="240" />
          <el-table-column prop="cycle" label="周期" width="120" />
          <el-table-column prop="orderCount" label="订单数" width="100" />
          <el-table-column prop="amount" label="应结算金额" width="140" />
          <el-table-column label="打款账户" min-width="220">
            <template #default="scope">
              <div v-if="scope.row.payoutAccount">
                <div style="font-weight: 700">{{ scope.row.payoutAccount.accountName || '—' }}</div>
                <div style="color: var(--lh-muted); font-size: 12px">
                  {{ scope.row.payoutAccount.method || scope.row.payoutMethod || '' }}
                  <span v-if="scope.row.payoutAccount.bankName"> · {{ scope.row.payoutAccount.bankName }}</span>
                  <span v-if="scope.row.payoutAccount.accountNoMasked"> · {{ scope.row.payoutAccount.accountNoMasked }}</span>
                </div>
              </div>
              <span v-else style="color: var(--lh-muted)">未配置</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="140">
            <template #default="scope">
              <el-tooltip :content="scope.row.status" placement="top">
                <el-tag size="small">
                  {{ statusLabel[scope.row.status as keyof typeof statusLabel] ?? scope.row.status }}
                </el-tag>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="200" />
          <el-table-column label="操作" width="160">
            <template #default="scope">
              <el-button v-if="scope.row.status === 'PENDING_CONFIRM'" size="small" type="success" @click="openSettle(scope.row)">标记已打款</el-button>
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
            @change="loadSettlements"
          />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="settleDialogOpen" title="标记已打款/已结算" width="640px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>确认打款信息</template>
        <div style="line-height: 1.7">
          <div>结算单：{{ settleRow?.id }}</div>
          <div>金额：¥{{ Number(settleRow?.amount ?? 0).toFixed(2) }}（cycle={{ settleRow?.cycle }}）</div>
        </div>
      </el-alert>

      <div
        v-if="settleRow?.payoutAccount"
        style="margin-bottom: 12px; padding: 10px 12px; border: 1px solid var(--lh-border); border-radius: 8px"
      >
        <div style="font-weight: 700">收款账户</div>
        <div style="margin-top: 6px; color: var(--lh-muted)">
          {{ settleRow.payoutAccount.method || settleRow.payoutMethod }} · {{ settleRow.payoutAccount.accountName }} ·
          {{ settleRow.payoutAccount.bankName || '' }} {{ settleRow.payoutAccount.accountNoMasked || '' }}
        </div>
      </div>

      <el-form label-width="110px">
        <el-form-item label="打款参考号">
          <el-input v-model="settleForm.payoutReference" placeholder="可选：银行回单号/流水号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="settleForm.payoutNote" type="textarea" :rows="3" placeholder="可选：备注信息" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="settleDialogOpen = false">取消</el-button>
        <el-button type="success" :loading="settling" @click="markSettled">确认标记</el-button>
      </template>
    </el-dialog>
  </div>
</template>


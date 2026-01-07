<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import { fmtBeijingDateTime } from '../../lib/time'

type Settlement = {
  id: string
  dealerId: string
  cycle: string
  orderCount: number
  amount: number
  status: 'PENDING_CONFIRM' | 'SETTLED' | 'FROZEN'
  createdAt: string
  settledAt?: string | null
  payoutReferenceLast4?: string | null
  payoutNote?: string | null
}

const SETTLEMENT_STATUS_LABEL: Record<Settlement['status'], string> = {
  PENDING_CONFIRM: '待确认',
  SETTLED: '已结算',
  FROZEN: '冻结',
}

const filters = reactive({
  cycle: '',
  status: '' as '' | Settlement['status'],
})

const loading = ref(false)
const rows = ref<Settlement[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

type SettlementAccount = {
  dealerId: string
  method: 'BANK' | 'ALIPAY'
  accountName: string
  accountNoMasked?: string | null
  bankName?: string
  bankBranch?: string
  contactPhone?: string
  updatedAt?: string | null
}

const acctLoading = ref(false)
const acct = ref<SettlementAccount | null>(null)
const acctDialogOpen = ref(false)
const acctSaving = ref(false)
const acctForm = reactive({
  method: 'BANK' as 'BANK' | 'ALIPAY',
  accountName: '',
  accountNo: '',
  bankName: '',
  bankBranch: '',
  contactPhone: '',
})

async function loadAccount() {
  acctLoading.value = true
  try {
    const data = await apiRequest<SettlementAccount>('/dealer/settlement-account')
    acct.value = data
    acctForm.method = (data.method as any) || 'BANK'
    acctForm.accountName = String(data.accountName || '')
    acctForm.accountNo = ''
    acctForm.bankName = String(data.bankName || '')
    acctForm.bankBranch = String(data.bankBranch || '')
    acctForm.contactPhone = String(data.contactPhone || '')
  } catch (e: any) {
    acct.value = null
  } finally {
    acctLoading.value = false
  }
}

function openEditAccount() {
  acctDialogOpen.value = true
}

async function saveAccount() {
  const method = acctForm.method
  const accountName = String(acctForm.accountName || '').trim()
  const accountNo = String(acctForm.accountNo || '').trim()
  const bankName = String(acctForm.bankName || '').trim()
  if (!accountName) return ElMessage.error('请输入收款户名/实名')
  if (!accountNo) return ElMessage.error('请输入收款账号（仅本次保存使用，不会回显明文）')
  if (method === 'BANK' && !bankName) return ElMessage.error('请输入开户行')

  acctSaving.value = true
  try {
    const data = await apiRequest<SettlementAccount>('/dealer/settlement-account', {
      method: 'PUT',
      query: {
        method,
        accountName,
        accountNo,
        bankName: method === 'BANK' ? bankName : null,
        bankBranch: method === 'BANK' ? (acctForm.bankBranch || null) : null,
        contactPhone: acctForm.contactPhone || null,
      },
    })
    acct.value = data
    acctDialogOpen.value = false
    ElMessage.success('已保存结算账户')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '保存失败')
  } finally {
    acctSaving.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<Settlement>>('/dealer/settlements', {
      query: {
        cycle: filters.cycle || null,
        status: filters.status || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
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

onMounted(async () => {
  await loadAccount()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="结算记录" />

    <el-alert
      title="结算记录按周期汇总：可按结算周期（YYYY-MM）与状态筛选。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card" style="margin-bottom: 12px" :loading="acctLoading">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap">
        <div style="font-weight: 800">结算账户/打款信息</div>
        <el-button size="small" type="primary" @click="openEditAccount">编辑</el-button>
      </div>
      <div style="margin-top: 10px; line-height: 1.7; color: var(--lh-muted)">
        <div v-if="acct">
          <div>方式：{{ acct.method }}</div>
          <div>户名：{{ acct.accountName || '—' }}</div>
          <div>账号：{{ acct.accountNoMasked || '—' }}</div>
          <div v-if="acct.method === 'BANK'">开户行：{{ acct.bankName || '—' }} {{ acct.bankBranch || '' }}</div>
          <div v-if="acct.contactPhone">联系人：{{ acct.contactPhone }}</div>
          <div style="font-size: 12px">updatedAt：{{ acct.updatedAt || '—' }}</div>
        </div>
        <div v-else>暂无结算账户信息，请先点“编辑”补齐（否则平台无法打款）。</div>
      </div>
    </el-card>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="结算周期">
          <el-date-picker
            v-model="filters.cycle"
            type="month"
            value-format="YYYY-MM"
            format="YYYY-MM"
            placeholder="选择月份（YYYY-MM）"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 200px">
            <el-option label="全部" value="" />
            <el-option label="待确认（PENDING_CONFIRM）" value="PENDING_CONFIRM" />
            <el-option label="已结算（SETTLED）" value="SETTLED" />
            <el-option label="已冻结（FROZEN）" value="FROZEN" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.cycle='';filters.status='';page=1;load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        style="margin-top: 12px"
        @retry="load"
      />
      <PageEmptyState
        v-else-if="!loading && rows.length === 0"
        title="暂无结算记录"
        description="可尝试：填写正确的周期（YYYY-MM）或清空状态筛选。"
        style="margin-top: 12px"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="结算单号" width="240" />
        <el-table-column prop="cycle" label="周期" width="160" />
        <el-table-column prop="orderCount" label="订单数" width="120" />
        <el-table-column prop="amount" label="金额" width="140" />
        <el-table-column prop="payoutReferenceLast4" label="打款参考号（后4）" width="200">
          <template #default="scope">
            {{ scope.row.payoutReferenceLast4 ? `****${scope.row.payoutReferenceLast4}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ SETTLEMENT_STATUS_LABEL[scope.row.status as keyof typeof SETTLEMENT_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column prop="settledAt" label="结算时间" width="200" :formatter="fmtBeijingDateTime" />
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

    <el-dialog v-model="acctDialogOpen" title="编辑结算账户" width="640px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>提示</template>
        <div style="line-height: 1.7">
          <div>账号明文仅用于本次保存；页面不会回显明文（只展示脱敏）。</div>
        </div>
      </el-alert>
      <el-form label-width="110px">
        <el-form-item label="打款方式">
          <el-select v-model="acctForm.method" style="width: 220px">
            <el-option label="银行卡（BANK）" value="BANK" />
            <el-option label="支付宝（ALIPAY）" value="ALIPAY" />
          </el-select>
        </el-form-item>
        <el-form-item label="收款户名">
          <el-input v-model="acctForm.accountName" placeholder="例如：张三 / XX公司" />
        </el-form-item>
        <el-form-item label="收款账号">
          <el-input v-model="acctForm.accountNo" placeholder="银行卡号/支付宝账号" />
        </el-form-item>
        <el-form-item v-if="acctForm.method === 'BANK'" label="开户行">
          <el-input v-model="acctForm.bankName" placeholder="例如：中国工商银行" />
        </el-form-item>
        <el-form-item v-if="acctForm.method === 'BANK'" label="支行（可选）">
          <el-input v-model="acctForm.bankBranch" placeholder="例如：XX支行" />
        </el-form-item>
        <el-form-item label="联系人电话（可选）">
          <el-input v-model="acctForm.contactPhone" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="acctDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="acctSaving" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

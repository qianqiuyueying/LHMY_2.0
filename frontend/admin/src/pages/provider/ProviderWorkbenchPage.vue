<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'

const bookingTotal = ref<number | null>(null)
const redemptionTotal = ref<number | null>(null)
const venueReady = ref<boolean | null>(null)
const loading = ref(false)
const route = useRoute()
const router = useRouter()
const agreementOpen = ref(false)
const agreementLoading = ref(false)
const agreementChecked = ref(false)
const agreementCode = ref<'PROVIDER_INFRA_APPLY' | 'PROVIDER_HEALTH_CARD_APPLY'>('PROVIDER_HEALTH_CARD_APPLY')
const agreementTitle = ref('')
const agreementContentHtml = ref('')
const agreementAction = ref<'OPEN_INFRA' | 'SUBMIT_HEALTH_CARD'>('SUBMIT_HEALTH_CARD')

type Onboarding = {
  infraCommerceStatus: 'NOT_OPENED' | 'OPENED'
  healthCardStatus: 'NOT_APPLIED' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
  infraAgreementAcceptedAt?: string | null
  agreementAcceptedAt?: string | null
  submittedAt?: string | null
  reviewedAt?: string | null
  notes?: string | null
}

const onboarding = ref<Onboarding | null>(null)
const onboardingLoading = ref(false)
const infraAccepted = computed(() => !!onboarding.value?.infraAgreementAcceptedAt)
const healthAccepted = computed(() => !!onboarding.value?.agreementAcceptedAt)
const gateHint = computed(() => {
  const gate = String(route.query.gate || '')
  if (gate === 'INFRA') return '未同意《基建联防协议》：当前仅允许“签署协议 / 完善场所信息 / 退出登录”。'
  if (gate === 'HEALTH') return '未同意《健行天下协议》：暂不可使用“健行天下服务”。请先在工作台完成签署。'
  return ''
})

async function loadOnboarding() {
  onboardingLoading.value = true
  try {
    onboarding.value = await apiRequest<Onboarding>('/provider/onboarding')
  } catch {
    onboarding.value = null
  } finally {
    onboardingLoading.value = false
  }
}

async function openInfraCommerce() {
  if (venueReady.value === false) {
    ElMessage.warning('请先完善场所信息（至少填写场所名称与地址）后再开通基建联防')
    router.push('/provider/venues')
    return
  }
  await openAgreementAndDo('OPEN_INFRA')
}

async function submitHealthCard() {
  if (venueReady.value === false) {
    ElMessage.warning('请先完善场所信息（至少填写场所名称与地址）后再提交健行天下开通申请')
    router.push('/provider/venues')
    return
  }
  await openAgreementAndDo('SUBMIT_HEALTH_CARD')
}

async function loadAgreement(code: 'PROVIDER_INFRA_APPLY' | 'PROVIDER_HEALTH_CARD_APPLY') {
  agreementLoading.value = true
  try {
    const data = await apiRequest<{ code: string; title: string; contentHtml: string; version: string }>(`/legal/${code}`)
    agreementTitle.value = String(data.title || '协议')
    agreementContentHtml.value = String(data.contentHtml || '<p>暂无协议内容</p>')
  } catch {
    agreementTitle.value = '协议'
    agreementContentHtml.value = '<p>协议加载失败</p>'
  } finally {
    agreementLoading.value = false
  }
}

async function openAgreementAndDo(action: 'OPEN_INFRA' | 'SUBMIT_HEALTH_CARD') {
  try {
    agreementAction.value = action
    agreementChecked.value = false
    agreementCode.value = action === 'OPEN_INFRA' ? 'PROVIDER_INFRA_APPLY' : 'PROVIDER_HEALTH_CARD_APPLY'
    await loadAgreement(agreementCode.value)
    agreementOpen.value = true
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function confirmAgreementAndSubmit() {
  if (!agreementChecked.value) {
    ElMessage.error('请先勾选并同意协议')
    return
  }
  try {
    if (agreementAction.value === 'OPEN_INFRA') {
      await apiRequest('/provider/onboarding/infra/open', { method: 'POST', body: { agree: true } })
      ElMessage.success('已开通基建联防')
    } else {
      await apiRequest('/provider/onboarding/health-card/submit', { method: 'POST', body: { agree: true } })
      ElMessage.success('已提交审核')
    }
    agreementOpen.value = false
    await loadOnboarding()
    // 通知布局：刷新侧边栏（协议门禁）
    try {
      window.dispatchEvent(new Event('lh-provider-onboarding-updated'))
    } catch {
      // ignore
    }
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '提交失败')
  }
}

async function load() {
  loading.value = true
  try {
    const res = await apiRequest<{ totalBookings: number; totalRedemptions: number }>('/provider/workbench/stats')
    bookingTotal.value = res.totalBookings
    redemptionTotal.value = res.totalRedemptions
    try {
      const v = await apiRequest<{ items: any[]; total: number }>('/provider/venues')
      const total = Number(v.total ?? 0)
      venueReady.value = total > 0
      if (total > 1) {
        // 业务规则：单 Provider=单场所；若历史数据异常，提示但不阻断
        ElMessage.warning('检测到多个场所（异常数据），当前口径按“单场所”展示')
      }
    } catch {
      venueReady.value = null
    }
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadOnboarding()
  await load()
})
</script>

<template>
  <div>
    <PageHeaderBar title="工作台" />

    <el-alert v-if="gateHint" type="warning" show-icon :closable="false" style="margin-top: 12px">
      <template #title>协议门禁</template>
      <div style="line-height: 1.7">
        <div>{{ gateHint }}</div>
        <div v-if="String(route.query.next || '')" style="color: var(--lh-muted); margin-top: 6px">你刚才访问的页面已被拦截。</div>
      </div>
    </el-alert>

    <el-card class="lh-card" style="margin-top: 12px">
      <el-alert type="info" show-icon :closable="false">
        <template #title>你在这里能做什么</template>
        <div style="line-height: 1.7">
          <div>服务提供方（场所）在平台上完成“供给侧管理 + 预约/核销履约”。</div>
          <div style="margin-top: 6px; color: rgba(0, 0, 0, 0.6)">
            常用路径：完善场所信息 → 配置可提供的服务 →（需要预约则配置排期/容量）→ 处理预约 → 核销并留痕。
          </div>
        </div>
      </el-alert>
    </el-card>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="12">
        <el-card class="lh-card" :loading="onboardingLoading">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div style="font-weight: 800">基建联防（电商）开通</div>
            <el-tag size="small" :type="onboarding?.infraCommerceStatus === 'OPENED' ? 'success' : 'info'">
              {{ onboarding?.infraCommerceStatus === 'OPENED' ? '已开通' : '未开通' }}
            </el-tag>
          </div>
          <div style="margin-top: 8px; color: var(--lh-muted); line-height: 1.7">
            开通后可管理“基建联防商品/服务”，并提交平台审核上架。
          </div>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button size="small" type="primary" :disabled="onboarding?.infraCommerceStatus === 'OPENED'" @click="openInfraCommerce">
              一键开通
            </el-button>
            <el-button size="small" @click="router.push('/provider/venues')">去完善场所信息</el-button>
            <el-button v-if="infraAccepted" size="small" @click="router.push('/provider/products')">去管理商品/服务</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="lh-card" :loading="onboardingLoading">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div style="font-weight: 800">健行天下（服务兑换/核销）开通</div>
            <el-tag
              size="small"
              :type="
                onboarding?.healthCardStatus === 'APPROVED'
                  ? 'success'
                  : onboarding?.healthCardStatus === 'SUBMITTED'
                    ? 'warning'
                    : onboarding?.healthCardStatus === 'REJECTED'
                      ? 'danger'
                      : 'info'
              "
            >
              {{
                onboarding?.healthCardStatus === 'APPROVED'
                  ? '已开通'
                  : onboarding?.healthCardStatus === 'SUBMITTED'
                    ? '待审核'
                    : onboarding?.healthCardStatus === 'REJECTED'
                      ? '已驳回'
                      : '未申请'
              }}
            </el-tag>
          </div>
          <div style="margin-top: 8px; color: var(--lh-muted); line-height: 1.7">
            业务说明：消费者在 H5 购买服务包（权益）后，到店兑换服务；场所侧完成预约（可选）与核销扣次数。
          </div>
          <div v-if="onboarding?.healthCardStatus === 'REJECTED' && onboarding?.notes" style="margin-top: 8px; color: #b91c1c">
            驳回原因：{{ onboarding?.notes }}
          </div>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button
              size="small"
              type="primary"
              :disabled="onboarding?.healthCardStatus === 'SUBMITTED' || onboarding?.healthCardStatus === 'APPROVED'"
              @click="submitHealthCard"
            >
              勾选协议并提交审核
            </el-button>
            <el-button size="small" @click="router.push('/provider/venues')">去完善场所信息</el-button>
            <el-button
              v-if="infraAccepted"
              size="small"
              :disabled="onboarding?.healthCardStatus !== 'APPROVED' || !healthAccepted"
              @click="router.push('/provider/services')"
            >
              去配置健行天下服务
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 方案A：未同意 infra 时，工作台仅用于签署协议，不展示其它业务入口 -->
    <el-row v-if="infraAccepted" :gutter="12" style="margin-top: 12px">
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">当前场所（单场所）</div>
          <div style="margin-top: 8px; font-size: 16px; font-weight: 800">
            {{ venueReady === null ? '—' : venueReady ? '已创建' : '未创建' }}
          </div>
          <div style="margin-top: 10px">
            <el-button size="small" type="primary" @click="router.push('/provider/venues')">完善场所信息</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">预约总数</div>
          <div style="margin-top: 8px; font-size: 24px; font-weight: 800">{{ bookingTotal ?? '—' }}</div>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button size="small" type="primary" @click="router.push('/provider/bookings')">处理预约</el-button>
            <el-button size="small" @click="router.push('/provider/schedules')">配置排期/容量</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">核销记录总数</div>
          <div style="margin-top: 8px; font-size: 24px; font-weight: 800">{{ redemptionTotal ?? '—' }}</div>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button size="small" type="primary" @click="router.push('/provider/redeem')">快速核销</el-button>
            <el-button size="small" @click="router.push('/provider/redemptions')">查看核销记录</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div style="margin-top: 12px">
      <el-button :loading="loading || onboardingLoading" @click="loadOnboarding(); load()">刷新</el-button>
    </div>
  </div>

  <el-dialog v-model="agreementOpen" title="协议确认" width="820px">
    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>{{ agreementTitle }}</template>
      <div style="color: var(--lh-muted)">请阅读并勾选同意后继续。</div>
    </el-alert>

    <el-skeleton v-if="agreementLoading" :rows="8" animated />
    <div v-else style="max-height: 420px; overflow: auto; padding: 8px 4px; border: 1px solid var(--lh-border); border-radius: 8px">
      <div v-html="agreementContentHtml"></div>
    </div>

    <div style="margin-top: 12px">
      <el-checkbox v-model="agreementChecked">我已阅读并同意上述协议</el-checkbox>
    </div>

    <template #footer>
      <el-button @click="agreementOpen = false">取消</el-button>
      <el-button type="primary" :disabled="agreementLoading" @click="confirmAgreementAndSubmit">同意并继续</el-button>
    </template>
  </el-dialog>
</template>

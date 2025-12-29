<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Finished, RefreshRight, ShoppingCart, UserFilled } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { apiRequest } from '../../lib/api'
import { getSession } from '../../lib/auth'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

// ECharts 最小初始化（仅本页使用）：减少跨文件跳转，保持行为不变
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const actor = computed(() => getSession())
const router = useRouter()

type DashboardSummary = {
  range: '7d' | '30d'
  today: {
    newMemberCount: number
    servicePackagePaidCount: number
    ecommercePaidCount: number
    refundRequestCount: number
    redemptionSuccessCount: number
  }
  trends: {
    servicePackageOrders: Array<{ date: string; count: number }>
    ecommerceOrders: Array<{ date: string; count: number }>
    redemptions: Array<{ date: string; count: number }>
  }
  todos: {
    refundUnderReviewCount: number
    abnormalOrderCount: number
    enterpriseBindingPendingCount: number
  }
}

const range = ref<'7d' | '30d'>('7d')
const loading = ref(false)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const data = ref<DashboardSummary | null>(null)

const rangeOptions = [
  { label: '近 7 天', value: '7d' },
  { label: '近 30 天', value: '30d' },
] as const

function go(path: string) {
  router.push(path)
}

function safeNum(v: any): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

type TrendPoint = { date: string; count: number }
function normalizeTrend(items?: TrendPoint[] | null): TrendPoint[] {
  return (items || []).map((x) => ({ date: String(x.date || ''), count: safeNum((x as any).count) }))
}

const trends = computed(() => {
  const t = data.value?.trends
  return {
    servicePackageOrders: normalizeTrend(t?.servicePackageOrders),
    ecommerceOrders: normalizeTrend(t?.ecommerceOrders),
    redemptions: normalizeTrend(t?.redemptions),
  }
})

const trendDates = computed(() => {
  const s = new Set<string>()
  for (const p of trends.value.servicePackageOrders) s.add(p.date)
  for (const p of trends.value.ecommerceOrders) s.add(p.date)
  for (const p of trends.value.redemptions) s.add(p.date)
  return Array.from(s).filter(Boolean).sort()
})

function seriesData(points: TrendPoint[]): number[] {
  const m = new Map<string, number>()
  for (const p of points) m.set(p.date, safeNum(p.count))
  return trendDates.value.map((d) => m.get(d) ?? 0)
}

const hasTrendData = computed(() => trendDates.value.length > 0)

const trendOption = computed(() => {
  const dates = trendDates.value
  return {
    color: ['#14B8A6', '#64748B', '#F59E0B'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, left: 0, itemWidth: 10, itemHeight: 10 },
    grid: { left: 12, right: 12, top: 34, bottom: 10, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisTick: { show: false },
      axisLabel: { color: 'rgba(15, 23, 42, 0.6)', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(15, 23, 42, 0.6)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.08)' } },
    },
    series: [
      {
        name: '服务包订单',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.12 },
        data: seriesData(trends.value.servicePackageOrders),
      },
      {
        name: '电商订单',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.08 },
        data: seriesData(trends.value.ecommerceOrders),
      },
      {
        name: '核销',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.1 },
        data: seriesData(trends.value.redemptions),
      },
    ],
  }
})

async function load() {
  loading.value = true
  errorText.value = ''
  errorCode.value = ''
  errorRequestId.value = ''
  try {
    data.value = await apiRequest<DashboardSummary>('/admin/dashboard/summary', { query: { range: range.value } })
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    ElMessage.error(
      `${msg}${errorCode.value ? `（code=${errorCode.value}）` : ''}${errorRequestId.value ? `（requestId=${errorRequestId.value}）` : ''}`,
    )
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="仪表盘">
      <template #extra>
        <el-segmented v-model="range" :options="rangeOptions as any" @change="load" />
      </template>
    </PageHeaderBar>

    <PageErrorState
      v-if="!loading && errorText"
      :message="errorText"
      :code="errorCode"
      :requestId="errorRequestId"
      @retry="load"
    />

    <div v-else style="margin-top: 12px; display: grid; gap: 12px">
      <!-- KPI -->
      <el-row :gutter="12">
        <el-col :span="6">
          <el-card class="lh-card">
            <div class="kpi">
              <div class="kpi__left">
                <div class="kpi__label">新增会员（今日）</div>
                <div class="kpi__value">{{ data?.today.newMemberCount ?? '—' }}</div>
              </div>
              <div class="kpi__icon kpi__icon--primary"><el-icon><UserFilled /></el-icon></div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="lh-card">
            <div class="kpi">
              <div class="kpi__left">
                <div class="kpi__label">服务包支付（今日）</div>
                <div class="kpi__value">{{ data?.today.servicePackagePaidCount ?? '—' }}</div>
              </div>
              <div class="kpi__icon kpi__icon--primary"><el-icon><ShoppingCart /></el-icon></div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="lh-card">
            <div class="kpi">
              <div class="kpi__left">
                <div class="kpi__label">电商支付（今日）</div>
                <div class="kpi__value">{{ data?.today.ecommercePaidCount ?? '—' }}</div>
              </div>
              <div class="kpi__icon kpi__icon--primary"><el-icon><ShoppingCart /></el-icon></div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="lh-card">
            <div class="kpi">
              <div class="kpi__left">
                <div class="kpi__label">核销成功（今日）</div>
                <div class="kpi__value">{{ data?.today.redemptionSuccessCount ?? '—' }}</div>
              </div>
              <div class="kpi__icon kpi__icon--primary"><el-icon><Finished /></el-icon></div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-card class="lh-card">
            <div class="sectionHead">
              <div class="sectionHead__title">待办与预警</div>
              <div class="sectionHead__sub lh-muted">点击可直达处理页面</div>
            </div>

            <div class="todoGrid">
              <div class="todoItem">
                <div class="todoItem__left">
                  <div class="todoItem__label">企业绑定待处理</div>
                  <div class="todoItem__value">{{ data?.todos?.enterpriseBindingPendingCount ?? '—' }}</div>
                </div>
                <el-button type="primary" plain size="small" @click="go('/admin/enterprise-bindings')">去处理</el-button>
              </div>

              <div class="todoItem">
                <div class="todoItem__left">
                  <div class="todoItem__label">退款待审核</div>
                  <div class="todoItem__value">{{ data?.todos?.refundUnderReviewCount ?? '—' }}</div>
                </div>
                <el-button size="small" @click="go('/admin/after-sales')">去查看</el-button>
              </div>

              <div class="todoItem">
                <div class="todoItem__left">
                  <div class="todoItem__label">异常订单</div>
                  <div class="todoItem__value">{{ data?.todos?.abnormalOrderCount ?? '—' }}</div>
                </div>
                <el-button size="small" @click="go('/admin/orders')">去查看</el-button>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card class="lh-card">
            <div class="sectionHead">
              <div class="sectionHead__title">趋势（{{ range === '7d' ? '近 7 天' : '近 30 天' }}）</div>
              <div class="sectionHead__sub lh-muted">折线趋势（ECharts）</div>
            </div>

            <el-empty v-if="!hasTrendData" description="暂无趋势数据" />
            <VChart v-else class="trendChart" :option="trendOption as any" autoresize />
          </el-card>
        </el-col>
      </el-row>

      <el-card class="lh-card">
        <div class="sectionHead">
          <div class="sectionHead__title">当前会话</div>
          <div class="sectionHead__sub lh-muted">用于排障；不作为主要运营信息</div>
        </div>
        <div class="sessionRow">
          <div class="sessionRow__item">
            <div class="sessionRow__k lh-muted">角色</div>
            <div class="sessionRow__v">{{ actor?.actorType || '-' }}</div>
          </div>
          <div class="sessionRow__item">
            <div class="sessionRow__k lh-muted">账号</div>
            <div class="sessionRow__v">{{ actor?.actorUsername || '-' }}</div>
          </div>
          <el-button size="small" :icon="RefreshRight" @click="load">刷新</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.kpi {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 92px;
}

.kpi__left {
  min-width: 0;
}

.kpi__label {
  font-size: 12px;
  color: var(--lh-muted);
}

.kpi__value {
  margin-top: 8px;
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0.2px;
}

.kpi__icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.kpi__icon--primary {
  background: rgba(20, 184, 166, 0.12);
  color: var(--lh-color-primary-active);
}

.sectionHead__title {
  font-size: 14px;
  font-weight: 800;
}

.sectionHead__sub {
  margin-top: 4px;
  font-size: 12px;
}

.todoGrid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.todoItem {
  padding: 10px 12px;
  border: 1px solid var(--lh-border);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: rgba(255, 255, 255, 0.7);
}

.todoItem__label {
  font-size: 12px;
  color: var(--lh-muted);
}

.todoItem__value {
  margin-top: 2px;
  font-size: 18px;
  font-weight: 800;
}

.trendChart {
  height: 320px;
  width: 100%;
  margin-top: 10px;
}

.sessionRow {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.sessionRow__item {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.sessionRow__k {
  font-size: 12px;
}

.sessionRow__v {
  font-size: 13px;
  font-weight: 700;
}
</style>

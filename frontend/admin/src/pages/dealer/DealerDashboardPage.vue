<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'

const router = useRouter()

const loading = ref(false)
const linkTotal = ref<number | null>(null)
const orderTotal = ref<number | null>(null)
const settlementTotal = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    const [links, orders, settlements] = await Promise.all([
      apiRequest<{ items: any[]; page: number; pageSize: number; total: number }>('/dealer-links', { query: { page: 1, pageSize: 1 } }),
      apiRequest<{ items: any[]; page: number; pageSize: number; total: number }>('/dealer/orders', { query: { page: 1, pageSize: 1 } }),
      apiRequest<{ items: any[]; page: number; pageSize: number; total: number }>('/dealer/settlements', { query: { page: 1, pageSize: 1 } }),
    ])
    linkTotal.value = Number(links.total ?? 0)
    orderTotal.value = Number(orders.total ?? 0)
    settlementTotal.value = Number(settlements.total ?? 0)
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="仪表盘" />

    <el-alert
      title="经销商端当前以“链接导流 → 订单归属 → 结算记录”为主流程；本页提供快捷入口与使用说明。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">链接总数</div>
          <div style="margin-top: 8px; font-size: 24px; font-weight: 800">{{ linkTotal ?? '—' }}</div>
          <div style="margin-top: 10px">
            <el-button size="small" type="primary" @click="router.push('/dealer/links')">去管理链接</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">归属订单数</div>
          <div style="margin-top: 8px; font-size: 24px; font-weight: 800">{{ orderTotal ?? '—' }}</div>
          <div style="margin-top: 10px">
            <el-button size="small" type="primary" @click="router.push('/dealer/orders')">去看订单</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card" :loading="loading">
          <div style="font-size: 12px; color: rgba(0, 0, 0, 0.6)">结算记录数</div>
          <div style="margin-top: 8px; font-size: 24px; font-weight: 800">{{ settlementTotal ?? '—' }}</div>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button size="small" type="primary" @click="router.push('/dealer/settlements')">去看结算</el-button>
            <el-button size="small" :loading="loading" @click="load">刷新</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-card class="lh-card">
          <div style="font-weight: 800">链接/参数管理</div>
          <div style="margin-top: 6px; font-size: 12px" class="lh-muted">生成导流链接，复制 URL 投放；可停用链接。</div>
          <el-button style="margin-top: 10px" type="primary" plain @click="router.push('/dealer/links')">进入</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card">
          <div style="font-weight: 800">订单归属</div>
          <div style="margin-top: 6px; font-size: 12px" class="lh-muted">查看归属到本经销商的订单与支付状态。</div>
          <el-button style="margin-top: 10px" type="primary" plain @click="router.push('/dealer/orders')">进入</el-button>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="lh-card">
          <div style="font-weight: 800">结算记录</div>
          <div style="margin-top: 6px; font-size: 12px" class="lh-muted">按周期查看结算单与金额，支持筛选状态。</div>
          <el-button style="margin-top: 10px" type="primary" plain @click="router.push('/dealer/settlements')">进入</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

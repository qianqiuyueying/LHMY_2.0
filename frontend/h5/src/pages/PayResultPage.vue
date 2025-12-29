<template>
  <div class="page">
    <div class="box">
      <div class="status" :class="statusClass">{{ statusText }}</div>
      <div v-if="reason" class="reason">原因：{{ reason }}</div>
      <div class="hint">
        提示：权益发放后，请前往小程序查看并使用。
      </div>
      <div v-if="status === 'success'" class="mini-tip muted">
        如需在微信内打开，可在支付成功后按提示进入小程序查看权益。
      </div>
    </div>

    <div class="actions">
      <van-button v-if="status !== 'success'" type="primary" block @click="retry">重新支付</van-button>
      <van-button v-else type="primary" block :loading="launchLoading" @click="openMiniProgram">打开小程序查看权益</van-button>
      <van-button v-if="status === 'success'" plain block @click="goHome">返回首页</van-button>
      <van-button plain block @click="contact">联系客服</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showDialog, showToast } from 'vant'
import { apiGet } from '../lib/api'
import { pickDealerQuery } from '../lib/dealer'

const route = useRoute()
const router = useRouter()

const status = computed(() => (typeof route.query.status === 'string' ? route.query.status : 'success'))
const reason = computed(() => (typeof route.query.reason === 'string' ? route.query.reason : ''))

const statusText = computed(() => (status.value === 'success' ? '支付成功' : '支付失败'))
const statusClass = computed(() => (status.value === 'success' ? 'ok' : 'fail'))

type MiniProgramLaunchResp = { appid: string; path: string; fallbackText?: string }
const launch = ref<MiniProgramLaunchResp | null>(null)
const launchLoading = ref(false)

function goHome() {
  // 首页是产品介绍页；不携带 dealerLinkId，避免“返回首页”再次跳回购卡页
  router.replace({ path: '/h5' })
}

function retry() {
  const q = pickDealerQuery(route.query as Record<string, unknown>)
  if (!('dealerLinkId' in q) || !String((q as any).dealerLinkId || '').trim()) {
    showToast('请通过经销商投放链接进入购买（门禁已启用）')
    router.replace({ path: '/h5' })
    return
  }
  router.replace({ path: '/h5/buy', query: q })
}

function contact() {
  showToast('请联系平台客服')
}

async function loadLaunch() {
  launchLoading.value = true
  try {
    launch.value = await apiGet<MiniProgramLaunchResp>('/h5/mini-program/launch')
  } catch {
    launch.value = null
  } finally {
    launchLoading.value = false
  }
}

async function openMiniProgram() {
  if (!launch.value) {
    await loadLaunch()
  }

  const l = launch.value
  if (!l?.appid || !l?.path) {
    showToast('小程序入口暂不可用')
    return
  }

  // v1：不引入微信 JS-SDK 签名与拉起组件（规格未定义），仅提供“可执行的兜底提示”
  const msg =
    l.fallbackText ||
    `请在微信中打开小程序（appid: ${l.appid}），进入路径：${l.path} 查看权益。`
  await showDialog({
    title: '打开小程序查看权益',
    message: msg,
    messageAlign: 'left',
  }).catch(() => {
    // ignore
  })
}

onMounted(() => {
  // 预加载一次，避免用户点击等待
  loadLaunch().catch(() => {
    // ignore
  })
})
</script>

<style scoped>
.page {
  padding: 16px;
}
.box {
  padding: 22px 16px;
  border-radius: var(--lh-radius-card);
  background: var(--lh-card-bg);
  box-shadow: var(--lh-shadow-card);
  border: 1px solid var(--lh-border);
  position: relative;
  overflow: hidden;
}
.box::before {
  content: '';
  position: absolute;
  left: -40px;
  top: -60px;
  width: 180px;
  height: 180px;
  border-radius: 999px;
  background: radial-gradient(circle at 40% 30%, rgba(20, 184, 166, 0.22), rgba(20, 184, 166, 0));
}
.status {
  font-size: 22px;
  font-weight: 700;
}
.status.ok {
  color: var(--lh-teal-700);
}
.status.fail {
  color: #dc2626;
}
.reason {
  margin-top: 10px;
  font-size: 13px;
  color: var(--lh-slate-700);
}
.hint {
  margin-top: 14px;
  font-size: 13px;
  color: var(--lh-slate-700);
  line-height: 1.6;
}
.actions {
  margin-top: 16px;
  display: grid;
  gap: 10px;
}
</style>


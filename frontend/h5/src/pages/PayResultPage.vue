<template>
  <div class="page">
    <div class="box">
      <div class="status" :class="statusClass">{{ statusText }}</div>
      <div v-if="reason" class="reason">原因：{{ reason }}</div>
      <div class="hint">
        <template v-if="status === 'success'">
          卡尚未绑定，请前往小程序完成绑定后再使用。你也可以稍后通过经销商找回绑定入口。
        </template>
        <template v-else-if="status === 'issuing'">
          支付已完成，正在发卡中（通常需要几秒）。请稍后刷新页面获取绑定入口。
        </template>
        <template v-else>
          如支付已完成但页面异常关闭，可通过经销商找回。
        </template>
      </div>
    </div>

    <div class="actions">
      <van-button v-if="status === 'fail'" type="primary" block @click="retry">重新支付</van-button>

      <template v-if="status === 'success'">
        <wx-open-launch-weapp
          v-if="isWeixin && jssdkReady && launch?.appid && bindToken"
          :appid="launch.appid"
          :path="mpBindPath"
          @error="onOpenTagError"
        >
          <script type="text/wxtag-template">
            <van-button type="primary" block>去小程序绑定卡</van-button>
          </script>
        </wx-open-launch-weapp>

        <van-button v-else type="primary" block :loading="launchLoading" @click="openMiniProgramFallback">
          去小程序绑定卡
        </van-button>
      </template>

      <van-button v-if="status === 'issuing'" type="primary" block :loading="bindLoading" @click="loadBind">刷新绑定入口</van-button>
      <van-button plain block @click="goHome">返回首页</van-button>
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
import { initWechatJssdkForOpenTag, isWeixinBrowser } from '../lib/wechatJssdk'

const route = useRoute()
const router = useRouter()

const orderId = computed(() => (typeof route.query.orderId === 'string' ? route.query.orderId : ''))
const reason = computed(() => (typeof route.query.reason === 'string' ? route.query.reason : ''))

type Status = 'issuing' | 'success' | 'fail'
const status = ref<Status>('issuing')

const statusText = computed(() => {
  if (status.value === 'success') return '支付成功'
  if (status.value === 'issuing') return '处理中'
  return '支付失败'
})
const statusClass = computed(() => (status.value === 'success' ? 'ok' : status.value === 'issuing' ? 'muted' : 'fail'))

type MiniProgramLaunchResp = { appid: string; path: string; fallbackText?: string }
const launch = ref<MiniProgramLaunchResp | null>(null)
const launchLoading = ref(false)

type H5OrderBindTokenResp = {
  orderId: string
  cardId: string
  cardStatus: 'UNBOUND' | 'BOUND' | null
  bindToken: string | null
  expiresAt: string | null
}
const bind = ref<H5OrderBindTokenResp | null>(null)
const bindLoading = ref(false)
const bindToken = computed(() => bind.value?.bindToken || '')

const isWeixin = computed(() => isWeixinBrowser())
const mpBindPath = computed(() => `pages/card/bind-by-token?token=${encodeURIComponent(bindToken.value)}`)
const jssdkReady = ref(false)

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

async function loadBind() {
  if (!orderId.value) {
    status.value = 'fail'
    return
  }
  bindLoading.value = true
  try {
    bind.value = await apiGet<H5OrderBindTokenResp>(`/h5/orders/${encodeURIComponent(orderId.value)}/bind-token`)
    if (bind.value?.cardStatus === 'BOUND') {
      // 已绑定：按成功态展示，但不再提供 token
      status.value = 'success'
      return
    }
    status.value = bind.value?.bindToken ? 'success' : 'issuing'
  } catch {
    status.value = 'issuing'
  } finally {
    bindLoading.value = false
  }
}

function onOpenTagError() {
  showToast('拉起小程序失败，请使用下方兜底方式')
}

async function openMiniProgramFallback() {
  if (!launch.value) await loadLaunch()
  const l = launch.value
  if (!l?.appid || !bindToken.value) {
    showToast('绑定入口暂不可用')
    return
  }
  const msg =
    l.fallbackText ||
    `请在微信中打开小程序（appid: ${l.appid}），进入路径：pages/card/bind-by-token?token=${bindToken.value} 绑定卡。`
  await showDialog({ title: '去小程序绑定卡', message: msg, messageAlign: 'left' }).catch(() => {})
}

onMounted(() => {
  // 预加载
  loadLaunch().catch(() => {})
  loadBind().catch(() => {})

  if (isWeixin.value) {
    initWechatJssdkForOpenTag()
      .then(() => {
        jssdkReady.value = true
      })
      .catch((e) => {
        jssdkReady.value = false
        // 不阻断流程：仍可用兜底弹窗提示用户手动打开
        console.warn('wechat jssdk init failed', e)
      })
  }
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
.status.muted {
  color: var(--lh-slate-700);
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


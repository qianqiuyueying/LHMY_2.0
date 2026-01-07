<template>
  <div class="page">
    <div class="header">
      <div class="logo">LHMY</div>
      <div class="title">健行天下高端服务卡</div>
    </div>

    <van-notice-bar v-if="dealerTip" :text="dealerTip" wrapable />
    <van-notice-bar v-if="gateTip" :text="gateTip" wrapable />

    <div class="section">
      <div class="section-title">产品介绍</div>
      <div class="text">
        「健行天下」是健康服务权益卡，覆盖多类健康服务。购买后权益将发放到小程序端，用于查看与使用服务。
      </div>
      <div class="text" style="margin-top: 8px">
        购买说明：本 H5 仅作为经销商投放购买入口，需通过经销商投放链接进入（携带 dealerLinkId）。
      </div>
      <div class="kv" style="margin-top: 10px">
        <div class="kv-row">
          <div class="k">购买入口</div>
          <div class="v">经销商投放链接</div>
        </div>
        <div class="kv-row">
          <div class="k">权益使用</div>
          <div class="v">小程序端</div>
        </div>
      </div>

      <div class="services" style="margin-top: 12px">
        <div class="services-title">你将获得什么</div>
        <van-cell title="服务权益" value="按卡片配置发放次数" />
        <van-cell title="使用方式" value="到店/预约后核销" />
        <van-cell title="购买保障" value="下单全程幂等与门禁校验" />
      </div>
    </div>

    <div v-if="cards.length" class="section">
      <div class="section-title">该经销商可售卡</div>
      <van-cell
        v-for="c in cards"
        :key="c.dealerLinkId"
        :title="c.sellableCard.name"
        :label="buildCardLabel(c)"
        is-link
        @click="router.push({ path: '/h5/buy', query: { dealerLinkId: dealerLinkId, sellableCardId: c.sellableCard.id } })"
      />
    </div>

    <div v-if="sellableCard" class="section">
      <div class="section-title">高端服务卡介绍</div>
      <div class="kv">
        <div class="kv-row">
          <div class="k">区域级别</div>
          <div class="v">{{ spLoading ? '加载中…' : sellableCard?.regionLevel ?? sp?.regionLevel ?? '--' }}</div>
        </div>
        <div class="kv-row">
          <div class="k">等级</div>
          <div class="v">{{ spLoading ? '加载中…' : sp?.tier ?? '--' }}</div>
        </div>
      </div>

      <div class="services">
        <div class="services-title">包含服务类别 × 次数</div>
        <van-skeleton v-if="spLoading" :row="3" />
        <div v-else-if="sp?.services?.length">
          <van-cell v-for="s in sp.services" :key="s.serviceType" :title="serviceTypeLabel(s.serviceType)" :value="`×${s.totalCount}`" />
        </div>
        <van-empty v-else :description="spLoadFailed ? '服务包信息加载失败' : '暂无服务包配置'">
          <template #bottom>
            <van-button v-if="spLoadFailed" size="small" type="primary" @click="loadServicePackage">重试</van-button>
          </template>
        </van-empty>
      </div>
    </div>

    <div v-if="sellableCard" class="section">
      <div class="section-title">价格</div>
      <div class="price-row">
        <div class="price">售价：¥{{ priceLoading ? '加载中…' : priceText }}</div>
        <div class="desc">购买后权益在小程序使用</div>
        <div v-if="priceLoadFailed" class="retry-row">
          <van-button size="small" plain type="primary" @click="loadPrice">重试加载价格</van-button>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">常见问题/用户须知/条款</div>
      <van-skeleton v-if="faqLoading" :row="4" />
      <template v-else>
        <van-empty v-if="faqLoadFailed" description="内容加载失败">
          <template #bottom>
            <van-button size="small" type="primary" @click="loadFaqTerms">重试</van-button>
          </template>
        </van-empty>
        <template v-else>
          <div v-if="faqItems.length" class="faq">
            <van-collapse>
              <van-collapse-item v-for="(it, idx) in faqItems" :key="idx" :title="it.q">
                <div class="text">{{ it.a }}</div>
              </van-collapse-item>
            </van-collapse>
          </div>
          <div v-if="termsText" class="terms text">{{ termsText }}</div>
          <div v-if="!faqItems.length && !termsText" class="text">购买成功后权益在小程序端可见并使用。</div>
        </template>
      </template>
    </div>

    <div class="cta">
      <div class="cta-row">
        <van-button v-if="dealerLinkId" type="primary" class="cta-btn" disabled>请选择下方卡片购买</van-button>
        <van-button
          v-else
          type="primary"
          class="cta-btn"
          disabled
        >
          请通过经销商链接购买
        </van-button>
        <van-button plain class="cta-btn" @click="consult">咨询</van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, apiGet } from '../lib/api'
import { parseDealerLinkId, parseDealerParams } from '../lib/dealer'
import { showToast, showDialog } from 'vant'

type ServicePackageDetail = {
  id: string
  name: string
  regionLevel: string
  tier: string
  description?: string | null
  services: Array<{ serviceType: string; totalCount: number }>
}

const route = useRoute()
const router = useRouter()

const dealerTip = ref<string>('')
const dealerLinkId = ref<string>('')
const gateTip = ref<string>('')

type H5DealerLinkResp = {
  dealer: { id: string; name: string } | null
  sellableCard: SellableCard | null
  link: { id: string; status: string; validFrom?: string | null; validUntil?: string | null } | null
}

type H5DealerCardsResp = {
  items: Array<{
    dealerLinkId: string
    sellableCard: SellableCard & { services?: Array<{ serviceType: string; totalCount: number }> }
  }>
}

const cards = ref<H5DealerCardsResp['items']>([])
const sp = ref<ServicePackageDetail | null>(null)
const priceText = ref<string>('--')
const spLoading = ref(false)
const spLoadFailed = ref(false)
const priceLoading = ref(false)
const priceLoadFailed = ref(false)

type FaqTermsResp = {
  version: string
  items: Array<{ q: string; a: string }>
  termsText: string
}

const faqLoading = ref(false)
const faqLoadFailed = ref(false)
const faqItems = ref<Array<{ q: string; a: string }>>([])
const termsText = ref('')

type SellableCard = {
  id: string
  name: string
  servicePackageTemplateId: string
  regionLevel: 'CITY' | 'PROVINCE' | 'COUNTRY'
  priceOriginal: number
}
const sellableCard = ref<SellableCard | null>(null)

type ServiceCategoryItem = { code: string; displayName: string }
const serviceCategoryNameByCode = ref(new Map<string, string>())

function serviceTypeLabel(code: string): string {
  const k = String(code || '').trim().toUpperCase()
  if (!k) return ''
  return serviceCategoryNameByCode.value.get(k) || k
}

async function loadServiceCategories() {
  try {
    const data = await apiGet<{ items: ServiceCategoryItem[]; total: number }>('/service-categories')
    const m = new Map<string, string>()
    for (const x of data.items || []) {
      const c = String((x as any).code || '').trim().toUpperCase()
      const n = String((x as any).displayName || '').trim()
      if (c && n) m.set(c, n)
    }
    serviceCategoryNameByCode.value = m
  } catch {
    serviceCategoryNameByCode.value = new Map()
  }
}

async function loadDealerContext() {
  const id = parseDealerLinkId(route.query as Record<string, unknown>)
  dealerLinkId.value = id || ''
  cards.value = []

  if (!id) {
    dealerTip.value = ''
    sellableCard.value = null
    return
  }

  try {
    const data = await apiGet<H5DealerLinkResp>(`/h5/dealer-links/${id}`)
    dealerTip.value = data?.dealer?.name ? `经销商：${data.dealer.name}` : '经销商链接已校验'
    sellableCard.value = data.sellableCard

    // vNext：支持 dealerLinkId + sellableCardId 直达购卡页
    const scid = String((route.query as any)?.sellableCardId ?? '').trim()
    if (scid) {
      router.replace({ path: '/h5/buy', query: { dealerLinkId: id, sellableCardId: scid } })
      return
    }

    const list = await apiGet<H5DealerCardsResp>(`/h5/dealer-links/${id}/cards`)
    cards.value = list.items || []
  } catch (e: unknown) {
    sellableCard.value = null
    cards.value = []
    if (e instanceof ApiError) dealerTip.value = `经销商链接不可用（${e.code}）`
    else dealerTip.value = '经销商链接不可用'
  }
}

async function loadServicePackage() {
  const tid = sellableCard.value?.servicePackageTemplateId
  if (!tid) {
    sp.value = null
    return
  }
  spLoading.value = true
  spLoadFailed.value = false
  try {
    sp.value = await apiGet<ServicePackageDetail>(`/service-packages/${tid}`)
  } catch {
    sp.value = null
    spLoadFailed.value = true
    showToast('服务包信息加载失败')
  } finally {
    spLoading.value = false
  }
}

async function loadPrice() {
  priceLoading.value = true
  priceLoadFailed.value = false
  try {
    const v = sellableCard.value?.priceOriginal
    priceText.value = typeof v === 'number' ? v.toFixed(2) : '--'
  } catch {
    priceText.value = '--'
    priceLoadFailed.value = true
    showToast('价格加载失败')
  } finally {
    priceLoading.value = false
  }
}

async function loadFaqTerms() {
  faqLoading.value = true
  faqLoadFailed.value = false
  try {
    const data = await apiGet<FaqTermsResp>('/h5/landing/faq-terms')
    faqItems.value = data.items || []
    termsText.value = data.termsText || ''
  } catch {
    faqItems.value = []
    termsText.value = ''
    faqLoadFailed.value = true
  } finally {
    faqLoading.value = false
  }
}

function buildCardLabel(x: H5DealerCardsResp['items'][number]): string {
  const basic = `区域：${x.sellableCard.regionLevel}｜售价：¥${Number(x.sellableCard.priceOriginal ?? 0).toFixed(2)}`
  const svcs = (x.sellableCard as any)?.services as Array<{ serviceType: string; totalCount: number }> | undefined
  if (!svcs?.length) return basic
  const tail = svcs.slice(0, 3).map((s) => `${serviceTypeLabel(s.serviceType)}×${s.totalCount}`).join('、')
  const more = svcs.length > 3 ? '…' : ''
  return `${basic}｜服务：${tail}${more}`
}

function consult() {
  showDialog({
    title: '咨询',
    message: '请联系平台客服',
  })
}

onMounted(() => {
  // 兼容提醒：旧链接参数已废弃（开发阶段无存量迁移需求）
  const legacy = parseDealerParams(route.query as Record<string, unknown>)
  if (legacy && !parseDealerLinkId(route.query as Record<string, unknown>)) {
    dealerTip.value = '链接格式已升级，请从经销商后台重新生成投放链接'
  }

  // 门禁：无 dealerLinkId 时禁止购买入口（防止记账/购买错误）
  if (!parseDealerLinkId(route.query as Record<string, unknown>)) {
    gateTip.value = '请通过经销商投放链接购买（当前页面仅为产品介绍页）'
  }

  loadDealerContext().finally(() => {
    loadServicePackage()
    loadPrice()
  })
  loadFaqTerms()

  // 服务大类字典：用于把 serviceType(code) 渲染成中文名称
  loadServiceCategories()
})
</script>

<style scoped>
.page {
  padding-bottom: 86px;
}
.header {
  margin: 16px 16px 0;
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.22) 0%, rgba(20, 184, 166, 0.08) 35%, rgba(255, 255, 255, 0.92) 100%);
  border: 1px solid rgba(2, 6, 23, 0.08);
  box-shadow: 0 10px 30px rgba(2, 6, 23, 0.05);
  color: var(--lh-slate-900);
  position: relative;
  overflow: hidden;
}
.header::after {
  content: '';
  position: absolute;
  right: -40px;
  top: -40px;
  width: 160px;
  height: 160px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, rgba(20, 184, 166, 0.35), rgba(20, 184, 166, 0));
}
.logo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--lh-teal-700);
}
.title {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 700;
}
.section {
  margin: 12px 16px 0;
  padding: 16px;
  border-radius: var(--lh-radius-card);
  background: var(--lh-card-bg);
  box-shadow: var(--lh-shadow-card);
  border: 1px solid var(--lh-border);
}
.section-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 700;
}
.kv {
  display: grid;
  gap: 8px;
}
.kv-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.k {
  color: var(--lh-slate-500);
}
.v {
  color: var(--lh-slate-900);
  font-weight: 700;
}
.services-title {
  margin: 12px 0 8px;
  font-size: 14px;
  font-weight: 700;
}
.text {
  font-size: 13px;
  color: var(--lh-slate-700);
  line-height: 1.6;
}
.terms {
  margin-top: 10px;
}
.cta {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.92);
  border-top: 1px solid var(--lh-border-soft);
  box-shadow: var(--lh-shadow-float);
}
.cta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.cta-btn {
  width: 100%;
  white-space: nowrap;
}
.price-row {
  display: grid;
  gap: 6px;
}
.price {
  font-size: 18px;
  font-weight: 700;
  color: var(--lh-slate-900);
}
.desc {
  font-size: 12px;
  color: var(--lh-slate-500);
}
.retry-row {
  margin-top: 10px;
}

/* 强调“价格/关键行动”色（克制使用） */
.price :deep(strong) {
  color: var(--lh-amber-500);
}
</style>


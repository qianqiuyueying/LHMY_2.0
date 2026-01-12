<template>
  <div class="page">
    <van-nav-bar title="确认购买" left-text="返回" left-arrow @click-left="goBack" />

    <van-notice-bar v-if="dealerTip" :text="dealerTip" wrapable />

    <van-empty
      v-if="gateBlocked"
      description="请通过经销商投放链接进入购买（门禁已启用）"
      style="margin-top: 24px"
    >
      <template #bottom>
        <van-button type="primary" @click="router.replace({ path: '/h5' })">返回产品介绍页</van-button>
      </template>
    </van-empty>

    <template v-else>
    <div class="section">
      <van-cell title="商品" :value="productTitle" />
      <van-cell
        v-if="sellableCard"
        title="售价"
        :value="`¥${Number(sellableCard.priceOriginal ?? 0).toFixed(2)}`"
      />
      <van-cell title="数量">
        <template #value>
          <van-stepper v-model="quantity" min="1" max="1" disabled />
        </template>
      </van-cell>
      <template v-if="requiredRegionLevel">
        <van-cell
          v-if="requiredRegionLevel === 'COUNTRY'"
          title="购买区域"
          value="全国（默认）"
        />
        <van-cell
          v-else
          title="购买区域"
          is-link
          :value="selectedRegionLabel"
          @click="regionSelectOpen = true"
        />
        <div v-if="requiredRegionLevel !== 'COUNTRY' && !regionsLoading && !hasRegionOptions" style="padding: 8px 16px; color: rgba(0,0,0,.6); font-size: 12px">
          当前没有可选区域配置（需要在后端 SystemConfig.key=REGION_CITIES 配置并发布对应 {{ requiredRegionLevel }}:* 编码）。
        </div>
      </template>
    </div>

    <div class="section">
      <van-cell title="包含服务类别 × 次数" />
      <van-skeleton v-if="spLoading" :row="3" style="padding: 0 16px 12px" />
      <template v-else-if="sp?.services?.length">
        <van-cell v-for="s in sp.services" :key="s.serviceType" :title="serviceTypeLabel(s.serviceType)" :value="`×${s.totalCount}`" />
      </template>
      <van-empty v-else :description="spLoadFailed ? '服务内容加载失败' : '暂无服务配置'">
        <template #bottom>
          <van-button v-if="spLoadFailed" size="small" type="primary" @click="loadServicePackage">重试</van-button>
        </template>
      </van-empty>
    </div>

    <div class="section">
      <van-cell title="提示" value="本页面不登录、不保存购买记录；支付成功后请前往小程序绑定卡。" />
    </div>

    <div class="section">
      <van-field
        v-model="buyerPhone"
        label="手机号"
        placeholder="用于订单联系（不用于登录）"
        type="tel"
        maxlength="20"
        clearable
      />
      <div style="padding: 0 16px 8px; color: rgba(0,0,0,.6); font-size: 12px">
        我们仅在后台以脱敏形式展示手机号，用于订单联系与售后跟进。
      </div>
    </div>

    <div class="section">
      <van-checkbox v-model="agree">
        我已阅读并同意
        <span class="link" @click.stop="openAgreement">《服务协议》</span>
      </van-checkbox>
    </div>

    <div class="cta">
      <van-button type="primary" block class="lh-cta-primary" :loading="submitting" :disabled="submitting" @click="submit">提交订单并支付</van-button>
    </div>

    <van-popup v-model:show="agreementOpen" position="bottom" round style="height: 80vh">
      <div class="agreement">
        <div class="agreement-header">
          <div class="agreement-title">{{ agreementTitle || '服务协议' }}</div>
          <van-button size="small" plain type="primary" @click="agreementOpen = false">关闭</van-button>
        </div>
        <div class="agreement-body">
          <div v-if="agreementHtml" class="agreement-html" v-html="agreementHtml"></div>
          <div v-else class="agreement-empty">暂无协议内容</div>
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="regionSelectOpen" position="bottom" round style="height: 80vh">
      <div class="region-popup">
        <div class="region-header">
          <div class="region-title">选择购买区域</div>
          <van-button size="small" plain type="primary" @click="regionSelectOpen = false">关闭</van-button>
        </div>

        <div v-if="requiredRegionLevel === 'PROVINCE'" class="region-body">
          <van-search v-model="provinceSearch" placeholder="搜索省份" />
          <div class="region-list">
            <van-cell
              v-for="p in filteredProvinces"
              :key="p.value"
              :title="p.text"
              is-link
              @click="selectRegion(p.value)"
            />
          </div>
        </div>

        <div v-else-if="requiredRegionLevel === 'CITY'" class="region-body">
          <van-tabs v-model:active="cityMode" shrink>
            <van-tab title="省市选择" name="CASCADE">
              <div class="region-cascade">
                <div class="region-col">
                  <div class="region-col-title">省</div>
                  <div class="region-scroll">
                    <van-cell
                      v-for="p in provinces"
                      :key="p.value"
                      :title="p.text"
                      :class="p.value === selectedProvinceScope ? 'active' : ''"
                      @click="selectedProvinceScope = p.value"
                    />
                  </div>
                </div>
                <div class="region-col">
                  <div class="region-col-title">市</div>
                  <div class="region-scroll">
                    <van-cell
                      v-for="c in cascadeCities"
                      :key="c.value"
                      :title="c.text"
                      is-link
                      @click="selectRegion(c.value)"
                    />
                  </div>
                </div>
              </div>
            </van-tab>
            <van-tab title="搜索" name="SEARCH">
              <van-search v-model="citySearch" placeholder="搜索城市" />
              <div class="region-list">
                <van-cell
                  v-for="c in filteredCities"
                  :key="c.value"
                  :title="c.text"
                  is-link
                  @click="selectRegion(c.value)"
                />
              </div>
            </van-tab>
          </van-tabs>
        </div>

        <div v-else class="region-body">
          <div style="padding: 12px 16px; color: rgba(0,0,0,.6); font-size: 13px">当前卡片无需选择区域。</div>
        </div>
      </div>
    </van-popup>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { ApiError, apiGet, apiPost, newIdempotencyKey, presentErrorMessage } from '../lib/api'
import { parseDealerLinkId, parseDealerParams } from '../lib/dealer'

const route = useRoute()
const router = useRouter()

const productTitle = ref('高端服务卡')
const quantity = ref(1)

const agree = ref(false)
const buyerPhone = ref('')

const dealerTip = ref('')
const dealerLinkId = ref('')
const gateBlocked = computed(() => !dealerLinkId.value || !sellableCard.value)

type SellableCard = {
  id: string
  name: string
  servicePackageTemplateId: string
  regionLevel: 'CITY' | 'PROVINCE' | 'COUNTRY'
  priceOriginal: number
}

const sellableCard = ref<SellableCard | null>(null)

const submitting = ref(false)
const agreementLoading = ref(false)
const agreementOpen = ref(false)
const agreementTitle = ref('')
const agreementHtml = ref('')

type H5DealerLinkResp = {
  dealer: { id: string; name: string } | null
  sellableCard: SellableCard | null
  link: { id: string; status: string; validFrom?: string | null; validUntil?: string | null } | null
}

type RegionItem = { code: string; name: string; sort: number }
type RegionsResp = { items: RegionItem[]; defaultCode?: string | null; version: string }

const regionsLoading = ref(false)
const regionItems = ref<RegionItem[]>([])
const selectedRegionScope = ref('') // 例如 CITY:110100 / PROVINCE:110000
const regionSelectOpen = ref(false)
const provinceSearch = ref('')
const citySearch = ref('')
const cityMode = ref<'CASCADE' | 'SEARCH'>('CASCADE')
const selectedProvinceScope = ref('')

function parseScope(scope: string): { level: 'CITY' | 'PROVINCE' | 'COUNTRY'; code: string } | null {
  const s = String(scope || '').trim()
  if (!s || !s.includes(':')) return null
  const [lv, code] = s.split(':', 2)
  const level = String(lv || '').toUpperCase()
  const c = String(code || '').trim()
  if (!['CITY', 'PROVINCE', 'COUNTRY'].includes(level)) return null
  if (!c) return null
  return { level: level as any, code: c }
}

const requiredRegionLevel = ref<'CITY' | 'PROVINCE' | 'COUNTRY' | ''>('')

type ServiceCategoryItem = { code: string; displayName: string }
const serviceCategoriesLoading = ref(false)
const serviceCategoryNameByCode = ref(new Map<string, string>())

function serviceTypeLabel(code: string): string {
  const k = String(code || '').trim().toUpperCase()
  if (!k) return ''
  return serviceCategoryNameByCode.value.get(k) || k
}

async function loadServiceCategories() {
  // 读侧仅返回 ENABLED；用于把 serviceType（code）渲染为中文 displayName
  serviceCategoriesLoading.value = true
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
  } finally {
    serviceCategoriesLoading.value = false
  }
}

async function loadRegions() {
  regionsLoading.value = true
  try {
    const data = await apiGet<RegionsResp>('/regions/cities')
    regionItems.value = (data.items || []).slice()
  } catch {
    regionItems.value = []
  } finally {
    regionsLoading.value = false
  }
}

type RegionOpt = { text: string; value: string }

const provinces = computed<RegionOpt[]>(() =>
  (regionItems.value || [])
    .filter((x) => String(x.code || '').startsWith('PROVINCE:'))
    .map((x) => ({ text: String(x.name || x.code), value: String(x.code || '') })),
)

const cities = computed<RegionOpt[]>(() =>
  (regionItems.value || [])
    .filter((x) => String(x.code || '').startsWith('CITY:'))
    .map((x) => ({ text: String(x.name || x.code), value: String(x.code || '') })),
)

const filteredProvinces = computed<RegionOpt[]>(() => {
  const kw = String(provinceSearch.value || '').trim()
  if (!kw) return provinces.value
  return provinces.value.filter((x) => x.text.includes(kw) || x.value.includes(kw))
})

const filteredCities = computed<RegionOpt[]>(() => {
  const kw = String(citySearch.value || '').trim()
  if (!kw) return cities.value
  return cities.value.filter((x) => x.text.includes(kw) || x.value.includes(kw))
})

function _digits(scope: string): string {
  const s = String(scope || '')
  const idx = s.indexOf(':')
  const raw = (idx >= 0 ? s.slice(idx + 1) : s).trim()
  return raw
}

function deriveProvinceScope(cityScope: string): string | null {
  const d = _digits(cityScope)
  if (!/^\d{6}$/.test(d)) return null
  return `PROVINCE:${d.slice(0, 2)}0000`
}

const cascadeCities = computed<RegionOpt[]>(() => {
  const ps = String(selectedProvinceScope.value || '').trim()
  if (!ps) return []
  const want = _digits(ps)
  if (!want || !/^\d{6}$/.test(want)) return []
  return cities.value.filter((c) => {
    const p = deriveProvinceScope(c.value)
    return p === ps
  })
})

const hasRegionOptions = computed(() => {
  const lv = requiredRegionLevel.value
  if (lv === 'PROVINCE') return provinces.value.length > 0
  if (lv === 'CITY') return provinces.value.length > 0 && cities.value.length > 0
  return true
})

const selectedRegionLabel = computed(() => {
  const v = String(selectedRegionScope.value || '').trim()
  if (!v) return '请选择'
  const hit = (regionItems.value || []).find((x) => String(x.code || '') === v)
  return hit?.name ? String(hit.name) : v
})

function selectRegion(scope: string) {
  selectedRegionScope.value = String(scope || '').trim()
  regionSelectOpen.value = false
}

type ServiceAgreementResp = { version: string; title: string; contentText?: string; contentHtml?: string }

async function loadDealerContext() {
  const id = parseDealerLinkId(route.query as Record<string, unknown>)
  dealerLinkId.value = id || ''
  if (!id) {
    dealerTip.value = ''
    sellableCard.value = null
    requiredRegionLevel.value = ''
    productTitle.value = '高端服务卡'
    // 最高门禁：不展示购买 UI；由模板 gateBlocked 统一阻断
    return
  }
  try {
    const data = await apiGet<H5DealerLinkResp>(`/h5/dealer-links/${id}`)
    dealerTip.value = data?.dealer?.name ? `经销商：${data.dealer.name}` : '经销商链接已校验'

    // 口径调整：购卡页需要 dealerLinkId + sellableCardId（从 query 取），并由后端校验授权
    const scid = String((route.query as any)?.sellableCardId ?? '').trim()
    if (!scid) {
      sellableCard.value = null
      requiredRegionLevel.value = ''
      productTitle.value = '高端服务卡'
      return
    }

    const cardData = await apiGet<{ sellableCard: SellableCard }>(`/h5/dealer-links/${id}/cards/${scid}`)
    sellableCard.value = cardData.sellableCard
    requiredRegionLevel.value = sellableCard.value?.regionLevel || ''
    productTitle.value = sellableCard.value?.name || '高端服务卡'

    // 门禁：/h5/buy 必须是“指定卡链接”，否则回到首页让用户先选卡
    // 最高门禁：/h5/buy 必须是“指定卡链接”，否则阻断购买 UI（不做自动跳转，避免循环/误导）

    // 省/市卡时若当前选中维度不匹配则清空
    if (requiredRegionLevel.value === 'PROVINCE' && selectedRegionScope.value && !selectedRegionScope.value.startsWith('PROVINCE:')) selectedRegionScope.value = ''
    if (requiredRegionLevel.value === 'CITY' && selectedRegionScope.value && !selectedRegionScope.value.startsWith('CITY:')) selectedRegionScope.value = ''
    if (requiredRegionLevel.value === 'COUNTRY') selectedRegionScope.value = 'COUNTRY:CN'

    await loadServicePackage()
  } catch (e: unknown) {
    sellableCard.value = null
    requiredRegionLevel.value = ''
    productTitle.value = '高端服务卡'
    if (e instanceof ApiError) dealerTip.value = `经销商链接不可用（${e.code}）`
    else dealerTip.value = '经销商链接不可用'
    // 最高门禁：链接不可用时阻断购买 UI；由模板 gateBlocked 统一处理
  }
}

type ServicePackageDetail = {
  id: string
  name: string
  regionLevel: string
  tier: string
  description?: string | null
  services: Array<{ serviceType: string; totalCount: number }>
}

const sp = ref<ServicePackageDetail | null>(null)
const spLoading = ref(false)
const spLoadFailed = ref(false)

async function loadServicePackage() {
  const tid = sellableCard.value?.servicePackageTemplateId
  if (!tid) {
    sp.value = null
    spLoadFailed.value = false
    return
  }
  spLoading.value = true
  spLoadFailed.value = false
  try {
    sp.value = await apiGet<ServicePackageDetail>(`/service-packages/${tid}`)
  } catch {
    sp.value = null
    spLoadFailed.value = true
  } finally {
    spLoading.value = false
  }
}

async function openAgreement() {
  agreementLoading.value = true
  try {
    const a = await apiGet<ServiceAgreementResp>('/h5/legal/service-agreement')
    // 规格：后端返回 contentHtml；这里按 HTML 渲染（避免把标签当作纯文本展示）
    agreementTitle.value = String(a.title || '服务协议')
    agreementHtml.value = String(a.contentHtml || a.contentText || '')
    agreementOpen.value = true
  } catch (e: any) {
    showToast(presentErrorMessage(e))
  } finally {
    agreementLoading.value = false
  }
}

async function submit() {
  // 最高门禁：任何情况下只要没拿到 dealerLinkId + 指定卡，就不允许提交
  if (gateBlocked.value) {
    showToast('请通过经销商投放链接进入购买（门禁已启用）')
    return
  }
  if (!agree.value) {
    showToast('请先同意服务协议')
    return
  }

  const rawPhone = String(buyerPhone.value || '').trim()
  const phoneDigits = rawPhone.replace(/[^\d]/g, '')
  if (phoneDigits.length !== 11) {
    showToast('请填写正确的手机号（11位）')
    return
  }

  const resolved = sellableCard.value
  const templateId = resolved?.servicePackageTemplateId || ''
  let regionScope = ''

  if (!dealerLinkId.value) return showToast('缺少 dealerLinkId（请使用经销商投放链接打开）')
  if (!resolved) return showToast('可售卡不可用或已停用，无法下单')
  if (!templateId) return showToast('可售卡配置不完整（缺少模板ID），无法下单')

  // v2：若走 sellableCardId，则必须按 regionLevel 选择具体区域（COUNTRY 自动默认）
  const lv = resolved.regionLevel
  if (lv === 'COUNTRY') regionScope = 'COUNTRY:CN'
  else regionScope = selectedRegionScope.value || ''

  if (lv === 'PROVINCE' && !regionScope.startsWith('PROVINCE:')) return showToast('省卡必须选择到省')
  if (lv === 'CITY' && !regionScope.startsWith('CITY:')) return showToast('市卡必须选择到市')

  const parsed = parseScope(regionScope)
  if (!parsed) {
    return showToast('请先选择购买区域')
  }
  const regionLevel = parsed.level
  const regionCode = parsed.code

  submitting.value = true
  try {
    const idem1 = newIdempotencyKey()
    const order = await apiPost<any>(
      '/orders',
      {
        orderType: 'SERVICE_PACKAGE',
        buyerPhone: phoneDigits,
        items: [
          {
            itemType: 'SERVICE_PACKAGE',
            // v2.1：itemId 即 sellableCardId（订单明细业务对象ID）
            itemId: resolved.id,
            quantity: 1,
            servicePackageTemplateId: templateId,
            regionScope,
            regionLevel,
            regionCode,
          },
        ],
      },
      {
        headers: {
          'Idempotency-Key': idem1,
        },
        query: { dealerLinkId: dealerLinkId.value },
      },
    )

    const idem2 = newIdempotencyKey()
    const payRes = await apiPost<{ orderId: string; paymentStatus: 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED' }>(
      `/orders/${order.id}/pay`,
      { paymentMethod: 'WECHAT' },
      { headers: { 'Idempotency-Key': idem2 } },
    )

    if (payRes.paymentStatus === 'FAILED') {
      router.replace({
        path: '/h5/pay/result',
        query: { dealerLinkId: dealerLinkId.value, status: 'fail', reason: '微信支付下单失败', orderId: order.id },
      })
      return
    }

    // 微信 H5（MWEB）：跳转支付页，并指定回跳到支付结果页（结果页将按 orderId 拉取 bind_token）
    const redirectUrl = `${window.location.origin}/h5/pay/result?dealerLinkId=${encodeURIComponent(
      dealerLinkId.value,
    )}&orderId=${encodeURIComponent(order.id)}`

    const rawUrl = (payRes as any).wechatH5Url as string | undefined
    if (!rawUrl) {
      router.replace({
        path: '/h5/pay/result',
        query: { dealerLinkId: dealerLinkId.value, status: 'fail', reason: '缺少 wechatH5Url', orderId: order.id },
      })
      return
    }

    const u = new URL(rawUrl)
    u.searchParams.set('redirect_url', redirectUrl)
    window.location.href = u.toString()
  } catch (e: any) {
    router.replace({ path: '/h5/pay/result', query: { dealerLinkId: dealerLinkId.value, status: 'fail', reason: presentErrorMessage(e) } })
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(() => {
  loadServiceCategories()
  loadRegions()
  loadDealerContext()

  // 兼容提醒：旧链接参数已废弃（开发阶段无存量迁移需求）
  const legacy = parseDealerParams(route.query as Record<string, unknown>)
  if (legacy && !parseDealerLinkId(route.query as Record<string, unknown>)) {
    dealerTip.value = '链接格式已升级，请从经销商后台重新生成投放链接'
  }
})

watch(
  () => provinces.value,
  (ps) => {
    if (requiredRegionLevel.value !== 'CITY') return
    if (!selectedProvinceScope.value && ps.length) selectedProvinceScope.value = ps[0]?.value || ''
  },
  { immediate: true },
)
</script>

<style scoped>
.page {
  padding-bottom: 96px;
}
.link {
  color: var(--lh-teal-700);
  font-weight: 600;
}
.section {
  margin: 12px 16px 0;
  overflow: hidden;
  border-radius: var(--lh-radius-card);
  background: var(--lh-card-bg);
  box-shadow: var(--lh-shadow-card);
  border: 1px solid var(--lh-border);
}
.cta {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.92);
  border-top: 1px solid rgba(2, 6, 23, 0.08);
  box-shadow: var(--lh-shadow-float);
}

/* ===== 服务协议弹层（仿照 H5 其它弹层/卡片风格） ===== */
.agreement {
  height: 80vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(
    180deg,
    rgba(20, 184, 166, 0.06) 0%,
    rgba(255, 255, 255, 1) 24%,
    rgba(255, 255, 255, 1) 100%
  );
}
.agreement-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--lh-border);
  /* sticky 让标题栏在长协议滚动时仍可见，体验和其它弹层一致 */
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: saturate(180%) blur(8px);
  z-index: 1;
}
.agreement-title {
  font-weight: 700;
  font-size: 15px;
  color: var(--lh-slate-900);
}
.agreement-body {
  flex: 1;
  overflow: auto;
  padding: 14px 16px 22px;
}
.agreement-empty {
  padding: 24px 0;
  font-size: 13px;
  color: var(--lh-slate-500);
  text-align: center;
}
/* 协议内容（HTML）排版：保证“有设计”的可读性，但不改变信息结构 */
.agreement-html {
  color: var(--lh-slate-700);
  font-size: 13px;
  line-height: 1.85;
  word-break: break-word;
}
.agreement-html :deep(h1),
.agreement-html :deep(h2),
.agreement-html :deep(h3) {
  margin: 14px 0 10px;
  color: var(--lh-slate-900);
  font-weight: 800;
  line-height: 1.4;
}
.agreement-html :deep(h1) {
  font-size: 16px;
}
.agreement-html :deep(h2) {
  font-size: 15px;
}
.agreement-html :deep(h3) {
  font-size: 14px;
}
.agreement-html :deep(p) {
  margin: 0 0 12px;
}
.agreement-html :deep(ul),
.agreement-html :deep(ol) {
  margin: 0 0 12px;
  padding-left: 18px;
}
.agreement-html :deep(li) {
  margin: 4px 0;
}
.agreement-html :deep(strong),
.agreement-html :deep(b) {
  color: var(--lh-slate-900);
}
.agreement-html :deep(a) {
  color: var(--lh-teal-700);
  text-decoration: underline;
}
.agreement-html :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
}
.agreement-html :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 14px;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid var(--lh-border-soft);
}
.agreement-html :deep(th),
.agreement-html :deep(td) {
  border: 1px solid var(--lh-border-soft);
  padding: 10px 10px;
  font-size: 12px;
  vertical-align: top;
}
.agreement-html :deep(th) {
  background: rgba(2, 6, 23, 0.03);
  color: var(--lh-slate-900);
  font-weight: 700;
}
.region-popup {
  height: 80vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(20, 184, 166, 0.06) 0%, rgba(255, 255, 255, 1) 24%, rgba(255, 255, 255, 1) 100%);
}
.region-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--lh-border);
}
.region-title {
  font-weight: 700;
}
.region-body {
  flex: 1;
  overflow: hidden;
}
.region-list {
  height: calc(80vh - 110px);
  overflow: auto;
}
.region-cascade {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}
.region-col {
  border-right: 1px solid var(--lh-border);
}
.region-col:last-child {
  border-right: none;
}
.region-col-title {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--lh-slate-500);
}
.region-scroll {
  height: calc(80vh - 160px);
  overflow: auto;
}
.active {
  background: rgba(20, 184, 166, 0.10);
}
</style>


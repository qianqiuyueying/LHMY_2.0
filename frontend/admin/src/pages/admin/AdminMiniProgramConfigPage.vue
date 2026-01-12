<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import { uploadImage } from '../../lib/uploads'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import mpAppJson from '../../../../mini-program/app.json'
import { fmtBeijingDateTime } from '../../lib/time'

// -----------------------------
// Spec: REQ-ADMIN-P0-012（运营向导 + 最小概念暴露）
// IA:
// - 首页装修：Banner、快捷入口（分离）
// - 页面库：聚合页、信息页（分离）
// - 高级：集合/JSON（默认隐藏）
// - 预览：纯文本预览（无需保存/发布）
// - 读侧对照：直接查看 /mini-program/* 返回
// -----------------------------

type JumpType = 'AGG_PAGE' | 'INFO_PAGE' | 'WEBVIEW' | 'ROUTE' | 'MINI_PROGRAM'
type NavLayout = 'TABS_LIST' | 'SIDEBAR_GRID'

type EntryItem = {
  id: string
  name: string
  iconUrl?: string | null
  position: 'SHORTCUT' | 'OPERATION'
  jumpType: JumpType
  targetId: string
  sort: number
  enabled: boolean
  published?: boolean | null
}

type PageItem = {
  id: string
  type: 'AGG_PAGE' | 'INFO_PAGE'
  config: Record<string, any>
  version?: string | null
  published: boolean
  draftVersion?: string | null
  draftUpdatedAt?: string | null
  publishedAt?: string | null
}

type RegionItem = { code: string; name: string; sort: number }
type CollectionItem = { id: string; name: string; schema?: Record<string, any>; items?: any[]; published?: boolean; updatedAt?: string | null }

type KvPair = { key: string; value: string }

// -----------------------------
// shared: utilities
// -----------------------------
function _defaultId(prefix: string): string {
  return `${prefix}_${Date.now()}`
}

function _safeDecodeURIComponent(s: string): string {
  try {
    return decodeURIComponent(String(s || ''))
  } catch {
    return String(s || '')
  }
}

function _safeEncodeURIComponent(s: string): string {
  try {
    return encodeURIComponent(String(s ?? ''))
  } catch {
    return String(s ?? '')
  }
}

function normalizeRoutePath(raw: string): string {
  let p = String(raw || '').trim()
  if (!p) return ''
  if (!p.startsWith('/')) p = '/' + p
  return p
}

function parseQueryString(raw: string): KvPair[] {
  const s = String(raw || '').trim().replace(/^\?/, '')
  if (!s) return []
  const parts = s.split('&').filter(Boolean)
  const out: KvPair[] = []
  for (const part of parts) {
    const idx = part.indexOf('=')
    if (idx < 0) {
      out.push({ key: _safeDecodeURIComponent(part), value: '' })
      continue
    }
    const k = part.slice(0, idx)
    const v = part.slice(idx + 1)
    out.push({ key: _safeDecodeURIComponent(k), value: _safeDecodeURIComponent(v) })
  }
  return out
}

function buildQueryString(pairs: KvPair[]): string {
  const clean = (pairs || [])
    .map((p) => ({ key: String(p?.key || '').trim(), value: String(p?.value ?? '').trim() }))
    .filter((p) => !!p.key)
  if (clean.length === 0) return ''
  const qs = clean.map((p) => `${_safeEncodeURIComponent(p.key)}=${_safeEncodeURIComponent(p.value)}`).join('&')
  return qs ? `?${qs}` : ''
}

function parseRouteTarget(targetId: string): { path: string; pairs: KvPair[] } {
  const s = String(targetId || '').trim()
  if (!s) return { path: '', pairs: [] }
  const idx = s.indexOf('?')
  const path = normalizeRoutePath(idx >= 0 ? s.slice(0, idx) : s)
  const qs = idx >= 0 ? s.slice(idx + 1) : ''
  return { path, pairs: parseQueryString(qs) }
}

function setRouteTarget(obj: any, path: string, pairs: KvPair[]) {
  const p = normalizeRoutePath(path)
  obj.targetId = `${p}${buildQueryString(pairs)}`
}

function parseMiniProgramTarget(targetId: string): { appId: string; path: string } {
  const s = String(targetId || '').trim()
  if (!s) return { appId: '', path: '' }
  const idx = s.indexOf('|')
  if (idx < 0) return { appId: s, path: '' }
  return { appId: s.slice(0, idx).trim(), path: s.slice(idx + 1).trim() }
}

function setMiniProgramTarget(obj: any, appId: string, path: string) {
  const aid = String(appId || '').trim()
  const p = String(path || '').trim()
  // 规格：targetId=appid|path（path 可为空）
  obj.targetId = `${aid}|${p}`
}

const pageTitleById = computed(() => {
  const m: Record<string, string> = {}
  for (const p of pages.value || []) {
    const title = String((p as any)?.config?.title || (p as any)?.config?.name || '').trim()
    m[String(p.id)] = title || String(p.id)
  }
  return m
})

function pageLabel(id: string): string {
  const k = String(id || '')
  return pageTitleById.value[k] || k
}

function jumpTypeLabel(jt: JumpType): string {
  return (
    {
      AGG_PAGE: '聚合页',
      INFO_PAGE: '信息页',
      WEBVIEW: 'H5 外链',
      MINI_PROGRAM: '其他小程序',
      ROUTE: '小程序路由',
    } as const
  )[jt]
}

function pageStatusText(p: PageItem): { kind: 'success' | 'info'; text: string } {
  return p?.published ? { kind: 'success', text: '已发布' } : { kind: 'info', text: '未发布' }
}

function pagesForJumpType(jt: JumpType): PageItem[] {
  if (jt === 'AGG_PAGE') return aggPages.value
  if (jt === 'INFO_PAGE') return infoPages.value
  return []
}

function targetPlaceholder(jt: JumpType): string {
  if (jt === 'ROUTE') return '例如：/pages/venue-detail/venue-detail?id=xxx'
  if (jt === 'WEBVIEW') return '例如：https://example.com/xxx'
  if (jt === 'MINI_PROGRAM') return '例如：wx1234567890abcdef|/pages/index/index（path 可为空）'
  return '请输入跳转目标'
}

function entryTargetLabel(e: EntryItem): string {
  if (!e) return ''
  if (e.jumpType === 'AGG_PAGE' || e.jumpType === 'INFO_PAGE') return pageLabel(e.targetId)
  return String(e.targetId || '')
}

function formatApiError(e: any, fallback: string, path?: string): string {
  const p = path ? `（${path}）` : ''
  const msg = e?.apiError?.message ?? e?.message ?? fallback
  const code = e?.apiError?.code ? `（code=${e.apiError.code}）` : ''
  const rid = e?.apiError?.requestId ? `（requestId=${e.apiError.requestId}）` : ''
  return `${msg}${code}${rid}${p}`
}

const router = useRouter()

// -----------------------------
// preview/read-side
// -----------------------------
const readSideOpen = ref(false)
const readSideTitle = ref('')
const readSideJson = ref('')

async function openReadSideEntries() {
  try {
    const data = await apiRequest<{ items: any[]; version: string }>('/mini-program/entries', { auth: false })
    readSideTitle.value = '读侧对照：/mini-program/entries'
    readSideJson.value = JSON.stringify(data, null, 2)
    readSideOpen.value = true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '读取读侧失败' })
  }
}

async function openReadSidePage(id: string) {
  try {
    const data = await apiRequest<any>(`/mini-program/pages/${id}`, { auth: false })
    readSideTitle.value = `读侧对照：/mini-program/pages/${id}`
    readSideJson.value = JSON.stringify(data, null, 2)
    readSideOpen.value = true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '读取读侧失败' })
  }
}

const textPreviewOpen = ref(false)
const textPreviewTitle = ref('')
const textPreviewContent = ref('')
function openTextPreview(title: string, content: string) {
  textPreviewTitle.value = title
  textPreviewContent.value = content
  textPreviewOpen.value = true
}

function _indent(s: string, n: number): string {
  const pad = '  '.repeat(Math.max(0, n))
  return String(s || '')
    .split('\n')
    .map((x) => (x ? pad + x : x))
    .join('\n')
}

function _jumpText(it: any): string {
  const title = String(it?.title || it?.name || '').trim()
  const sub = String(it?.subtitle || '').trim()
  const icon = String(it?.iconUrl || '').trim()
  const jt = String(it?.jumpType || '').trim()
  const tid = String(it?.targetId || '').trim()
  const enabled = it?.enabled === false ? '（禁用）' : ''
  const sort = Number(it?.sort || 0)
  const iconText = icon ? ` icon=${icon}` : ''
  const subText = sub ? ` / ${sub}` : ''
  return `${title}${subText}${enabled}  ${jt} -> ${tid}  sort=${sort}${iconText}`
}

function buildEntriesPreview(items: EntryItem[], position: EntryItem['position']): string {
  const list = (items || [])
    .filter((x) => x?.position === position)
    .slice()
    .sort((a, b) => (a.sort || 0) - (b.sort || 0))
  const title = position === 'OPERATION' ? 'Banner/运营位（OPERATION）' : '快捷入口（SHORTCUT）'
  const lines: string[] = []
  lines.push(`${title}：${list.length}`)
  for (const x of list) {
    lines.push(_indent(`- ${x.name}${x.enabled ? '' : '（禁用）'}  ${x.jumpType} -> ${x.targetId}  sort=${x.sort}`, 1))
  }
  return lines.join('\n').trim() + '\n'
}

function buildAggPreview(cfg: any): string {
  const title = String(cfg?.title || '').trim() || '（未命名聚合页）'
  const layout = String(cfg?.nav?.layout || 'TABS_LIST').trim() || 'TABS_LIST'
  const groups = Array.isArray(cfg?.nav?.groups) ? cfg.nav.groups : []
  const lines: string[] = []
  lines.push(`聚合页：${title}`)
  lines.push(`布局：${layout}`)
  lines.push('')

  if (layout === 'SIDEBAR_GRID') {
    for (const g of groups) {
      const gName = String(g?.name || '').trim() || '（未命名分类）'
      lines.push(`- ${gName}`)
      const items = Array.isArray(g?.items) ? g.items : []
      for (const it of items) lines.push(_indent(`- ${_jumpText(it)}`, 1))
      if (items.length === 0) lines.push(_indent('（暂无图标项）', 1))
    }
    if (groups.length === 0) lines.push('（暂无分类）')
    return lines.join('\n').trim() + '\n'
  }

  for (const g of groups) {
    const gName = String(g?.name || '').trim() || '（未命名一级）'
    lines.push(`- ${gName}`)
    const children = Array.isArray(g?.children) ? g.children : []
    for (const c of children) {
      const cName = String(c?.name || '').trim() || '全部'
      lines.push(_indent(`- ${cName}`, 1))
      const items = Array.isArray(c?.items) ? c.items : []
      for (const it of items) lines.push(_indent(`- ${_jumpText(it)}`, 2))
      if (items.length === 0) lines.push(_indent('（暂无条目）', 2))
    }
    if (children.length === 0) lines.push(_indent('（暂无二级分类）', 1))
  }
  if (groups.length === 0) lines.push('（暂无分类）')
  return lines.join('\n').trim() + '\n'
}

function buildInfoPreview(cfg: any): string {
  const title = String(cfg?.title || '').trim() || '（未命名信息页）'
  const blocks = Array.isArray(cfg?.blocks) ? cfg.blocks : []
  const lines: string[] = []
  lines.push(`信息页：${title}`)
  lines.push(`Blocks：${blocks.length}`)
  lines.push('')
  for (const [idx, b] of blocks.entries()) {
    const t = String(b?.type || '').trim()
    if (t === 'richText') {
      const html = String(b?.contentHtml || '').trim()
      lines.push(`- [${idx + 1}] richText`)
      lines.push(_indent(html ? html.slice(0, 400) + (html.length > 400 ? '…' : '') : '（空）', 1))
      continue
    }
    if (t === 'banner' || t === 'links' || t === 'cards') {
      const items = Array.isArray(b?.items) ? b.items : []
      lines.push(`- [${idx + 1}] ${t}：${items.length}`)
      for (const it of items) lines.push(_indent(`- ${_jumpText(it)}`, 1))
      continue
    }
    if (t === 'cmsContent') {
      const cid = String(b?.contentId || '').trim()
      const ct = String(b?.title || '').trim()
      lines.push(`- [${idx + 1}] cmsContent：${cid}${ct ? `（${ct}）` : ''}`)
      continue
    }
    lines.push(`- [${idx + 1}] ${t || 'unknown'}`)
  }
  return lines.join('\n').trim() + '\n'
}

// -----------------------------
// loading state
// -----------------------------
const activeMain = ref<'home' | 'pages' | 'recommendations' | 'advanced'>('home')
const activePages = ref<'agg' | 'info'>('agg')
const showAdvanced = ref(false)

// -----------------------------
// home recommendations (venues/products)
// -----------------------------
type MpRecommendedVenueItem = { venueId: string; name: string; publishStatus: string }
type MpRecommendedProductItem = { productId: string; title: string; status: string }
type MpRecommendedVenuesResp = { enabled: boolean; version: string; items: MpRecommendedVenueItem[] }
type MpRecommendedProductsResp = { enabled: boolean; version: string; items: MpRecommendedProductItem[] }

const mpRecLoading = ref(false)
const mpRecSaving = ref(false)
const mpRecVenuesEnabled = ref(false)
const mpRecProductsEnabled = ref(false)
const mpRecVenuesVersion = ref('0')
const mpRecProductsVersion = ref('0')
const mpRecVenues = ref<MpRecommendedVenueItem[]>([])
const mpRecProducts = ref<MpRecommendedProductItem[]>([])

const mpRecNewVenueId = ref('')
const mpRecNewProductId = ref('')
const mpRecVenueSearchLoading = ref(false)
const mpRecProductSearchLoading = ref(false)
const mpRecVenueOptions = ref<Array<{ value: string; label: string; name: string; publishStatus: string }>>([])
const mpRecProductOptions = ref<Array<{ value: string; label: string; title: string; status: string }>>([])

async function loadMpRecommendations() {
  mpRecLoading.value = true
  try {
    const [v, p] = await Promise.all([
      apiRequest<MpRecommendedVenuesResp>('/admin/mini-program/home/recommended-venues'),
      apiRequest<MpRecommendedProductsResp>('/admin/mini-program/home/recommended-products'),
    ])
    mpRecVenuesEnabled.value = !!v.enabled
    mpRecProductsEnabled.value = !!p.enabled
    mpRecVenuesVersion.value = v.version || '0'
    mpRecProductsVersion.value = p.version || '0'
    mpRecVenues.value = (v.items || []).map((x) => ({
      venueId: String((x as any).venueId || '').trim(),
      name: String((x as any).name || ''),
      publishStatus: String((x as any).publishStatus || ''),
    }))
    mpRecProducts.value = (p.items || []).map((x) => ({
      productId: String((x as any).productId || '').trim(),
      title: String((x as any).title || ''),
      status: String((x as any).status || ''),
    }))
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '加载推荐配置失败' })
    mpRecVenues.value = []
    mpRecProducts.value = []
  } finally {
    mpRecLoading.value = false
  }
}

async function searchMpRecVenues(keyword: string) {
  const kw = String(keyword || '').trim()
  if (!kw) {
    mpRecVenueOptions.value = []
    return
  }
  mpRecVenueSearchLoading.value = true
  try {
    const data = await apiRequest<{ items: any[]; total: number }>('/admin/venues', {
      // 口径：候选以“审核通过”为准；若尚未发布，上线会在保存推荐时自动补发布
      query: { keyword: kw, reviewStatus: 'APPROVED', page: 1, pageSize: 20 },
    })
    mpRecVenueOptions.value = (data.items || []).map((x) => {
      const id = String(x.id || '').trim()
      const name = String(x.name || '').trim()
      const ps = String(x.publishStatus || '').trim()
      const providerName = String(x.providerName || '').trim()
      const label = `${name || id}${providerName ? `（${providerName}）` : ''}（发布=${ps || '-'} / id=${id}）`
      return { value: id, label, name, publishStatus: ps }
    })
  } catch (e: any) {
    mpRecVenueOptions.value = []
    handleApiError(e, { router, fallbackMessage: '场所搜索失败' })
  } finally {
    mpRecVenueSearchLoading.value = false
  }
}

async function searchMpRecProducts(keyword: string) {
  const kw = String(keyword || '').trim()
  if (!kw) {
    mpRecProductOptions.value = []
    return
  }
  mpRecProductSearchLoading.value = true
  try {
    // 管理端：用 /admin/products（可筛选状态），口径为“审核通过=ON_SALE”
    const data = await apiRequest<{ items: any[]; total: number }>('/admin/products', { query: { keyword: kw, status: 'ON_SALE', page: 1, pageSize: 20 } })
    mpRecProductOptions.value = (data.items || []).map((x) => {
      const id = String(x.id || '').trim()
      const title = String(x.title || '').trim()
      const label = `${title || id}（id=${id}）`
      return { value: id, label, title, status: String(x.status || 'ON_SALE') }
    })
  } catch (e: any) {
    mpRecProductOptions.value = []
    handleApiError(e, { router, fallbackMessage: '商品搜索失败' })
  } finally {
    mpRecProductSearchLoading.value = false
  }
}

function mpRecAddVenue() {
  const vid = String(mpRecNewVenueId.value || '').trim()
  if (!vid) return ElMessage.error('请选择场所')
  if (mpRecVenues.value.some((x) => x.venueId === vid)) return ElMessage.error('该场所已在列表中')
  const opt = mpRecVenueOptions.value.find((x) => x.value === vid)
  mpRecVenues.value.push({ venueId: vid, name: opt?.name || '', publishStatus: opt?.publishStatus || '' })
  mpRecNewVenueId.value = ''
}

function mpRecAddProduct() {
  const pid = String(mpRecNewProductId.value || '').trim()
  if (!pid) return ElMessage.error('请选择商品')
  if (mpRecProducts.value.some((x) => x.productId === pid)) return ElMessage.error('该商品已在列表中')
  const opt = mpRecProductOptions.value.find((x) => x.value === pid)
  mpRecProducts.value.push({ productId: pid, title: opt?.title || '', status: opt?.status || '' })
  mpRecNewProductId.value = ''
}

async function saveMpRecommendations() {
  mpRecSaving.value = true
  try {
    const venueIds = mpRecVenues.value.map((x) => String(x.venueId || '').trim()).filter(Boolean)
    const productIds = mpRecProducts.value.map((x) => String(x.productId || '').trim()).filter(Boolean)
    if (venueIds.length !== mpRecVenues.value.length) return ElMessage.error('推荐场所列表存在空ID')
    if (productIds.length !== mpRecProducts.value.length) return ElMessage.error('推荐商品列表存在空ID')

    // 选中的场所若尚未发布：保存推荐前自动补发布（否则小程序读侧会过滤掉）
    for (const it of mpRecVenues.value) {
      const vid = String(it.venueId || '').trim()
      if (!vid) continue
      const ps = String(it.publishStatus || '').toUpperCase()
      if (ps !== 'PUBLISHED') {
        await apiRequest(`/admin/venues/${vid}/publish`, { method: 'POST' })
      }
    }

    await Promise.all([
      apiRequest('/admin/mini-program/home/recommended-venues', {
        method: 'PUT',
        body: { enabled: mpRecVenuesEnabled.value, items: venueIds.map((venueId) => ({ venueId })) },
      }),
      apiRequest('/admin/mini-program/home/recommended-products', {
        method: 'PUT',
        body: { enabled: mpRecProductsEnabled.value, items: productIds.map((productId) => ({ productId })) },
      }),
    ])
    ElMessage.success('已保存')
    await loadMpRecommendations()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    mpRecSaving.value = false
  }
}

// entries/pages/collections
const entriesLoading = ref(false)
const entriesError = ref('')
const entriesErrorCode = ref('')
const entriesErrorRequestId = ref('')
const entriesVersion = ref('0')
const entries = ref<EntryItem[]>([])

const pagesLoading = ref(false)
const pagesError = ref('')
const pagesErrorCode = ref('')
const pagesErrorRequestId = ref('')
const pages = ref<PageItem[]>([])

const mpRouteOptions = computed(() => {
  const pages = ((mpAppJson as any)?.pages || []) as string[]
  return pages.map((x) => normalizeRoutePath(String(x || '').replace(/^\//, ''))).filter(Boolean)
})

const miniProgramAppIdOptions = computed(() => {
  const ids = new Set<string>()
  // entries
  for (const e of entries.value || []) {
    if (e?.jumpType !== 'MINI_PROGRAM') continue
    const { appId } = parseMiniProgramTarget(String(e?.targetId || ''))
    if (appId) ids.add(appId)
  }
  // pages（已保存的 config 内也会带）
  for (const p of pages.value || []) {
    const cfg: any = (p as any)?.config || {}
    const groups = Array.isArray(cfg?.nav?.groups) ? cfg.nav.groups : []
    for (const g of groups) {
      const items = Array.isArray(g?.items) ? g.items : []
      for (const it of items) {
        if (String(it?.jumpType || '') !== 'MINI_PROGRAM') continue
        const { appId } = parseMiniProgramTarget(String(it?.targetId || ''))
        if (appId) ids.add(appId)
      }
      const children = Array.isArray(g?.children) ? g.children : []
      for (const c of children) {
        const cItems = Array.isArray(c?.items) ? c.items : []
        for (const it of cItems) {
          if (String(it?.jumpType || '') !== 'MINI_PROGRAM') continue
          const { appId } = parseMiniProgramTarget(String(it?.targetId || ''))
          if (appId) ids.add(appId)
        }
      }
    }
  }
  return Array.from(ids).sort()
})

const colsLoading = ref(false)
const colsError = ref('')
const colsErrorCode = ref('')
const colsErrorRequestId = ref('')
const cols = ref<CollectionItem[]>([])

// regions for legacy collections editor (advanced)
const regionsLoading = ref(false)
const regionItems = ref<RegionItem[]>([])

async function loadRegions() {
  regionsLoading.value = true
  try {
    const data = await apiRequest<{ items: RegionItem[]; version: string }>('/regions/cities', { auth: false })
    regionItems.value = (data.items || []).slice()
  } catch {
    regionItems.value = []
  } finally {
    regionsLoading.value = false
  }
}

async function loadEntries() {
  entriesLoading.value = true
  try {
    const data = await apiRequest<{ items: EntryItem[]; version: string }>('/admin/mini-program/entries')
    entries.value = data.items || []
    entriesVersion.value = data.version || '0'
    entriesError.value = ''
    entriesErrorCode.value = ''
    entriesErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    entriesError.value = msg
    entriesErrorCode.value = e?.apiError?.code ?? ''
    entriesErrorRequestId.value = e?.apiError?.requestId ?? ''
  } finally {
    entriesLoading.value = false
  }
}

async function loadPages() {
  pagesLoading.value = true
  try {
    const data = await apiRequest<{ items: PageItem[]; version: string }>('/admin/mini-program/pages')
    pages.value = data.items || []
    pagesError.value = ''
    pagesErrorCode.value = ''
    pagesErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    pagesError.value = msg
    pagesErrorCode.value = e?.apiError?.code ?? ''
    pagesErrorRequestId.value = e?.apiError?.requestId ?? ''
  } finally {
    pagesLoading.value = false
  }
}

async function loadCollections() {
  if (!showAdvanced.value) return
  colsLoading.value = true
  try {
    const data = await apiRequest<{ items: CollectionItem[]; version: string }>('/admin/mini-program/collections')
    cols.value = data.items || []
    colsError.value = ''
    colsErrorCode.value = ''
    colsErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    colsError.value = msg
    colsErrorCode.value = e?.apiError?.code ?? ''
    colsErrorRequestId.value = e?.apiError?.requestId ?? ''
  } finally {
    colsLoading.value = false
  }
}

// -----------------------------
// Home: Banner / Shortcuts (separated)
// -----------------------------
const banners = computed(() => entries.value.filter((x) => x.position === 'OPERATION').slice().sort((a, b) => (a.sort || 0) - (b.sort || 0)))
const shortcuts = computed(() => entries.value.filter((x) => x.position === 'SHORTCUT').slice().sort((a, b) => (a.sort || 0) - (b.sort || 0)))

function upsertEntryLocal(item: EntryItem) {
  const next = entries.value.slice()
  const idx = next.findIndex((x) => x.id === item.id)
  if (idx >= 0) next[idx] = { ...next[idx], ...item }
  else next.push({ ...item })
  next.sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0))
  entries.value = next
}

function removeEntryLocal(id: string) {
  entries.value = entries.value.filter((x) => x.id !== id)
}

function precheckEntriesBeforePublish(): string | null {
  const pageById = new Map(pages.value.map((p) => [String(p.id), p] as const))
  for (const x of entries.value) {
    if (!x?.enabled) continue
    const jt = String(x?.jumpType || '').trim()
    const tid = String(x?.targetId || '').trim()
    if (!jt) return `入口「${x.name}」的 jumpType 不能为空`
    if (!tid) return `入口「${x.name}」的 targetId 不能为空`
    if (!['AGG_PAGE', 'INFO_PAGE', 'WEBVIEW', 'ROUTE', 'MINI_PROGRAM', 'FIXED_ROUTE'].includes(jt)) {
      return `入口「${x.name}」的 jumpType 不合法：${jt}`
    }
    if (jt === 'ROUTE' || jt === 'FIXED_ROUTE') {
      if (!tid.startsWith('/')) return `入口「${x.name}」的 ROUTE 必须以 “/” 开头（例如：/pages/xxx/xxx?id=1）`
      // 仅做基础防呆：避免误填成 http 链接
      if (tid.startsWith('http://') || tid.startsWith('https://')) return `入口「${x.name}」选择了 ROUTE，但 targetId 看起来是外链；请改为 WEBVIEW 或填小程序页面路径`
    }
    if (jt === 'WEBVIEW') {
      if (!/^https?:\/\//i.test(tid)) return `入口「${x.name}」的 WEBVIEW targetId 必须是 http(s) 链接`
    }
    if (jt === 'MINI_PROGRAM') {
      const { appId } = parseMiniProgramTarget(tid)
      if (!appId) return `入口「${x.name}」的 MINI_PROGRAM targetId 必须包含 appId（格式：appid|path）`
    }
    if (x.jumpType === 'AGG_PAGE' || x.jumpType === 'INFO_PAGE') {
      const pid = String(x.targetId || '').trim()
      const p = pageById.get(pid) || null
      if (!p) return `入口「${x.name}」指向页面 ${pid}，但该 pageId 不存在（请先创建页面）`
      // 读侧契约：未发布页面在小程序端必然 404
      if (!p.published) {
        return `入口「${x.name}」指向页面 ${pid}，但该页面尚未发布（小程序会提示“页面不存在”）。请先到「页面库」发布该页面。`
      }
    }
  }
  return null
}

const entryDialogOpen = ref(false)
const entryDialogMode = ref<'create' | 'edit'>('create')
const entryDialogTitle = computed(() => {
  const pos = entryForm.value.position === 'OPERATION' ? 'Banner' : '快捷入口'
  return entryDialogMode.value === 'create' ? `新增${pos}` : `编辑${pos}`
})

const entryForm = ref<EntryItem>({
  id: '',
  name: '',
  iconUrl: '',
        position: 'SHORTCUT',
        jumpType: 'ROUTE',
  targetId: '',
        sort: 10,
        enabled: true,
  published: null,
})

// ROUTE 参数编辑器（key/value -> querystring）
const routeParamEditorOpen = ref(false)
const routeParamEditorTitle = ref('')
const routeParamPairs = ref<KvPair[]>([])
const routeParamTargetObj = ref<any | null>(null)
const routeParamBasePath = ref('')

function openRouteParamEditor(targetObj: any, title: string) {
  routeParamTargetObj.value = targetObj
  routeParamEditorTitle.value = title
  const { path, pairs } = parseRouteTarget(String(targetObj?.targetId || ''))
  routeParamBasePath.value = path
  routeParamPairs.value = pairs.length > 0 ? pairs.map((p) => ({ ...p })) : [{ key: '', value: '' }]
  routeParamEditorOpen.value = true
}

function confirmRouteParamEditor() {
  const obj = routeParamTargetObj.value
  if (!obj) return (routeParamEditorOpen.value = false)
  const basePath = routeParamBasePath.value || parseRouteTarget(String(obj.targetId || '')).path
  setRouteTarget(obj, basePath, routeParamPairs.value)
  routeParamEditorOpen.value = false
}

const entryIconUploading = ref(false)
async function uploadEntryIcon(file: any) {
  const raw: File | undefined = file?.raw
  if (!raw) return ElMessage.error('请选择图片文件')
  entryIconUploading.value = true
  try {
    const url = await uploadImage(raw)
    entryForm.value.iconUrl = url
    ElMessage.success('已上传')
  } catch (e: any) {
    ElMessage.error(e?.message ?? '上传失败')
  } finally {
    entryIconUploading.value = false
  }
}

function onEntryJumpTypeChange() {
  // 避免“先选页面后切到外链/路由”等导致残留 targetId 误导
  entryForm.value.targetId = ''
}

function openCreateBanner() {
  entryDialogMode.value = 'create'
  entryForm.value = {
    id: _defaultId('BANNER'),
    name: '',
    iconUrl: '',
        position: 'OPERATION',
        jumpType: 'AGG_PAGE',
    targetId: '',
        sort: 20,
        enabled: true,
    published: null,
  }
  entryDialogOpen.value = true
}

function openCreateShortcut() {
  entryDialogMode.value = 'create'
  entryForm.value = {
    id: _defaultId('ENTRY'),
    name: '',
    iconUrl: '',
    position: 'SHORTCUT',
    jumpType: 'ROUTE',
    targetId: '',
    sort: 10,
    enabled: true,
    published: null,
  }
  entryDialogOpen.value = true
}

function openEditEntry(row: EntryItem) {
  entryDialogMode.value = 'edit'
  entryForm.value = { ...row }
  entryDialogOpen.value = true
}

const entriesSaving = ref(false)

function _validateEntryDraft(e: EntryItem): string | null {
  const name = String((e as any)?.name || '').trim() || String((e as any)?.id || '').trim() || '未命名'
  const jumpType = String((e as any)?.jumpType || '').trim()
  const targetId = String((e as any)?.targetId || '').trim()
  if (!targetId) return `「${name}」跳转目标必填`

  if (jumpType === 'WEBVIEW') {
    // 口径与后端一致：生产仅 https；开发允许 localhost/127.0.0.1/0.0.0.0 回环
    const url = targetId
    const ok = /^https:\/\//.test(url) || /^http:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:|\/|$)/.test(url)
    if (!ok) return `「${name}」外链仅允许 https://（开发环境允许 localhost 回环）`
  }

  if (jumpType === 'MINI_PROGRAM') {
    // 规格：targetId=appid|path（path 可为空；若不为空必须以 / 开头）
    const { appId, path } = parseMiniProgramTarget(targetId)
    if (!String(appId || '').trim()) return `「${name}」其他小程序 appId 不能为空`
    if (path && !String(path).startsWith('/')) return `「${name}」小程序 path 必须以 / 开头（例如 /pages/index/index）`
    // 规范化存储格式：确保包含 "|"
    setMiniProgramTarget(e as any, appId, path)
  }

  return null
}

async function saveEntriesDraft(): Promise<boolean> {
  entriesSaving.value = true
  try {
    const beforeCount = entries.value.length
    // 保存草稿前做一次前端校验，避免把明显非法配置提交到后端（否则后端会返回 400）
    for (const it of entries.value || []) {
      const err = _validateEntryDraft(it)
      if (err) {
        ElMessage.error(err)
        return false
      }
    }
    await apiRequest('/admin/mini-program/entries', { method: 'PUT', body: { items: entries.value } })
    await loadEntries()
    // 强确认：如果本地有条目，但保存后重新拉取还是空，说明保存未落库/环境不一致
    if (beforeCount > 0 && (entries.value || []).length === 0) {
      ElMessage.error(
        '保存看似成功，但重新拉取 entries 仍为空：可能保存未落库，或当前前端请求的后端与实际生效环境不一致（端口/代理/多后端）。请打开“诊断信息”确认页面地址与 API Base，并重试。',
      )
      return false
    }
    ElMessage.success('已保存草稿')
    return true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
    return false
  } finally {
    entriesSaving.value = false
  }
}

async function publishEntries() {
  try {
    const err = precheckEntriesBeforePublish()
    if (err) return ElMessage.error(err)
    await apiRequest('/admin/mini-program/entries/publish', { method: 'POST' })
    ElMessage.success('已发布（小程序读侧可见）')
    await loadEntries()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function saveAndPublishEntries() {
  const ok = await saveEntriesDraft()
  if (!ok) return
  await publishEntries()
  await openReadSideEntries()
}

async function offlineEntries() {
  try {
    await apiRequest('/admin/mini-program/entries/offline', { method: 'POST' })
    ElMessage.success('已下线')
    await loadEntries()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

async function confirmDeleteEntry(row: EntryItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」吗？（仅删除草稿，需重新发布后生效）`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  removeEntryLocal(row.id)
  await saveEntriesDraft()
}

async function submitEntryDialog() {
  const e = entryForm.value
  e.id = String(e.id || '').trim()
  e.name = String(e.name || '').trim()
  e.targetId = String(e.targetId || '').trim()
  if (!e.id) return ElMessage.error('系统ID 不能为空')
  if (!e.name) return ElMessage.error('名称必填')
  if (e.jumpType === 'ROUTE') {
    const { path, pairs } = parseRouteTarget(e.targetId)
    if (!path) return ElMessage.error('请选择/填写本小程序页面路径')
    setRouteTarget(e, path, pairs)
  } else if (e.jumpType === 'MINI_PROGRAM') {
    const { appId, path } = parseMiniProgramTarget(e.targetId)
    if (!appId) return ElMessage.error('请输入其他小程序 appId')
    if (path && !String(path).startsWith('/')) return ElMessage.error('小程序 path 必须以 / 开头（例如 /pages/index/index）')
    setMiniProgramTarget(e, appId, path)
  } else if (e.jumpType === 'WEBVIEW') {
    // 前端提前提示：避免后端拒绝导致“保存失败”（后端也会二次校验）
    const url = e.targetId
    const ok = /^https:\/\//.test(url) || /^http:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:|\/|$)/.test(url)
    if (!ok) return ElMessage.error('外链仅允许 https://（开发环境允许 localhost 回环）')
  } else {
    if (!e.targetId) return ElMessage.error('跳转目标必填')
  }
  upsertEntryLocal(e)
  const ok = await saveEntriesDraft()
  if (ok) entryDialogOpen.value = false
}

// -----------------------------
// Pages: Agg / Info (separated)
// -----------------------------
const aggPages = computed(() => pages.value.filter((x) => x.type === 'AGG_PAGE'))
const infoPages = computed(() => pages.value.filter((x) => x.type === 'INFO_PAGE'))

// Agg editor
type AggNavItem = { title: string; subtitle?: string; iconUrl?: string; jumpType: JumpType; targetId: string; enabled: boolean; sort: number }
type AggNavChild = { name: string; items: AggNavItem[] }
type AggNavGroup = { name: string; children?: AggNavChild[]; items?: AggNavItem[] }

const pageEditorOpen = ref(false)
const pageEditorKind = ref<'AGG' | 'INFO'>('AGG')
const pageEditorMode = ref<'create' | 'edit'>('create')
const pageEditorId = ref('')
const pagePublished = ref(false)

const aggLayout = ref<NavLayout>('TABS_LIST')
const aggTitle = ref('')
const aggGroupsTabs = ref<AggNavGroup[]>([])
const aggGroupsGrid = ref<Array<{ name: string; items: AggNavItem[] }>>([])

function resetAggForm() {
  aggLayout.value = 'TABS_LIST'
  aggTitle.value = ''
  aggGroupsTabs.value = []
  aggGroupsGrid.value = []
}

function openCreateAggPage() {
  pageEditorKind.value = 'AGG'
  pageEditorMode.value = 'create'
  pageEditorId.value = _defaultId('PAGE')
  pagePublished.value = false
  resetAggForm()
  pageEditorOpen.value = true
}

function openEditAggPage(row: PageItem) {
  pageEditorKind.value = 'AGG'
  pageEditorMode.value = 'edit'
  pageEditorId.value = row.id
  pagePublished.value = !!row.published
  const cfg = row.config || {}
  aggTitle.value = String(cfg?.title || '')
  const layout = String(cfg?.nav?.layout || 'TABS_LIST')
  aggLayout.value = layout === 'SIDEBAR_GRID' ? 'SIDEBAR_GRID' : 'TABS_LIST'
  const groups = Array.isArray(cfg?.nav?.groups) ? cfg.nav.groups : []
  if (aggLayout.value === 'SIDEBAR_GRID') {
    aggGroupsGrid.value = groups.map((g: any) => ({
      name: String(g?.name || ''),
      items: Array.isArray(g?.items) ? g.items : [],
    }))
  } else {
    aggGroupsTabs.value = groups.map((g: any) => ({
      name: String(g?.name || ''),
      children: Array.isArray(g?.children) ? g.children : [{ name: '', items: [] }],
    }))
  }
  pageEditorOpen.value = true
}

function addAggGroup() {
  if (aggLayout.value === 'SIDEBAR_GRID') {
    aggGroupsGrid.value.push({ name: '', items: [] })
    return
}
  aggGroupsTabs.value.push({ name: '', children: [{ name: '', items: [] }] })
}

function addAggChild(gi: number) {
  const g = aggGroupsTabs.value[gi]
  if (!g) return
  g.children = g.children || []
  g.children.push({ name: '', items: [] })
}

function addAggItemTabs(gi: number, ci: number) {
  const c = aggGroupsTabs.value?.[gi]?.children?.[ci]
  if (!c) return
  c.items = c.items || []
  c.items.push({ title: '', subtitle: '', jumpType: 'ROUTE', targetId: '', enabled: true, sort: (c.items.length + 1) * 10 })
}

function addAggItemGrid(gi: number) {
  const g = aggGroupsGrid.value?.[gi]
  if (!g) return
  g.items = g.items || []
  g.items.push({ title: '', subtitle: '', iconUrl: '', jumpType: 'ROUTE', targetId: '', enabled: true, sort: (g.items.length + 1) * 10 })
}

const aggIconUploading = ref<Record<string, boolean>>({})
async function uploadAggIcon(opts: { gi: number; ii: number; file: any }) {
  const raw: File | undefined = opts.file?.raw
  if (!raw) return ElMessage.error('请选择图片文件')
  const key = `${opts.gi}-${opts.ii}`
  aggIconUploading.value = { ...aggIconUploading.value, [key]: true }
  try {
    const url = await uploadImage(raw)
    const g = aggGroupsGrid.value[opts.gi]
    if (!g) return
    const it = g.items?.[opts.ii]
    if (!it) return
    it.iconUrl = url
    ElMessage.success('已上传')
  } catch (e: any) {
    ElMessage.error(e?.message ?? '上传失败')
  } finally {
    aggIconUploading.value = { ...aggIconUploading.value, [key]: false }
  }
}

function buildAggConfig(): any {
  const title = String(aggTitle.value || '').trim()
  const layout = aggLayout.value
  if (layout === 'SIDEBAR_GRID') {
    const groups = aggGroupsGrid.value.map((g) => ({
      name: String(g.name || '').trim(),
      items: (g.items || [])
        .slice()
        .map((it) => ({
          title: String(it.title || '').trim(),
          subtitle: String(it.subtitle || '').trim() || undefined,
          iconUrl: String((it as any).iconUrl || '').trim() || undefined,
          jumpType: String(it.jumpType || 'ROUTE'),
          targetId: String(it.targetId || '').trim(),
                              enabled: it.enabled !== false,
                              sort: Number(it.sort || 0),
                            }))
        .sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0)),
    }))
    return { title, nav: { layout: 'SIDEBAR_GRID', groups } }
    }

  const groups = aggGroupsTabs.value.map((g) => ({
      name: String(g.name || '').trim(),
      children: (g.children || []).map((c) => ({
      name: String(c.name || '').trim(), // 允许空，表示“全部”
        items: (c.items || [])
          .slice()
          .map((it) => ({
            title: String(it.title || '').trim(),
            subtitle: String(it.subtitle || '').trim() || undefined,
          iconUrl: String((it as any).iconUrl || '').trim() || undefined,
            jumpType: String(it.jumpType || 'ROUTE'),
            targetId: String(it.targetId || '').trim(),
            enabled: it.enabled !== false,
            sort: Number(it.sort || 0),
          }))
          .sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0)),
      })),
    }))
  return { title, nav: { layout: 'TABS_LIST', groups } }
}

function validateAggConfig(cfg: any): string | null {
  if (!cfg || typeof cfg !== 'object') return '配置不合法'
  const layout = String(cfg?.nav?.layout || 'TABS_LIST')
  const groups = Array.isArray(cfg?.nav?.groups) ? cfg.nav.groups : []
  if (groups.length === 0) return '至少需要 1 个分类'
  if (layout === 'SIDEBAR_GRID') {
    for (const [gi, g] of groups.entries()) {
      if (!String(g?.name || '').trim()) return `第 ${gi + 1} 个侧边栏分类名称必填`
      const items = Array.isArray(g?.items) ? g.items : []
      for (const [ii, it] of items.entries()) {
        if (!String(it?.title || '').trim()) return `「${g.name}」第 ${ii + 1} 个图标项标题必填`
        const jt = String(it?.jumpType || '')
        if (!['AGG_PAGE', 'INFO_PAGE', 'WEBVIEW', 'ROUTE', 'MINI_PROGRAM'].includes(jt)) return `「${g.name}」第 ${ii + 1} 个 jumpType 不合法`
        const tid = String(it?.targetId || '').trim()
        if (!tid) return `「${g.name}」第 ${ii + 1} 个 targetId 必填`
        if (jt === 'ROUTE') {
          const { path } = parseRouteTarget(tid)
          if (!path) return `「${g.name}」第 ${ii + 1} 个路由路径不能为空`
        }
        if (jt === 'MINI_PROGRAM') {
          const { appId } = parseMiniProgramTarget(tid)
          if (!appId) return `「${g.name}」第 ${ii + 1} 个其他小程序 appId 不能为空`
        }
      }
    }
    return null
  }
  for (const [gi, g] of groups.entries()) {
    if (!String(g?.name || '').trim()) return `第 ${gi + 1} 个一级分类名称必填`
    const children = Array.isArray(g?.children) ? g.children : []
    if (children.length === 0) return `「${g.name}」至少需要 1 个二级分类（名称可空表示“全部”）`
    for (const c of children) {
      const items = Array.isArray(c?.items) ? c.items : []
      for (const [ii, it] of items.entries()) {
        if (!String(it?.title || '').trim()) return `「${g.name}/${c?.name || '全部'}」第 ${ii + 1} 个条目标题必填`
        const jt = String(it?.jumpType || '')
        if (!['AGG_PAGE', 'INFO_PAGE', 'WEBVIEW', 'ROUTE', 'MINI_PROGRAM'].includes(jt))
          return `「${g.name}/${c?.name || '全部'}」第 ${ii + 1} 个 jumpType 不合法`
        const tid = String(it?.targetId || '').trim()
        if (!tid) return `「${g.name}/${c?.name || '全部'}」第 ${ii + 1} 个 targetId 必填`
        if (jt === 'ROUTE') {
          const { path } = parseRouteTarget(tid)
          if (!path) return `「${g.name}/${c?.name || '全部'}」第 ${ii + 1} 个路由路径不能为空`
        }
        if (jt === 'MINI_PROGRAM') {
          const { appId } = parseMiniProgramTarget(tid)
          if (!appId) return `「${g.name}/${c?.name || '全部'}」第 ${ii + 1} 个其他小程序 appId 不能为空`
        }
      }
    }
  }
  return null
}

// Info editor
type InfoBlock =
  | { type: 'cmsContent'; contentId: string; title?: string }

const infoTitle = ref('')
const infoBlocks = ref<InfoBlock[]>([])

// CMS 内容选择（事实更新：运行时小程序按 contentId 拉取）
type CmsContentRow = { id: string; title: string; status: string; updatedAt?: string | null; publishedAt?: string | null; summary?: string | null }
type CmsChannelRow = { id: string; name: string; status: string; sort: number }
const cmsPickerOpen = ref(false)
const cmsLoading = ref(false)
const cmsKeyword = ref('')
const cmsChannelId = ref('')
const cmsChannels = ref<CmsChannelRow[]>([])
const cmsRows = ref<CmsContentRow[]>([])
const cmsSelectedId = ref<string | null>(null)
const cmsTargetBlockIndex = ref<number | null>(null)

// Assets picker (image library)
type AssetRow = { id: string; url: string; originalFilename?: string | null; createdAt?: string | null }
const assetPickerOpen = ref(false)
const assetLoading = ref(false)
const assetKeyword = ref('')
const assetRows = ref<AssetRow[]>([])
const assetSelectedId = ref<string | null>(null)
const assetApply = ref<null | ((url: string) => void)>(null)

async function loadAssets() {
  assetLoading.value = true
  try {
    const data = await apiRequest<{ items: AssetRow[] }>('/admin/assets', {
      query: { kind: 'IMAGE', keyword: assetKeyword.value || undefined, page: 1, pageSize: 50 },
    })
    assetRows.value = data.items || []
  } catch (e: any) {
    ElMessage.error(formatApiError(e, '加载资产失败', '/admin/assets'))
    assetRows.value = []
  } finally {
    assetLoading.value = false
  }
}

function openAssetPicker(apply: (url: string) => void) {
  assetApply.value = apply
  assetKeyword.value = ''
  assetSelectedId.value = null
  assetPickerOpen.value = true
  loadAssets()
}

function confirmAssetPick() {
  const id = String(assetSelectedId.value || '').trim()
  if (!id) return ElMessage.error('请选择一张图片')
  const row = assetRows.value.find((x) => x.id === id) || null
  if (!row?.url) return ElMessage.error('图片 url 为空')
  const fn = assetApply.value
  if (fn) fn(String(row.url))
  assetPickerOpen.value = false
}

async function loadCmsChannels() {
  try {
    const data = await apiRequest<{ items: CmsChannelRow[] }>('/admin/cms/channels')
    cmsChannels.value = (data.items || [])
      .filter((x) => String(x.status || '') === 'ENABLED')
      .slice()
      .sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0))
  } catch {
    cmsChannels.value = []
  }
}

async function loadCmsContents() {
  cmsLoading.value = true
  try {
    const data = await apiRequest<{ items: CmsContentRow[]; page: number; pageSize: number; total: number }>('/admin/cms/contents', {
      query: {
        page: 1,
        pageSize: 50,
        keyword: cmsKeyword.value || undefined,
        channelId: cmsChannelId.value || undefined,
        scope: 'MINI_PROGRAM',
        status: 'PUBLISHED',
        includeContent: false,
      },
    })
    cmsRows.value = data.items || []
  } catch (e: any) {
    ElMessage.error(formatApiError(e, '加载 CMS 内容失败', '/admin/cms/contents'))
    cmsRows.value = []
  } finally {
    cmsLoading.value = false
  }
}

function addCmsBlock() {
  infoBlocks.value.push({ type: 'cmsContent', contentId: '', title: '' })
  cmsTargetBlockIndex.value = infoBlocks.value.length - 1
  cmsSelectedId.value = null
  cmsKeyword.value = ''
  cmsChannelId.value = ''
  cmsPickerOpen.value = true
  loadCmsChannels()
  loadCmsContents()
}

function openCmsPickerForBlock(idx: number) {
  cmsTargetBlockIndex.value = idx
  cmsSelectedId.value = null
  cmsKeyword.value = ''
  cmsChannelId.value = ''
  cmsPickerOpen.value = true
  loadCmsChannels()
  loadCmsContents()
}

function confirmCmsPick() {
  const idx = cmsTargetBlockIndex.value
  const id = String(cmsSelectedId.value || '').trim()
  if (idx === null || idx === undefined) return
  if (!id) return ElMessage.error('请选择一条 CMS 内容')
  const row = cmsRows.value.find((x) => x.id === id) || null
  const b = infoBlocks.value[idx] as any
  if (!b || b.type !== 'cmsContent') return
  b.contentId = id
  b.title = row ? String(row.title || '') : ''
  cmsPickerOpen.value = false
}

function resetInfoForm() {
  infoTitle.value = ''
  infoBlocks.value = []
}

function openCreateInfoPage() {
  pageEditorKind.value = 'INFO'
  pageEditorMode.value = 'create'
  pageEditorId.value = _defaultId('PAGE')
  pagePublished.value = false
  resetInfoForm()
  // 平台未上线：仅允许引用 CMS 内容（内容生产在“内容中心”）
  infoBlocks.value = [{ type: 'cmsContent', contentId: '', title: '' }]
  pageEditorOpen.value = true
}

function openEditInfoPage(row: PageItem) {
  pageEditorKind.value = 'INFO'
  pageEditorMode.value = 'edit'
  pageEditorId.value = row.id
  pagePublished.value = !!row.published
  const cfg = row.config || {}
  infoTitle.value = String(cfg?.title || '')
  const blocks = Array.isArray(cfg?.blocks) ? cfg.blocks : []
  infoBlocks.value = blocks
    .map((b: any) => {
      const t = String(b?.type || '')
      if (t === 'cmsContent') return { type: 'cmsContent', contentId: String(b?.contentId || ''), title: String(b?.title || '') } as InfoBlock
      return null
    })
    .filter(Boolean) as InfoBlock[]
  pageEditorOpen.value = true
}

function buildInfoConfig(): any {
  const title = String(infoTitle.value || '').trim()
  const blocks = (infoBlocks.value || []).map((b: any) => {
    if (b.type === 'cmsContent') return { type: 'cmsContent', contentId: String(b.contentId || '').trim(), title: String(b.title || '').trim() || undefined }
    return null
  })
  return { title, blocks: blocks.filter(Boolean) }
}

function validateInfoConfig(cfg: any): string | null {
  if (!cfg || typeof cfg !== 'object') return '配置不合法'
  if (!Array.isArray(cfg.blocks)) return 'blocks 必须是数组'
  // 最小：至少 1 个 block
  if (cfg.blocks.length === 0) return '请至少添加 1 个内容块（引用 CMS 内容）'
  for (const [i, b] of cfg.blocks.entries()) {
    const t = String(b?.type || '')
    if (t !== 'cmsContent') return `第 ${i + 1} 个 block 类型不支持（仅支持 cmsContent）`
    const cid = String(b?.contentId || '').trim()
    if (!cid) return `第 ${i + 1} 个 block：contentId 必填`
  }
  return null
}

async function savePageDraft(kind: 'AGG' | 'INFO') {
  try {
    const id = String(pageEditorId.value || '').trim()
    if (!id) throw new Error('页面ID 不能为空')
    const type = kind === 'AGG' ? 'AGG_PAGE' : 'INFO_PAGE'
    const config = kind === 'AGG' ? buildAggConfig() : buildInfoConfig()
    const err = kind === 'AGG' ? validateAggConfig(config) : validateInfoConfig(config)
    if (err) throw new Error(err)
    await apiRequest(`/admin/mini-program/pages/${id}`, { method: 'PUT', body: { type, config } })
    await loadPages()
    // 强确认：保存后立刻验证该 pageId 确实存在于当前后端页面库
    const exists = await ensureAdminPageExists(id)
    if (!exists) return false
    ElMessage.success('已保存草稿')
    return true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
    return false
  }
}

async function saveAndPublishPage(kind: 'AGG' | 'INFO') {
  const id = String(pageEditorId.value || '').trim()
  if (!id) return ElMessage.error('页面ID 不能为空')
  const ok = await savePageDraft(kind)
  if (!ok) return
  // 发布前二次确认：避免“保存到 A 环境，但发布请求打到 B 环境”导致 NOT_FOUND
  const exists = await ensureAdminPageExists(id)
  if (!exists) return
  try {
    await apiRequest(`/admin/mini-program/pages/${id}/publish`, { method: 'POST' })
    ElMessage.success('已发布（小程序读侧可见）')
    await loadPages()
    await openReadSidePage(id)
    pageEditorOpen.value = false
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlinePage(id: string) {
  try {
    await apiRequest(`/admin/mini-program/pages/${id}/offline`, { method: 'POST' })
    ElMessage.success('已下线')
    await loadPages()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

async function ensureAdminPageExists(id: string): Promise<boolean> {
  try {
    const data = await apiRequest<{ items: PageItem[]; version: string }>('/admin/mini-program/pages')
    const ok = (data.items || []).some((x) => String(x.id) === String(id))
    if (!ok) {
      ElMessage.error(
        `页面「${id}」在当前后端的页面库中不存在，无法发布。常见原因：你当前 Admin 页面请求的后端与保存时不是同一个（端口/代理/环境不一致）。请打开页面“诊断信息”确认 API Base/页面地址后重试。`,
      )
      return false
    }
    return true
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布前校验失败' })
    return false
  }
}

async function publishPage(id: string) {
  try {
    const exists = await ensureAdminPageExists(id)
    if (!exists) return
    await apiRequest(`/admin/mini-program/pages/${id}/publish`, { method: 'POST' })
    ElMessage.success('已发布（小程序读侧可见）')
    await loadPages()
    await openReadSidePage(id)
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

function previewCurrentPage() {
  const id = String(pageEditorId.value || '').trim() || '(未填写 pageId)'
  if (pageEditorKind.value === 'AGG') {
    const cfg = buildAggConfig()
    openTextPreview(`纯文本预览：${id}（AGG_PAGE）`, buildAggPreview(cfg))
    return
  }
  const cfg = buildInfoConfig()
  openTextPreview(`纯文本预览：${id}（INFO_PAGE）`, buildInfoPreview(cfg))
}

// -----------------------------
// advanced (collections/JSON) - minimal keep for compatibility
// -----------------------------
const colEditorOpen = ref(false)
const colEditId = ref('')
const colEditName = ref('')
const colEditSchemaJson = ref('{}')
const colEditItemsJson = ref('[]')
const colCreating = ref(false)

function openCreateCollection() {
  colEditId.value = _defaultId('COLLECTION')
  colEditName.value = ''
  colEditSchemaJson.value = '{}'
  colEditItemsJson.value = '[]'
  colCreating.value = true
  colEditorOpen.value = true
}

function openEditCollection(row: CollectionItem) {
  colEditId.value = row.id
  colEditName.value = row.name || ''
  colEditSchemaJson.value = JSON.stringify(row.schema ?? {}, null, 2)
  colEditItemsJson.value = JSON.stringify(row.items ?? [], null, 2)
  colCreating.value = false
  colEditorOpen.value = true
}

async function saveCollectionDraft() {
  try {
    const id = String(colEditId.value || '').trim()
    if (!id) throw new Error('集合ID 必填')
    const schema = JSON.parse(colEditSchemaJson.value || '{}')
    const items = JSON.parse(colEditItemsJson.value || '[]')
    await apiRequest(`/admin/mini-program/collections/${id}`, { method: 'PUT', body: { name: colEditName.value, schema, items } })
    ElMessage.success('已保存草稿')
    colEditorOpen.value = false
    await loadCollections()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

async function publishCollection(id: string) {
  try {
    await apiRequest(`/admin/mini-program/collections/${id}/publish`, { method: 'POST' })
    ElMessage.success('已发布')
    await loadCollections()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发布失败' })
  }
}

async function offlineCollection(id: string) {
  try {
    await apiRequest(`/admin/mini-program/collections/${id}/offline`, { method: 'POST' })
    ElMessage.success('已下线')
    await loadCollections()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '下线失败' })
  }
}

function toggleAdvanced(v: boolean) {
  showAdvanced.value = v
  if (v) {
    activeMain.value = 'advanced'
    loadRegions()
    loadCollections()
  } else {
    if (activeMain.value === 'advanced') activeMain.value = 'home'
  }
}

const uiBuildTag = 'MP_CONFIG_UI_V2_2025-12-21'

onMounted(async () => {
  await loadEntries()
  await loadPages()
  await loadMpRecommendations()
})
</script>

<template>
  <div>
    <PageHeaderBar title="小程序装修中心（运营）" />

    <el-card style="margin-top: 12px">
      <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom: 10px">
        <el-tag type="success">{{ uiBuildTag }}</el-tag>
      </div>
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>你只需要记住两件事</template>
        <div style="line-height: 1.7">
          <div>1）你在这里做的是：创建页面 → 给首页入口指向它。</div>
          <div>2）小程序只读取“已发布”的数据；所以请用“保存并发布”。</div>
          </div>
      </el-alert>

      <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom: 12px">
        <el-segmented
          v-model="activeMain"
          :options="[
            { label: '首页装修', value: 'home' },
            { label: '页面库', value: 'pages' },
            { label: '推荐管理', value: 'recommendations' },
            { label: '高级', value: 'advanced' },
          ]"
        />
        <div style="display:flex; align-items:center; gap:10px">
          <span style="font-size: 12px; color: rgba(0,0,0,.6)">高级模式</span>
          <el-switch v-model="showAdvanced" @change="toggleAdvanced" />
          </div>
        </div>

      <!-- 首页装修 -->
      <div v-if="activeMain === 'home'">
        <div style="display:flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px">
          <el-card style="flex: 1; min-width: 420px">
            <template #header>
              <div style="display:flex; justify-content: space-between; align-items:center">
                <div>Banner 管理</div>
                <div style="display:flex; gap:8px; align-items:center">
                  <el-button size="small" :loading="entriesLoading" @click="loadEntries">刷新</el-button>
                  <el-button size="small" type="primary" @click="openCreateBanner">新增 Banner</el-button>
          </div>
              </div>
            </template>

          <PageErrorState
            v-if="!entriesLoading && entriesError"
            :message="entriesError"
            :code="entriesErrorCode"
            :requestId="entriesErrorRequestId"
            @retry="loadEntries"
          />
            <PageEmptyState v-else-if="!entriesLoading && banners.length === 0" title="暂无 Banner" />

            <el-table v-else :data="banners" :loading="entriesLoading" size="small" style="width: 100%">
              <el-table-column prop="name" label="标题" min-width="180" />
              <el-table-column label="跳转" min-width="240">
                <template #default="scope">
                  <span>{{ jumpTypeLabel(scope.row.jumpType) }} → {{ entryTargetLabel(scope.row) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="sort" label="排序" width="90" />
              <el-table-column label="显示" width="110">
                <template #default="scope">
                  <el-switch v-model="scope.row.enabled" @change="saveEntriesDraft" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
              <template #default="scope">
                <el-button size="small" @click="openEditEntry(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="confirmDeleteEntry(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

            <div style="margin-top: 10px; display:flex; gap:8px; align-items:center; flex-wrap: wrap">
              <el-button type="success" :loading="entriesSaving" @click="saveAndPublishEntries">保存并发布</el-button>
              <el-button @click="openReadSideEntries">查看读侧</el-button>
              <el-button @click="openTextPreview('纯文本预览：Banner', buildEntriesPreview(entries, 'OPERATION'))">纯文本预览</el-button>
              <el-button type="warning" @click="offlineEntries">全量下线</el-button>
              <el-tag type="info">version={{ entriesVersion }}</el-tag>
            </div>
          </el-card>

          <el-card style="flex: 1; min-width: 420px">
            <template #header>
              <div style="display:flex; justify-content: space-between; align-items:center">
                <div>快捷入口管理</div>
                <div style="display:flex; gap:8px; align-items:center">
                  <el-button size="small" :loading="entriesLoading" @click="loadEntries">刷新</el-button>
                  <el-button size="small" type="primary" @click="openCreateShortcut">新增快捷入口</el-button>
                </div>
              </div>
            </template>

            <PageErrorState
              v-if="!entriesLoading && entriesError"
              :message="entriesError"
              :code="entriesErrorCode"
              :requestId="entriesErrorRequestId"
              @retry="loadEntries"
            />
            <PageEmptyState v-else-if="!entriesLoading && shortcuts.length === 0" title="暂无快捷入口" />

            <el-table v-else :data="shortcuts" :loading="entriesLoading" size="small" style="width: 100%">
              <el-table-column prop="name" label="名称" min-width="180" />
              <el-table-column label="跳转" min-width="240">
                <template #default="scope">
                  <span>{{ jumpTypeLabel(scope.row.jumpType) }} → {{ entryTargetLabel(scope.row) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="sort" label="排序" width="90" />
              <el-table-column label="显示" width="110">
                <template #default="scope">
                  <el-switch v-model="scope.row.enabled" @change="saveEntriesDraft" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
              <template #default="scope">
                <el-button size="small" @click="openEditEntry(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="confirmDeleteEntry(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

            <div style="margin-top: 10px; display:flex; gap:8px; align-items:center; flex-wrap: wrap">
              <el-button type="success" :loading="entriesSaving" @click="saveAndPublishEntries">保存并发布</el-button>
              <el-button @click="openReadSideEntries">查看读侧</el-button>
              <el-button @click="openTextPreview('纯文本预览：快捷入口', buildEntriesPreview(entries, 'SHORTCUT'))">纯文本预览</el-button>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 页面库 -->
      <div v-else-if="activeMain === 'pages'">
        <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom: 12px">
          <el-segmented v-model="activePages" :options="[{label:'聚合页',value:'agg'},{label:'信息页',value:'info'}]" />
          <div style="display:flex; gap: 8px">
            <el-button :loading="pagesLoading" @click="loadPages">刷新</el-button>
            <el-button v-if="activePages==='agg'" type="success" @click="openCreateAggPage">新增聚合页</el-button>
            <el-button v-else type="success" @click="openCreateInfoPage">新增信息页</el-button>
          </div>
          </div>

          <PageErrorState
            v-if="!pagesLoading && pagesError"
            :message="pagesError"
            :code="pagesErrorCode"
            :requestId="pagesErrorRequestId"
            @retry="loadPages"
          />

        <PageEmptyState
          v-else-if="!pagesLoading && (activePages==='agg' ? aggPages.length===0 : infoPages.length===0)"
          title="暂无页面"
          description="先创建页面，再把首页入口跳转指向它。"
        />

        <el-table v-else :data="activePages==='agg' ? aggPages : infoPages" :loading="pagesLoading" style="width: 100%">
          <el-table-column label="名称" min-width="240">
              <template #default="scope">
                <span>{{ pageLabel(scope.row.id) }}</span>
              </template>
            </el-table-column>
          <el-table-column prop="id" label="pageId（系统）" width="260" />
          <el-table-column label="发布" width="120">
              <template #default="scope">
              <el-tag :type="pageStatusText(scope.row).kind" size="small">{{ pageStatusText(scope.row).text }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="360">
            <template #default="scope">
              <el-button size="small" @click="activePages==='agg' ? openEditAggPage(scope.row) : openEditInfoPage(scope.row)">编辑</el-button>
              <el-button size="small" type="success" @click="publishPage(scope.row.id)">发布</el-button>
              <el-button size="small" type="warning" @click="offlinePage(scope.row.id)">下线</el-button>
              <el-tooltip v-if="!scope.row.published" content="读侧只返回已发布页面；未发布时会 404" placement="top">
                <el-button size="small" :disabled="true">读侧</el-button>
              </el-tooltip>
              <el-button v-else size="small" @click="openReadSidePage(scope.row.id)">读侧</el-button>
              </template>
            </el-table-column>
          </el-table>
      </div>

      <!-- 推荐管理（小程序端：推荐商品/推荐场所） -->
      <div v-else-if="activeMain === 'recommendations'">
        <el-alert type="info" show-icon :closable="false" style="margin-top: 12px">
          <template #title>小程序首页推荐（运营配置）</template>
          <div style="line-height: 1.7">
            <div>在这里控制小程序端“推荐商品/推荐场所”的展示与列表（仅可选择已上架/已发布项）。</div>
            <div style="color: var(--lh-muted); margin-top: 4px">保存后，小程序首页刷新即可生效。</div>
          </div>
        </el-alert>

        <el-card class="lh-card" style="margin-top: 12px" :loading="mpRecLoading">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap">
            <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap">
              <el-button size="small" :loading="mpRecLoading" @click="loadMpRecommendations">刷新</el-button>
              <span style="font-size: 12px; color: rgba(0, 0, 0, 0.55)">
                venuesVersion={{ mpRecVenuesVersion }} / productsVersion={{ mpRecProductsVersion }}
              </span>
            </div>
            <el-button type="primary" :loading="mpRecSaving" @click="saveMpRecommendations">保存</el-button>
          </div>

          <el-divider />

          <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center">
            <el-switch v-model="mpRecVenuesEnabled" active-text="推荐场所：展示" inactive-text="推荐场所：不展示" />
            <el-select
              v-model="mpRecNewVenueId"
              filterable
              remote
              clearable
              reserve-keyword
              :remote-method="searchMpRecVenues"
              :loading="mpRecVenueSearchLoading"
              placeholder="搜索并选择场所（仅 PUBLISHED）"
              style="max-width: 520px; width: 100%"
            >
              <el-option v-for="opt in mpRecVenueOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-button type="primary" plain @click="mpRecAddVenue">添加场所</el-button>
          </div>

          <el-table :data="mpRecVenues" row-key="venueId" border style="width: 100%; margin-top: 10px">
            <el-table-column type="index" width="60" label="#" />
            <el-table-column prop="venueId" label="场所ID" min-width="240" />
            <el-table-column prop="name" label="名称" min-width="200" />
            <el-table-column prop="publishStatus" label="状态" width="160" />
            <el-table-column label="操作" width="120">
              <template #default="{ $index }">
                <el-button size="small" type="danger" @click="mpRecVenues.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-divider />

          <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center">
            <el-switch v-model="mpRecProductsEnabled" active-text="推荐商品：展示" inactive-text="推荐商品：不展示" />
            <el-select
              v-model="mpRecNewProductId"
              filterable
              remote
              clearable
              reserve-keyword
              :remote-method="searchMpRecProducts"
              :loading="mpRecProductSearchLoading"
              placeholder="搜索并选择商品（仅 ON_SALE）"
              style="max-width: 520px; width: 100%"
            >
              <el-option v-for="opt in mpRecProductOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-button type="primary" plain @click="mpRecAddProduct">添加商品</el-button>
          </div>

          <el-table :data="mpRecProducts" row-key="productId" border style="width: 100%; margin-top: 10px">
            <el-table-column type="index" width="60" label="#" />
            <el-table-column prop="productId" label="商品ID" min-width="240" />
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column prop="status" label="状态" width="160" />
            <el-table-column label="操作" width="120">
              <template #default="{ $index }">
                <el-button size="small" type="danger" @click="mpRecProducts.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- 高级（默认隐藏） -->
      <div v-else>
        <el-alert v-if="!showAdvanced" type="warning" show-icon :closable="false">
          <template #title>高级模式已隐藏</template>
          <div style="line-height: 1.7; color: rgba(0,0,0,.65)">
            运营不需要编辑 schema/JSON。只有维护历史 collectionId 聚合页时才需要。
          </div>
        </el-alert>

        <div v-else>
          <div style="margin-bottom: 12px; display:flex; gap:8px">
            <el-button :loading="colsLoading" @click="loadCollections">刷新集合</el-button>
            <el-button type="success" @click="openCreateCollection">新增集合</el-button>
          </div>

          <PageErrorState
            v-if="!colsLoading && colsError"
            :message="colsError"
            :code="colsErrorCode"
            :requestId="colsErrorRequestId"
            @retry="loadCollections"
          />
          <PageEmptyState v-else-if="!colsLoading && cols.length === 0" title="暂无内容集合" />
          <el-table v-else :data="cols" :loading="colsLoading" style="width: 100%">
            <el-table-column prop="id" label="集合ID" width="260" />
            <el-table-column prop="name" label="名称" min-width="200" />
            <el-table-column prop="published" label="已发布" width="100" />
            <el-table-column label="操作" width="260">
              <template #default="scope">
                <el-button size="small" @click="openEditCollection(scope.row)">编辑</el-button>
                <el-button size="small" type="success" @click="publishCollection(scope.row.id)">发布</el-button>
                <el-button size="small" type="warning" @click="offlineCollection(scope.row.id)">下线</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-card>

    <!-- Entry dialog -->
    <el-dialog v-model="entryDialogOpen" :title="entryDialogTitle" width="760px">
      <el-form label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="entryForm.name" placeholder="运营可读名称" />
        </el-form-item>
        <el-form-item label="图片/图标（可选）">
          <div style="display:flex; gap:8px; align-items:center; width: 100%">
            <el-input v-model="entryForm.iconUrl" placeholder="可填 URL 或上传后地址；允许为空" />
            <el-upload :show-file-list="false" :auto-upload="false" :on-change="(f:any) => uploadEntryIcon(f)">
              <el-button size="small" :loading="entryIconUploading">上传</el-button>
            </el-upload>
            <el-button size="small" @click="openAssetPicker((url) => (entryForm.iconUrl = url))">资源库</el-button>
            <el-button size="small" @click="entryForm.iconUrl = ''">清空</el-button>
          </div>
        </el-form-item>
        <el-form-item label="跳转类型">
          <el-select v-model="entryForm.jumpType" style="width: 220px" @change="onEntryJumpTypeChange">
            <el-option label="聚合页" value="AGG_PAGE" />
            <el-option label="信息页" value="INFO_PAGE" />
            <el-option label="H5 外链" value="WEBVIEW" />
            <el-option label="其他小程序" value="MINI_PROGRAM" />
            <el-option label="小程序路由" value="ROUTE" />
          </el-select>
        </el-form-item>
        <el-form-item label="跳转目标">
          <template v-if="entryForm.jumpType === 'AGG_PAGE' || entryForm.jumpType === 'INFO_PAGE'">
            <el-select v-model="entryForm.targetId" filterable placeholder="选择页面" style="width: 520px">
              <el-option v-for="p in pagesForJumpType(entryForm.jumpType)" :key="p.id" :label="`${pageLabel(p.id)}（${p.type}）`" :value="p.id" />
            </el-select>
          </template>
          <template v-else-if="entryForm.jumpType === 'ROUTE'">
            <div style="display:flex; gap:8px; align-items:center; width: 100%">
              <el-select
                :model-value="parseRouteTarget(entryForm.targetId).path"
                filterable
                allow-create
                default-first-option
                placeholder="选择本小程序页面（可搜索）"
                style="flex: 1"
                @update:model-value="(v:any) => setRouteTarget(entryForm, String(v || ''), parseRouteTarget(entryForm.targetId).pairs)"
              >
                <el-option v-for="p in mpRouteOptions" :key="p" :label="p" :value="p" />
              </el-select>
              <el-button size="small" @click="openRouteParamEditor(entryForm, '入口：路由参数')">参数…</el-button>
              <el-button size="small" @click="entryForm.targetId = ''">清空</el-button>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">targetId 将保存为：/pages/xxx/xxx?key=value</div>
          </template>
          <template v-else-if="entryForm.jumpType === 'MINI_PROGRAM'">
            <div style="display:flex; gap:8px; align-items:center; width: 100%">
              <el-select
                :model-value="parseMiniProgramTarget(entryForm.targetId).appId"
                filterable
                allow-create
                default-first-option
                placeholder="选择/输入合作小程序 appId"
                style="width: 260px"
                @update:model-value="(v:any) => setMiniProgramTarget(entryForm, String(v || ''), parseMiniProgramTarget(entryForm.targetId).path)"
              >
                <el-option v-for="id in miniProgramAppIdOptions" :key="id" :label="id" :value="id" />
              </el-select>
              <el-input
                :model-value="parseMiniProgramTarget(entryForm.targetId).path"
                placeholder="path（可空，例如：/pages/index/index）"
                style="flex: 1"
                @update:model-value="(v:any) => setMiniProgramTarget(entryForm, parseMiniProgramTarget(entryForm.targetId).appId, String(v || ''))"
              />
              <el-button size="small" @click="entryForm.targetId = ''">清空</el-button>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">targetId 将保存为：appid|path（path 可为空）</div>
          </template>
          <template v-else>
            <el-input v-model="entryForm.targetId" :placeholder="targetPlaceholder(entryForm.jumpType)" />
          </template>
        </el-form-item>
        <el-form-item label="排序 / 显示">
          <div style="display:flex; gap:12px; align-items:center">
          <el-input-number v-model="entryForm.sort" :min="0" :max="9999" />
          <el-switch v-model="entryForm.enabled" />
          </div>
        </el-form-item>
        <el-form-item label="系统ID（高级）">
          <el-input v-model="entryForm.id" disabled />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">ID 默认隐藏概念；此处仅用于复制。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="entryDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="submitEntryDialog">保存</el-button>
      </template>
    </el-dialog>

    <!-- ROUTE params editor -->
    <el-dialog v-model="routeParamEditorOpen" :title="routeParamEditorTitle || '编辑路由参数'" width="820px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>提示</template>
        <div style="line-height: 1.7; color: rgba(0,0,0,.65)">
          这里编辑的是路由的 query 参数（即 <code>?key=value</code> 部分）。空 key 会被忽略；会自动拼接生成最终 targetId。
        </div>
      </el-alert>

      <el-form label-width="120px">
        <el-form-item label="路由 path">
          <el-input v-model="routeParamBasePath" placeholder="例如：/pages/venue-detail/venue-detail" />
        </el-form-item>
        <el-form-item label="参数列表">
          <div style="width: 100%">
            <el-table :data="routeParamPairs" size="small" border>
              <el-table-column label="key" min-width="220">
                <template #default="{ row }"><el-input v-model="row.key" placeholder="例如：id" /></template>
              </el-table-column>
              <el-table-column label="value" min-width="260">
                <template #default="{ row }"><el-input v-model="row.value" placeholder="例如：123" /></template>
              </el-table-column>
              <el-table-column label="操作" width="90">
                <template #default="{ $index }">
                  <el-button type="danger" link @click="routeParamPairs.splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top: 10px; display:flex; gap:8px; align-items:center; flex-wrap: wrap">
              <el-button size="small" @click="routeParamPairs.push({ key: '', value: '' })">新增参数</el-button>
              <el-tag type="info">预览：{{ normalizeRoutePath(routeParamBasePath) }}{{ buildQueryString(routeParamPairs) }}</el-tag>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="routeParamEditorOpen = false">取消</el-button>
        <el-button type="primary" @click="confirmRouteParamEditor">确定</el-button>
      </template>
    </el-dialog>

    <!-- Page editor -->
    <el-dialog v-model="pageEditorOpen" :title="pageEditorKind==='AGG' ? '编辑聚合页' : '编辑信息页'" width="920px">
      <el-form label-width="120px">
        <el-form-item label="页面名称">
          <el-input v-if="pageEditorKind==='AGG'" v-model="aggTitle" placeholder="例如：推荐商品/服务聚合" />
          <el-input v-else v-model="infoTitle" placeholder="例如：购买说明/文章详情" />
        </el-form-item>
        <el-form-item label="页面ID（系统）">
          <el-input v-model="pageEditorId" :disabled="pageEditorMode==='edit'" />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">仅用于系统引用；运营一般不需要关注。</div>
        </el-form-item>

        <!-- AGG -->
        <template v-if="pageEditorKind==='AGG'">
          <el-form-item label="布局">
            <el-radio-group v-model="aggLayout">
              <el-radio value="TABS_LIST">顶部标签 + 列表卡片</el-radio>
              <el-radio value="SIDEBAR_GRID">侧边栏 + 图标宫格</el-radio>
                    </el-radio-group>
                  </el-form-item>

          <el-form-item v-if="aggLayout==='TABS_LIST'" label="分类与条目">
                      <div style="width: 100%">
                        <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:8px">
                <div style="font-size: 12px; color: rgba(0,0,0,.6)">一级→二级（名称可空=全部）→条目</div>
                <el-button size="small" @click="addAggGroup">新增一级</el-button>
                        </div>

                        <div
                v-for="(g, gi) in aggGroupsTabs"
                          :key="gi"
                          style="border: 1px solid rgba(0,0,0,.08); border-radius: 10px; padding: 10px; margin-bottom: 10px"
                        >
                          <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px">
                            <el-input v-model="g.name" placeholder="一级分类名称（必填）" style="width: 260px" />
                  <el-button size="small" @click="addAggChild(gi)">新增二级</el-button>
                  <el-button size="small" type="danger" plain @click="aggGroupsTabs.splice(gi, 1)">删除一级</el-button>
                          </div>

                          <div
                            v-for="(c, ci) in g.children"
                            :key="ci"
                            style="border: 1px dashed rgba(0,0,0,.08); border-radius: 10px; padding: 10px; margin-bottom: 10px"
                          >
                            <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px">
                    <el-input v-model="c.name" placeholder="二级名称（可空=全部）" style="width: 260px" />
                    <el-button size="small" @click="addAggItemTabs(gi, ci)">新增条目</el-button>
                    <el-button size="small" type="danger" plain @click="g.children?.splice(ci, 1)" :disabled="(g.children||[]).length<=1">删除二级</el-button>
                            </div>

                            <el-table :data="c.items || []" size="small" border>
                    <el-table-column label="标题" min-width="200">
                      <template #default="{ row }"><el-input v-model="row.title" placeholder="标题" /></template>
                              </el-table-column>
                    <el-table-column label="副标题" min-width="200">
                                <template #default="{ row }"><el-input v-model="row.subtitle" placeholder="可选" /></template>
                              </el-table-column>
                    <el-table-column label="跳转类型" width="160">
                                <template #default="{ row }">
                        <el-select v-model="row.jumpType" style="width: 140px" @change="() => (row.targetId = '')">
                                    <el-option label="聚合页" value="AGG_PAGE" />
                                    <el-option label="信息页" value="INFO_PAGE" />
                          <el-option label="H5 外链" value="WEBVIEW" />
                                    <el-option label="其他小程序" value="MINI_PROGRAM" />
                                    <el-option label="小程序路由" value="ROUTE" />
                                  </el-select>
                                </template>
                              </el-table-column>
                    <el-table-column label="目标" min-width="260">
                                <template #default="{ row }">
                        <template v-if="row.jumpType==='AGG_PAGE' || row.jumpType==='INFO_PAGE'">
                          <el-select v-model="row.targetId" filterable placeholder="选择页面" style="width: 240px">
                            <el-option v-for="p in pagesForJumpType(row.jumpType)" :key="p.id" :label="`${pageLabel(p.id)}（${p.type}）`" :value="p.id" />
                          </el-select>
                        </template>
                        <template v-else-if="row.jumpType === 'ROUTE'">
                          <div style="display:flex; gap:6px; align-items:center">
                            <el-select
                              :model-value="parseRouteTarget(row.targetId).path"
                              filterable
                              allow-create
                              default-first-option
                              placeholder="选择页面"
                              style="width: 170px"
                              @update:model-value="(v:any) => setRouteTarget(row, String(v || ''), parseRouteTarget(row.targetId).pairs)"
                            >
                              <el-option v-for="p in mpRouteOptions" :key="p" :label="p" :value="p" />
                            </el-select>
                            <el-button size="small" @click="openRouteParamEditor(row, '聚合页条目：路由参数')">参数…</el-button>
                          </div>
                        </template>
                        <template v-else-if="row.jumpType === 'MINI_PROGRAM'">
                          <div style="display:flex; flex-direction: column; gap:6px">
                            <el-select
                              :model-value="parseMiniProgramTarget(row.targetId).appId"
                              filterable
                              allow-create
                              default-first-option
                              placeholder="appId"
                              style="width: 240px"
                              @update:model-value="(v:any) => setMiniProgramTarget(row, String(v || ''), parseMiniProgramTarget(row.targetId).path)"
                            >
                              <el-option v-for="id in miniProgramAppIdOptions" :key="id" :label="id" :value="id" />
                            </el-select>
                            <el-input
                              :model-value="parseMiniProgramTarget(row.targetId).path"
                              placeholder="path（可空）"
                              @update:model-value="(v:any) => setMiniProgramTarget(row, parseMiniProgramTarget(row.targetId).appId, String(v || ''))"
                            />
                          </div>
                        </template>
                        <template v-else>
                          <el-input v-model="row.targetId" :placeholder="targetPlaceholder(row.jumpType)" />
                        </template>
                                </template>
                              </el-table-column>
                              <el-table-column label="排序" width="90">
                                <template #default="{ row }"><el-input-number v-model="row.sort" :min="0" :max="9999" /></template>
                              </el-table-column>
                              <el-table-column label="启用" width="80">
                                <template #default="{ row }"><el-switch v-model="row.enabled" /></template>
                              </el-table-column>
                    <el-table-column label="操作" width="80">
                                <template #default="{ $index }">
                                  <el-button type="danger" link @click="c.items.splice($index, 1)">删除</el-button>
                                </template>
                              </el-table-column>
                            </el-table>
                          </div>
                        </div>
                      </div>
                    </el-form-item>

          <el-form-item v-else label="侧边栏分类与图标项">
            <div style="width: 100%">
              <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:8px">
                <div style="font-size: 12px; color: rgba(0,0,0,.6)">仅一级分类；每个分类下维护图标宫格项</div>
                <el-button size="small" @click="addAggGroup">新增分类</el-button>
                      </div>

              <div
                v-for="(g, gi) in aggGroupsGrid"
                :key="gi"
                style="border: 1px solid rgba(0,0,0,.08); border-radius: 10px; padding: 10px; margin-bottom: 10px"
              >
                <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px">
                  <el-input v-model="g.name" placeholder="侧边栏分类名称（必填）" style="width: 260px" />
                  <el-button size="small" @click="addAggItemGrid(gi)">新增图标项</el-button>
                  <el-button size="small" type="danger" plain @click="aggGroupsGrid.splice(gi, 1)">删除分类</el-button>
                </div>

                <el-table :data="g.items || []" size="small" border>
                  <el-table-column label="图标（可选）" min-width="340">
                    <template #default="{ row, $index }">
                      <div style="display:flex; gap:8px; align-items:center">
                        <el-input v-model="row.iconUrl" placeholder="可填 URL 或上传后地址；允许留空" />
                        <el-upload :show-file-list="false" :auto-upload="false" :on-change="(f:any) => uploadAggIcon({ gi, ii: $index, file: f })">
                          <el-button size="small" :loading="!!aggIconUploading[`${gi}-${$index}`]">上传</el-button>
                        </el-upload>
                        <el-button size="small" @click="openAssetPicker((url) => (row.iconUrl = url))">资源库</el-button>
                        <el-button size="small" @click="row.iconUrl = ''">清空</el-button>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="标题" min-width="200">
                    <template #default="{ row }"><el-input v-model="row.title" placeholder="标题" /></template>
                  </el-table-column>
                  <el-table-column label="跳转类型" width="160">
                    <template #default="{ row }">
                      <el-select v-model="row.jumpType" style="width: 140px" @change="() => (row.targetId = '')">
                        <el-option label="聚合页" value="AGG_PAGE" />
                        <el-option label="信息页" value="INFO_PAGE" />
                        <el-option label="H5 外链" value="WEBVIEW" />
                        <el-option label="其他小程序" value="MINI_PROGRAM" />
                        <el-option label="小程序路由" value="ROUTE" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="目标" min-width="260">
                    <template #default="{ row }">
                      <template v-if="row.jumpType==='AGG_PAGE' || row.jumpType==='INFO_PAGE'">
                        <el-select v-model="row.targetId" filterable placeholder="选择页面" style="width: 240px">
                          <el-option v-for="p in pagesForJumpType(row.jumpType)" :key="p.id" :label="`${pageLabel(p.id)}（${p.type}）`" :value="p.id" />
                      </el-select>
                  </template>
                      <template v-else-if="row.jumpType === 'ROUTE'">
                        <div style="display:flex; gap:6px; align-items:center">
                          <el-select
                            :model-value="parseRouteTarget(row.targetId).path"
                            filterable
                            allow-create
                            default-first-option
                            placeholder="选择页面"
                            style="width: 170px"
                            @update:model-value="(v:any) => setRouteTarget(row, String(v || ''), parseRouteTarget(row.targetId).pairs)"
                          >
                            <el-option v-for="p in mpRouteOptions" :key="p" :label="p" :value="p" />
                          </el-select>
                          <el-button size="small" @click="openRouteParamEditor(row, '聚合页条目：路由参数')">参数…</el-button>
                        </div>
                      </template>
                      <template v-else-if="row.jumpType === 'MINI_PROGRAM'">
                        <div style="display:flex; flex-direction: column; gap:6px">
                          <el-select
                            :model-value="parseMiniProgramTarget(row.targetId).appId"
                            filterable
                            allow-create
                            default-first-option
                            placeholder="appId"
                            style="width: 240px"
                            @update:model-value="(v:any) => setMiniProgramTarget(row, String(v || ''), parseMiniProgramTarget(row.targetId).path)"
                          >
                            <el-option v-for="id in miniProgramAppIdOptions" :key="id" :label="id" :value="id" />
                          </el-select>
                          <el-input
                            :model-value="parseMiniProgramTarget(row.targetId).path"
                            placeholder="path（可空）"
                            @update:model-value="(v:any) => setMiniProgramTarget(row, parseMiniProgramTarget(row.targetId).appId, String(v || ''))"
                          />
                        </div>
                      </template>
                      <template v-else>
                        <el-input v-model="row.targetId" :placeholder="targetPlaceholder(row.jumpType)" />
                      </template>
                    </template>
                  </el-table-column>
                  <el-table-column label="排序" width="90">
                    <template #default="{ row }"><el-input-number v-model="row.sort" :min="0" :max="9999" /></template>
                  </el-table-column>
                  <el-table-column label="启用" width="80">
                    <template #default="{ row }"><el-switch v-model="row.enabled" /></template>
                  </el-table-column>
                  <el-table-column label="操作" width="80">
                    <template #default="{ $index }">
                      <el-button type="danger" link @click="g.items.splice($index, 1)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
                  </el-form-item>
        </template>

        <!-- INFO -->
        <template v-else>
          <el-form-item label="Blocks">
            <div style="width: 100%">
              <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:8px">
                <div style="font-size: 12px; color: rgba(0,0,0,.6)">
                  信息页仅支持引用 CMS 内容（内容生产在“内容中心”，小程序端按 contentId 实时拉取）
                </div>
                <div style="display:flex; gap:8px">
                  <el-button size="small" @click="addCmsBlock">引用 CMS 内容</el-button>
                </div>
                </div>

                <div
                v-for="(b, idx) in infoBlocks"
                  :key="idx"
                  style="border: 1px solid rgba(0,0,0,.08); border-radius: 10px; padding: 10px; margin-bottom: 10px"
                >
                <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:8px">
                  <el-tag>{{ (b as any).type }}</el-tag>
                  <el-button size="small" type="danger" plain @click="infoBlocks.splice(idx, 1)">删除</el-button>
                  </div>

                <div v-if="(b as any).type === 'cmsContent'">
                  <div style="display:flex; gap:8px; align-items:center; margin-bottom: 8px">
                    <el-input v-model="(b as any).contentId" placeholder="contentId（从 CMS 选择）" style="flex: 1" />
                    <el-button size="small" @click="openCmsPickerForBlock(idx)">选择</el-button>
                    <el-tag v-if="(b as any).title" type="info">{{ (b as any).title }}</el-tag>
                  </div>
                  <el-alert type="info" show-icon :closable="false">
                    <template #title>事实更新</template>
                    <div style="line-height: 1.7; color: rgba(0,0,0,.65)">
                      小程序端会按 contentId 实时拉取已发布内容并渲染；CMS 内容变更后无需重新发布该信息页。
                    </div>
                  </el-alert>
                </div>

                <div v-else>
                  <el-alert type="warning" show-icon :closable="false">
                    <template #title>不支持的内容块</template>
                    <div style="line-height: 1.7; color: rgba(0,0,0,.65)">
                      信息页目前只支持引用 CMS（cmsContent）。请删除该 block 后重新保存。
                    </div>
                  </el-alert>
                </div>
            </div>
          </div>
        </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="pageEditorOpen = false">关闭</el-button>
        <el-button @click="previewCurrentPage">纯文本预览</el-button>
        <el-button type="primary" @click="savePageDraft(pageEditorKind==='AGG' ? 'AGG' : 'INFO')">保存草稿</el-button>
        <el-button type="success" @click="saveAndPublishPage(pageEditorKind==='AGG' ? 'AGG' : 'INFO')">保存并发布</el-button>
      </template>
    </el-dialog>

    <!-- Advanced: collection editor -->
    <el-dialog v-model="colEditorOpen" title="编辑集合（高级）" width="900px">
      <el-form label-width="110px">
        <el-form-item label="集合ID">
          <el-input v-model="colEditId" :disabled="!colCreating" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="colEditName" />
        </el-form-item>
        <el-form-item label="schema(JSON)">
          <el-input v-model="colEditSchemaJson" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="items(JSON)">
          <el-input v-model="colEditItemsJson" type="textarea" :rows="10" />
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0,0,0,.6)">
            高级模式：仅用于历史 collectionId 聚合页；运营模式不需要。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="colEditorOpen = false">取消</el-button>
        <el-button type="primary" @click="saveCollectionDraft">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- read-side -->
    <el-dialog v-model="readSideOpen" :title="readSideTitle" width="860px">
      <el-input v-model="readSideJson" type="textarea" :rows="20" readonly />
      <template #footer>
        <el-button @click="readSideOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- text preview -->
    <el-dialog v-model="textPreviewOpen" :title="textPreviewTitle" width="860px">
      <el-input v-model="textPreviewContent" type="textarea" :rows="20" readonly />
      <template #footer>
        <el-button @click="textPreviewOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- CMS picker -->
    <el-dialog v-model="cmsPickerOpen" title="选择 CMS 内容（已发布到小程序）" width="860px">
      <div style="display:flex; gap:8px; align-items:center; margin-bottom: 10px; flex-wrap: wrap">
        <el-select v-model="cmsChannelId" placeholder="栏目（全部）" style="width: 220px" @change="loadCmsContents">
          <el-option label="全部栏目" value="" />
          <el-option v-for="c in cmsChannels" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-input v-model="cmsKeyword" placeholder="按标题/摘要搜索" style="flex: 1; min-width: 240px" @keyup.enter="loadCmsContents" />
        <el-button :loading="cmsLoading" @click="loadCmsContents">搜索</el-button>
      </div>
      <el-table :data="cmsRows" :loading="cmsLoading" height="420">
        <el-table-column width="50">
          <template #default="scope">
            <el-radio v-model="cmsSelectedId" :label="scope.row.id"><span></span></el-radio>
                </template>
              </el-table-column>
        <el-table-column prop="title" label="标题" min-width="260" />
        <el-table-column prop="id" label="contentId" width="320" />
        <el-table-column prop="updatedAt" label="更新时间" width="200" :formatter="fmtBeijingDateTime" />
            </el-table>
      <template #footer>
        <el-button @click="cmsPickerOpen = false">取消</el-button>
        <el-button type="primary" @click="confirmCmsPick">确定</el-button>
      </template>
    </el-dialog>

    <!-- Assets picker -->
    <el-dialog v-model="assetPickerOpen" title="选择图片（资源库）" width="860px">
      <div style="display:flex; gap:8px; align-items:center; margin-bottom: 10px">
        <el-input v-model="assetKeyword" placeholder="按文件名/url/sha256 搜索" style="flex: 1" @keyup.enter="loadAssets" />
        <el-button :loading="assetLoading" @click="loadAssets">搜索</el-button>
      </div>
      <el-table :data="assetRows" :loading="assetLoading" height="420">
        <el-table-column width="50">
          <template #default="scope">
            <el-radio v-model="assetSelectedId" :label="scope.row.id"><span></span></el-radio>
          </template>
        </el-table-column>
        <el-table-column label="预览" width="120">
          <template #default="scope">
            <img :src="scope.row.url" alt="img" style="width: 96px; height: 64px; object-fit: cover; border-radius: 8px; border: 1px solid rgba(0,0,0,.08)" />
          </template>
        </el-table-column>
        <el-table-column prop="originalFilename" label="文件名" min-width="220" />
        <el-table-column prop="url" label="URL" min-width="320" />
        <el-table-column prop="createdAt" label="创建时间" width="200" :formatter="fmtBeijingDateTime" />
      </el-table>
      <template #footer>
        <el-button @click="assetPickerOpen = false">取消</el-button>
        <el-button type="primary" @click="confirmAssetPick">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>



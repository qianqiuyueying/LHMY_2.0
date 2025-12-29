// pages/index/index.js
// 首页

const api = require('../../utils/api')
const app = getApp()
const { computeDisplayPrice } = require('../../utils/price')
const { navigateByJump } = require('../../utils/navigate')
const _cfg = require('../../utils/config') || {}
const getApiBaseUrl = _cfg.getApiBaseUrl || (_cfg.default && _cfg.default.getApiBaseUrl)

function _absStaticUrl(raw) {
  let u = String(raw || '').trim()
  if (!u) return ''
  if (u.startsWith('http://') || u.startsWith('https://')) return u
  // 兼容：运营侧/人工粘贴时可能写成 "static/..."（缺少前导 /）
  if (u.startsWith('static/')) u = `/${u}`
  if (!u.startsWith('/static/')) return u
  const base = String(getApiBaseUrl() || '').trim().replace(/\/$/, '')
  if (!base) return u
  return `${base}${u}`
}

function _stripDefaultVenueSuffix(name) {
  const s = String(name || '').trim()
  // 来源定位：后端 admin 创建 Provider 时会同步创建 Venue(name="${providerName}（默认场所）")
  // 这里仅做展示侧归一化，不改变真实数据。
  return s.replace(/（默认场所）$/g, '').trim()
}

Page({
  data: {
    // v1：保留城市配置读取（供未来扩展/后台控制）；REQ-MP-P1-001 移除首页顶部入口按钮
    currentCity: '全国',
    currentCityCode: null,
    cities: [],
    
    // Banner列表
    banners: [],
    // Banner 图片加载失败标记（避免出现“空白但无反馈”）
    bannerImageError: {},
    
    // 快捷入口列表（来自后台配置）
    entries: [],
    entriesAll: [],
    hasMoreEntries: false,
    
    // 推荐商品
    recommendedProducts: [],
    
    // 推荐场所
    recommendedVenues: [],
    
    // 是否显示AI旋钮
    showAiButton: true,

    // 首页搜索关键词（事实清单：跳转商城并传递关键词）
    searchKeyword: '',

    // 页面状态：避免“静默失败=空白页”
    pageState: 'loading', // loading/ready/error
    pageErrorMessage: '',
    pageEmptyHint: ''
  },

  onLoad() {
    this.loadCitiesConfig().finally(() => {
      this.loadPageData()
    })
  },

  onShow() {
    // 自定义 TabBar：每次显示时同步选中态
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tabBar && tabBar.setData) {
      tabBar.setData({ selected: 0 })
    }

    // 每次显示时刷新用户信息
    if (app.globalData.userInfo) {
      this.setData({
        userInfo: app.globalData.userInfo
      })
    }

    // 登录态变化后，刷新价格显示（不额外打接口）
    this.refreshPriceDisplays()
  },

  onPullDownRefresh() {
    this.loadPageData().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 加载页面数据
  async loadPageData() {
    try {
      this.setData({ pageState: 'loading', pageErrorMessage: '', pageEmptyHint: '' })
      // 并行加载所有数据（使用 Promise.allSettled 确保单个失败不影响其他）
      const [entriesResult, productsResult, venuesResult] = await Promise.allSettled([
        this.loadEntries(),
        this.loadRecommendedProducts(),
        this.loadRecommendedVenues()
      ])
      
      const entriesOk = entriesResult.status === 'fulfilled'
      const productsOk = productsResult.status === 'fulfilled'
      const venuesOk = venuesResult.status === 'fulfilled'

      // 提取结果，失败时使用空数组（但保留失败信息，用于展示错误态）
      const entries = entriesOk ? (entriesResult.value || []) : []
      const products = productsOk ? (productsResult.value || []) : []
      const venues = venuesOk ? (venuesResult.value || []) : []
      
      // 首页 Banner：position="OPERATION" 的 entries（当前 UI 使用占位块，不依赖 iconUrl）
      const banners = entries
        .filter((x) => x && x.position === 'OPERATION')
        .map((x) => ({
          id: x.id,
          // 兼容：后端读侧契约是 iconUrl；这里也容错支持 imageUrl（避免历史/手工数据导致不显示）
          imageUrl: x.iconUrl || x.imageUrl,
          imageUrlAbs: _absStaticUrl(x.iconUrl || x.imageUrl),
          // 兼容：历史数据/手工写入可能使用 snake_case
          jumpType: x.jumpType || x.jump_type,
          targetId: x.targetId || x.target_id,
          name: x.name,
        }))

      // 快捷入口：position="SHORTCUT"
      const shortcuts = entries.filter((x) => x && x.position === 'SHORTCUT')
      const displayedShortcuts = shortcuts.slice(0, 8).map((x) => ({
        ...x,
        iconUrlAbs: _absStaticUrl(x.iconUrl),
      }))
      const hasMoreEntries = shortcuts.length > displayedShortcuts.length

      this.setData({
        banners,
        entries: displayedShortcuts,
        entriesAll: shortcuts.map((x) => ({ ...x, iconUrlAbs: _absStaticUrl(x.iconUrl) })),
        hasMoreEntries,
        recommendedProducts: this.normalizeProducts(products),
        recommendedVenues: this.normalizeVenues(venues),
      })
      
      // 1) 全部失败：显示错误态（不允许静默空白）
      if (!entriesOk && !productsOk && !venuesOk) {
        this.setData({
          pageState: 'error',
          pageErrorMessage: '暂时无法加载首页内容，请检查网络或稍后重试。',
        })
        return
      }

      // 2) 有接口成功但整体无内容：显示空态解释（不再让用户面对空白区域）
      if (entries.length === 0 && products.length === 0 && venues.length === 0) {
        this.setData({
          pageState: 'ready',
          pageEmptyHint: '暂无可展示内容',
        })
        return
      }

      this.setData({ pageState: 'ready' })
    } catch (error) {
      // 异常：显示错误态（不允许静默空白）
      this.setData({
        pageState: 'error',
        pageErrorMessage: '加载失败，请稍后重试。',
      })
    }
  },

  onRetryTap() {
    this.loadPageData()
  },

  onSupportTap() {
    wx.navigateTo({ url: '/pages/support/support' })
  },

  // 加载快捷入口配置
  async loadEntries() {
    // silent=true：不弹 toast，但失败仍 reject（用于首页决定是否展示错误态）
    const data = await api.get('/api/v1/mini-program/entries', {}, false, true)
    return data?.items || []
  },

  // 加载推荐商品
  async loadRecommendedProducts() {
    // 读侧：小程序首页推荐商品（由管理端配置）
    const data = await api.get('/api/v1/mini-program/home/recommended-products', {}, false, true)
    if (data?.enabled === false) return []
    return data?.items || []
  },

  // 加载推荐场所
  async loadRecommendedVenues() {
    // 读侧：小程序首页推荐场所（由管理端配置）
    const data = await api.get('/api/v1/mini-program/home/recommended-venues', {}, false, true)
    if (data?.enabled === false) return []
    return data?.items || []
  },

  normalizeProducts(items) {
    const identities = app.globalData.userInfo?.identities || []
    return (items || []).map((p) => {
      const computed = computeDisplayPrice(p.price, identities)
      return {
        ...p,
        coverImageUrlAbs: _absStaticUrl(p.coverImageUrl),
        displayPrice: computed.displayPrice,
        hasMemberPrice: computed.hasMemberPrice,
        hasEmployeePrice: computed.hasEmployeePrice,
        hasActivityPrice: computed.hasActivityPrice,
      }
    })
  },

  normalizeVenues(items) {
    const cities = Array.isArray(this.data.cities) ? this.data.cities : []
    const cityNameByCode = new Map(cities.map((x) => [String(x.code || ''), String(x.name || '')]))

    return (items || []).map((v) => {
      const cityCode = String(v.cityCode || '').trim()
      const cityName = cityNameByCode.get(cityCode) || ''
      const rawName = String(v.name || '').trim()
      const displayName = _stripDefaultVenueSuffix(rawName) || rawName

      return {
        ...v,
        nameDisplay: displayName,
        cityName,
        tags: Array.isArray(v.tags) ? v.tags.filter((x) => !!String(x || '').trim()) : [],
        coverImageUrlAbs: _absStaticUrl(v.coverImageUrl),
      }
    })
  },

  refreshPriceDisplays() {
    if (!Array.isArray(this.data.recommendedProducts) || this.data.recommendedProducts.length === 0) return
    this.setData({ recommendedProducts: this.normalizeProducts(this.data.recommendedProducts) })
  },

  async loadCitiesConfig() {
    try {
      const data = await api.get('/api/v1/regions/cities', {}, false, true)
      // REGION_CITIES 读侧可能同时包含 PROVINCE/CITY；小程序首页仅使用 CITY 作为筛选维度
      const cities = (data?.items || [])
        .filter((x) => String(x?.code || '').startsWith('CITY:'))
        .slice()
        .sort((a, b) => (a.sort || 0) - (b.sort || 0))

      const stored = wx.getStorageSync('selectedCity') || null
      let selected = stored

      if (!selected && data?.defaultCode) {
        const found = cities.find((x) => x.code === data.defaultCode)
        if (found) selected = found
      }

      if (selected) {
        wx.setStorageSync('selectedCity', selected)
        this.setData({ currentCity: selected.name, currentCityCode: selected.code })
      }

      this.setData({ cities })
    } catch (e) {
      // 静默失败：保持“全国”
    }
  },

  // 搜索
  onSearch() {
    const kw = String(this.data.searchKeyword || '').trim()
    wx.navigateTo({ url: `/pages/search/search?keyword=${encodeURIComponent(kw)}` })
  },

  onSearchInput(e) {
    this.setData({ searchKeyword: e.detail.value })
  },

  onSearchConfirm() {
    this.onSearch()
  },

  // 快捷入口点击
  onEntryTap(e) {
    const { item } = e.currentTarget.dataset
    if (!item) return

    navigateByJump({ jumpType: item.jumpType, targetId: item.targetId, title: item.name })
  },

  onMoreEntriesTap() {
    try {
      // 简化：用 storage 传递（避免 URL 过长/序列化风险）
      wx.setStorageSync('mp_entries_all', this.data.entriesAll || [])
    } catch (e) {}
    wx.navigateTo({ url: '/pages/index/entries-more/entries-more' })
  },

  // Banner 点击：复用 entries 的跳转逻辑
  onBannerTap(e) {
    const { item } = e.currentTarget.dataset
    if (!item) return
    navigateByJump({ jumpType: item.jumpType, targetId: item.targetId, title: item.name })
  },

  onBannerImageLoad(e) {
    const { item } = e.currentTarget.dataset
    if (!item) return
  },

  onBannerImageError(e) {
    const { item } = e.currentTarget.dataset
    const err = e?.detail || {}
    const id = String(item?.id || '').trim()
    if (!id) return
    const next = { ...(this.data.bannerImageError || {}) }
    next[id] = true
    this.setData({ bannerImageError: next })
  },

  // 商品点击
  onProductTap(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/mall/product-detail/product-detail?id=${id}`
    })
  },

  // 场所点击
  onVenueTap(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/venue-detail/venue-detail?id=${id}`
    })
  },

  // AI旋钮点击
  onAiButtonTap() {
    // 检查登录状态
    if (!app.globalData.token) {
      wx.showModal({
        title: '提示',
        content: '使用AI对话需要先登录',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/profile/profile' })
          }
        }
      })
      return
    }

    wx.navigateTo({
      url: '/pages/ai-chat/ai-chat'
    })
  }
})

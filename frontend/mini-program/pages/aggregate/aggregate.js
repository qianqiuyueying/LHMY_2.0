// pages/aggregate/aggregate.js
// 聚合页（可配置）

const api = require('../../utils/api')
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

function parseRegionLevel(code) {
  if (!code || typeof code !== 'string') return null
  const idx = code.indexOf(':')
  if (idx <= 0) return null
  return code.slice(0, idx)
}

Page({
  data: {
    pageId: null,
    pageConfig: null, // AGG_PAGE 的 config（collectionId/defaultRegionLevel/defaultRegionCode/defaultTaxonomyId 等）
    // vNow：NAV 模式（一级/二级标签 + 跳转卡片）
    navMode: false,
    navLayout: 'TABS_LIST', // TABS_LIST / SIDEBAR_GRID
    navGroups: [],
    navL1Index: 0,
    navL2Index: 0,
    navItems: [],
    // 侧边栏维度
    dimension: 'CITY', // CITY/PROVINCE/COUNTRY
    selectedRegion: null,
    selectedRegionLevel: null,
    taxonomyId: null,
    regionsEmpty: false,
    items: [],
    loading: true,
    errorMessage: '',
    emptyMessage: ''
  },

  onLoad(options) {
    if (options.pageId) {
      this.setData({ pageId: options.pageId })
      this.loadPageConfig()
    }
  },

  // 加载页面配置
  async loadPageConfig() {
    try {
      this.setData({ loading: true, errorMessage: '', emptyMessage: '' })
      const resp = await api.get(`/api/v1/mini-program/pages/${this.data.pageId}`, {}, false)
      const config = resp?.config || null

      if (!config) {
        this.setData({
          loading: false,
          errorMessage: '页面配置不存在或不可用',
        })
        return
      }

      // vNow：若配置为 NAV 模式，直接渲染导航聚合，不再加载 collection
      const navGroups = config?.nav?.groups
      if (Array.isArray(navGroups) && navGroups.length > 0) {
        const layout = String(config?.nav?.layout || 'TABS_LIST').trim().toUpperCase()
        this.setData({
          pageConfig: config,
          navMode: true,
          navLayout: layout === 'SIDEBAR_GRID' ? 'SIDEBAR_GRID' : 'TABS_LIST',
          navGroups,
          navL1Index: 0,
          navL2Index: 0,
          loading: false,
          regionsEmpty: true,
          items: [],
          emptyMessage: ''
        })
        this.refreshNavItems()
        return
      }

      const storedCity = wx.getStorageSync('selectedCity') || null
      const fallbackRegionCode = storedCity?.code || null
      const fallbackRegionLevel = parseRegionLevel(fallbackRegionCode)

      const defaultRegionCode = config?.defaultRegionCode || null
      const defaultRegionLevel = config?.defaultRegionLevel || parseRegionLevel(defaultRegionCode) || fallbackRegionLevel || 'CITY'
      const selectedRegion = defaultRegionCode || fallbackRegionCode || null

      this.setData({
        pageConfig: config,
        dimension: defaultRegionLevel,
        selectedRegion,
        selectedRegionLevel: selectedRegion ? (parseRegionLevel(selectedRegion) || defaultRegionLevel) : null,
        taxonomyId: config?.defaultTaxonomyId || null,
        regionsEmpty: !Array.isArray(config?.regions) || config.regions.length === 0,
        loading: false
      })
      this.loadItems()
    } catch (error) {
      console.error('加载页面配置失败:', error)
      this.setData({
        loading: false,
        errorMessage: '加载失败，请稍后重试',
      })
    }
  },

  refreshNavItems() {
    const groups = this.data.navGroups || []
    const g = groups[this.data.navL1Index] || null
    let items = []

    if (this.data.navLayout === 'SIDEBAR_GRID') {
      // SIDEBAR_GRID：仅一级分类，items 在 group.items
      if (g && Array.isArray(g.items)) items = g.items
      // 兼容旧结构：如果没有 items，但有 children，则取第一个 children 的 items
      if ((!items || items.length === 0) && g && Array.isArray(g.children) && g.children[0] && Array.isArray(g.children[0].items)) {
        items = g.children[0].items
      }
    } else {
      // TABS_LIST：一级/二级
      const children = (g && Array.isArray(g.children)) ? g.children : []
      const c = children[this.data.navL2Index] || null
      if (c && Array.isArray(c.items)) items = c.items
      // 兼容“无二级”：若 children 为空但 group.items 存在，则直接用 group.items
      if ((!items || items.length === 0) && g && Array.isArray(g.items)) items = g.items
    }

    const filtered = items.filter((x) => x && x.enabled !== false)
    this.setData({
      navItems: filtered.map((x) => ({
        ...x,
        iconUrlAbs: _absStaticUrl(x.iconUrl),
      })),
      emptyMessage: items.length === 0 ? '暂无可展示内容' : ''
    })
  },

  // 加载聚合数据
  async loadItems() {
    try {
      const collectionId = this.data.pageConfig?.collectionId
      if (!collectionId) {
        this.setData({ emptyMessage: '暂无可展示内容' })
        return
      }

      const params = {
        page: 1,
        pageSize: 20,
      }

      if (this.data.selectedRegion) {
        const level = parseRegionLevel(this.data.selectedRegion) || this.data.selectedRegionLevel || this.data.dimension || 'CITY'
        params.regionLevel = level
        params.regionCode = this.data.selectedRegion
      }

      if (this.data.taxonomyId) {
        params.taxonomyId = this.data.taxonomyId
      }

      const data = await api.get(`/api/v1/mini-program/collections/${collectionId}/items`, params, false)
      this.setData({
        items: data?.items || [],
        emptyMessage: (data?.items || []).length === 0 ? '暂无可展示内容' : ''
      })
    } catch (error) {
      console.error('加载聚合数据失败:', error)
      // v1：数据加载失败也应让用户可理解
      this.setData({ errorMessage: '加载失败，请稍后重试' })
    }
  },

  onRetryTap() {
    this.loadPageConfig()
  },

  onBackTap() {
    wx.navigateBack()
  },

  // 选择地区
  onRegionTap(e) {
    const { region } = e.currentTarget.dataset
    const code = region && typeof region === 'object' ? region.code : region
    this.setData({ selectedRegion: code || null, selectedRegionLevel: parseRegionLevel(code) || null })
    this.loadItems()
  },

  onNavL1Tap(e) {
    const idx = Number(e.currentTarget.dataset.index || 0)
    this.setData({ navL1Index: idx, navL2Index: 0 })
    this.refreshNavItems()
  },

  onNavL2Tap(e) {
    const idx = Number(e.currentTarget.dataset.index || 0)
    this.setData({ navL2Index: idx })
    this.refreshNavItems()
  },

  onNavItemTap(e) {
    const { item } = e.currentTarget.dataset
    if (!item) return
    navigateByJump({ jumpType: item.jumpType, targetId: item.targetId, title: item.title })
  }
})

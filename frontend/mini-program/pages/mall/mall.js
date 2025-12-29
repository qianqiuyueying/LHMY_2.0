// pages/mall/mall.js
// 商城 - 商品列表

const api = require('../../utils/api')
const { computeDisplayPrice } = require('../../utils/price')
const app = getApp()
const _cfg = require('../../utils/config') || {}
const getApiBaseUrl = _cfg.getApiBaseUrl || (_cfg.default && _cfg.default.getApiBaseUrl)

const NEXT_KEYWORD_KEY = 'mp_mall_next_keyword'

function _absStaticUrl(raw) {
  const u = String(raw || '').trim()
  if (!u) return ''
  if (u.startsWith('http://') || u.startsWith('https://')) return u
  if (!u.startsWith('/static/')) return u
  const base = String(getApiBaseUrl() || '').trim().replace(/\/$/, '')
  if (!base) return u
  return `${base}${u}`
}

Page({
  data: {
    // 搜索关键词
    keyword: '',
    
    // 分类筛选
    categoryId: null,
    categories: [],
    
    // 商品列表
    products: [],
    
    // 分页
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,

    pageState: 'loading', // loading/ready/error
    errorMessage: ''
  },

  onLoad(options) {
    if (options.keyword) {
      this.setData({ keyword: options.keyword })
    }
    if (options.categoryId) {
      this.setData({ categoryId: options.categoryId })
    }
    
    this.loadCategories()
    this.loadProducts(true)
  },

  onShow() {
    // 自定义 TabBar：每次显示时同步选中态
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tabBar && tabBar.setData) {
      tabBar.setData({ selected: 1 })
    }

    // 从搜索页接收 keyword（TabBar 页无法带 query）
    let nextKw = ''
    try {
      nextKw = String(wx.getStorageSync(NEXT_KEYWORD_KEY) || '').trim()
    } catch (e) {}
    if (nextKw) {
      try {
        wx.removeStorageSync(NEXT_KEYWORD_KEY)
      } catch (e) {}
      if (String(this.data.keyword || '') !== nextKw) {
        this.setData({ keyword: nextKw, page: 1, hasMore: true })
        this.loadProducts(true)
      }
    }
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadProducts(true).finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadProducts(false)
    }
  },

  // 加载分类
  async loadCategories() {
    try {
      const data = await api.get('/api/v1/product-categories', {}, false)
      this.setData({ categories: data?.items || [] })
    } catch (error) {
      console.error('加载分类失败:', error)
    }
  },

  // 加载商品列表
  async loadProducts(refresh = false) {
    if (this.data.loading) return
    
    this.setData({ loading: true })
    
    try {
      if (refresh) {
        this.setData({ pageState: 'loading', errorMessage: '' })
      }
      const params = {
        page: refresh ? 1 : this.data.page,
        pageSize: this.data.pageSize
      }
      
      if (this.data.keyword) {
        params.keyword = this.data.keyword
      }
      if (this.data.categoryId) {
        params.categoryId = this.data.categoryId
      }
      
      const data = await api.get('/api/v1/products', params, false)
      const identities = app.globalData.userInfo?.identities || []
      const items = (data?.items || []).map((p) => {
        const computed = computeDisplayPrice(p.price, identities)
        const cover = p.coverImageUrl || (Array.isArray(p.imageUrls) ? p.imageUrls[0] : '') || ''
        return {
          ...p,
          displayPrice: computed.displayPrice,
          hasMemberPrice: computed.hasMemberPrice,
          hasEmployeePrice: computed.hasEmployeePrice,
          hasActivityPrice: computed.hasActivityPrice,
          coverImageUrlAbs: _absStaticUrl(cover),
        }
      })
      
      if (refresh) {
        this.setData({
          products: items,
          page: 2,
          hasMore: items.length >= this.data.pageSize,
          pageState: 'ready',
          errorMessage: ''
        })
      } else {
        this.setData({
          products: [...this.data.products, ...items],
          page: this.data.page + 1,
          hasMore: items.length >= this.data.pageSize
        })
      }
    } catch (error) {
      console.error('加载商品失败:', error)
      if (refresh) {
        this.setData({
          pageState: 'error',
          errorMessage: '加载失败，请稍后重试',
        })
      } else {
        wx.showToast({ title: '加载失败', icon: 'none' })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  onRetryTap() {
    this.setData({ page: 1, hasMore: true })
    this.loadProducts(true)
  },

  // 搜索
  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  onSearchConfirm() {
    this.setData({ page: 1, hasMore: true })
    this.loadProducts(true)
  },

  // 选择分类
  onCategoryTap(e) {
    const { id } = e.currentTarget.dataset
    this.setData({ 
      categoryId: id === this.data.categoryId ? null : id,
      page: 1,
      hasMore: true
    })
    this.loadProducts(true)
  },

  // 商品点击
  onProductTap(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/mall/product-detail/product-detail?id=${id}`
    })
  }
})

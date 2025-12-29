// pages/venue-detail/venue-detail.js
// 场所详情

const api = require('../../utils/api')
const app = getApp()
const { computeDisplayPrice } = require('../../utils/price')
const _cfg = require('../../utils/config') || {}
const getApiBaseUrl = _cfg.getApiBaseUrl || (_cfg.default && _cfg.default.getApiBaseUrl)

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
    venueId: null,
    venue: null,
    loading: true,
    cityNameMap: {},
    cityName: '',
    coverImageUrlAbs: '',
    products: [],
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ venueId: options.id })
      this.loadVenueDetail()
    }
  },

  async loadCities() {
    try {
      const data = await api.get('/api/v1/regions/cities', {}, false, true)
      const items = data?.items || []
      const map = {}
      items.forEach((x) => {
        const code = String(x?.code || '').trim()
        if (!code) return
        map[code] = String(x?.name || '').trim()
      })
      this.setData({ cityNameMap: map })
    } catch (e) {
      this.setData({ cityNameMap: {} })
    }
  },

  // 加载场所详情
  async loadVenueDetail() {
    try {
      await this.loadCities()
      // v1 固化：不新增 /services，统一使用 venues/{id}.services
      // 且 services 仅在登录后返回（未登录时允许为空数组）
      const needAuth = !!(app.globalData.token || wx.getStorageSync('token'))
      const venue = await api.get(`/api/v1/venues/${this.data.venueId}`, {}, needAuth)

      const cityCode = String(venue?.cityCode || '').trim()
      const cityName = (this.data.cityNameMap || {})[cityCode] || ''
      const cover = String(venue?.coverImageUrl || '').trim()
      const coverImageUrlAbs = _absStaticUrl(cover)

      this.setData({ venue, cityName, coverImageUrlAbs })

      // v2：场所详情展示该 Provider 的全部商品/服务（无需登录，走商品列表 read side）
      const providerId = String(venue?.providerId || '').trim()
      if (providerId) {
        const data = await api.get('/api/v1/products', { providerId, page: 1, pageSize: 50 }, false)
        const identities = app.globalData.userInfo?.identities || []
        const items = (data?.items || []).map((p) => {
          const computed = computeDisplayPrice(p.price, identities)
          const pCover = p.coverImageUrl || (Array.isArray(p.imageUrls) ? p.imageUrls[0] : '') || ''
          return {
            ...p,
            displayPrice: computed.displayPrice,
            coverImageUrlAbs: _absStaticUrl(pCover),
          }
        })
        this.setData({ products: items })
      } else {
        this.setData({ products: [] })
      }

      this.setData({
        loading: false
      })
    } catch (error) {
      console.error('加载场所详情失败:', error)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  onProductTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return
    wx.navigateTo({ url: `/pages/mall/product-detail/product-detail?id=${id}` })
  },
})

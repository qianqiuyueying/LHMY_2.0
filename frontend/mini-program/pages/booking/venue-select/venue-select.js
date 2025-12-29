// pages/booking/venue-select/venue-select.js
// 场所选择页

const api = require('../../../utils/api')
const _cfg = require('../../../utils/config') || {}
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
    entitlementId: null,
    entitlement: null,
    venues: [],
    selectedVenueId: null,
    loading: true,
    cityNameMap: {},
  },

  onLoad(options) {
    if (options.entitlementId) {
      this.setData({ entitlementId: options.entitlementId })
    }
    if (options.venueId) {
      this.setData({ selectedVenueId: options.venueId })
    }
    this.loadEntitlementAndVenues()
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

  async loadEntitlementAndVenues() {
    try {
      await this.loadCities()
      if (!this.data.entitlementId) {
        this.setData({ loading: false })
        wx.showModal({
          title: '无法继续',
          content: '请选择一张可用权益后再查看可预约场所。',
          confirmText: '去权益',
          cancelText: '返回',
          success: (res) => {
            if (res.confirm) {
              wx.switchTab({ url: '/pages/entitlement/entitlement' })
            } else {
              wx.navigateBack()
            }
          },
        })
        return
      }

      const entitlement = await api.get(`/api/v1/entitlements/${this.data.entitlementId}`)
      this.setData({ entitlement })
      await this.loadVenues()
    } catch (error) {
      console.error('加载权益/场所失败:', error)
      this.setData({ loading: false })
    }
  },

  // 加载可用场所
  async loadVenues() {
    try {
      const params = {}
      if (this.data.entitlementId) {
        params.entitlementId = this.data.entitlementId
      }
      // design.md：taxonomyId v1 最小口径等同 “serviceType”
      if (this.data.entitlement?.serviceType) {
        params.taxonomyId = this.data.entitlement.serviceType
      }

      const data = await api.get('/api/v1/venues', params, true)
      const map = this.data.cityNameMap || {}
      const items = (data?.items || []).map((v) => {
        const cover = String(v?.coverImageUrl || '').trim()
        return {
          ...v,
          coverImageUrlAbs: _absStaticUrl(cover),
          cityName: map[String(v?.cityCode || '').trim()] || '',
        }
      })
      this.setData({
        venues: items,
        loading: false
      })
    } catch (error) {
      console.error('加载场所列表失败:', error)
      this.setData({ loading: false })
    }
  },

  // 选择场所
  onVenueTap(e) {
    const { id } = e.currentTarget.dataset
    this.setData({ selectedVenueId: id })
    
    // 跳转到日期时段选择页
    const serviceType = this.data.entitlement?.serviceType ? encodeURIComponent(this.data.entitlement.serviceType) : ''
    wx.navigateTo({
      url: `/pages/booking/date-slot-select/date-slot-select?venueId=${id}&entitlementId=${this.data.entitlementId || ''}&serviceType=${serviceType}`
    })
  }
})

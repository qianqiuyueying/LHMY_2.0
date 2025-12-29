// pages/profile/enterprise-bind/enterprise-bind.js
// 企业绑定

const api = require('../../../utils/api')
const app = getApp()

Page({
  data: {
    enterpriseName: '',
    enterpriseId: null,
    cities: [],
    cityIndex: 0,
    selectedCityCode: '',
    selectedCityName: '',
    suggestions: [],
    showSuggestions: false
  },

  onLoad() {
    // 加载已绑定企业信息
    this.loadEnterpriseInfo()
    this.loadCitiesConfig()
  },

  async loadCitiesConfig() {
    try {
      const data = await api.get('/api/v1/regions/cities', {}, false, true)
      const cities = (data?.items || [])
        .filter((x) => String(x?.code || '').startsWith('CITY:'))
        .slice()
        .sort((a, b) => (a.sort || 0) - (b.sort || 0))

      let selected = null
      try { selected = wx.getStorageSync('selectedCity') || null } catch (e) {}

      if (!selected && data?.defaultCode) {
        selected = cities.find((x) => x.code === data.defaultCode) || null
      }

      let idx = 0
      if (selected) {
        const foundIdx = cities.findIndex((x) => x.code === selected.code)
        if (foundIdx >= 0) idx = foundIdx
      }

      const pick = cities[idx] || null
      this.setData({
        cities,
        cityIndex: idx,
        selectedCityCode: pick?.code || '',
        selectedCityName: pick?.name || '',
      })
    } catch (e) {
      console.warn('加载城市配置失败:', e)
    }
  },

  onCityChange(e) {
    const idx = Number(e?.detail?.value || 0)
    const item = (this.data.cities || [])[idx] || null
    if (!item) return
    try { wx.setStorageSync('selectedCity', item) } catch (e) {}
    this.setData({
      cityIndex: idx,
      selectedCityCode: item.code || '',
      selectedCityName: item.name || '',
    })
  },

  // 加载企业信息
  async loadEnterpriseInfo() {
    try {
      const userInfo = await api.get('/api/v1/users/profile')
      if (userInfo.enterpriseName) {
        this.setData({
          enterpriseName: userInfo.enterpriseName
        })
      }
    } catch (error) {
      console.error('加载企业信息失败:', error)
    }
  },

  // 输入企业名称
  onEnterpriseNameInput(e) {
    const value = e.detail.value
    // 输入变化后清除已选 enterpriseId，避免“换了名字但还带旧 id”
    this.setData({ enterpriseName: value, enterpriseId: null })
    
    if (value.length >= 2) {
      this.loadSuggestions(value)
    } else {
      this.setData({ suggestions: [], showSuggestions: false })
    }
  },

  // 加载匹配建议
  async loadSuggestions(keyword) {
    try {
      const data = await api.get('/api/v1/auth/enterprise-suggestions', {
        keyword
      })
      this.setData({
        suggestions: data?.items || [],
        showSuggestions: true
      })
    } catch (error) {
      console.error('加载企业建议失败:', error)
    }
  },

  // 选择建议
  onSelectSuggestion(e) {
    const { item } = e.currentTarget.dataset
    this.setData({
      enterpriseName: item.name,
      enterpriseId: item.id || null,
      // 若建议里带 cityCode，则以建议为准；否则保留用户手动选择
      selectedCityCode: item.cityCode || this.data.selectedCityCode,
      suggestions: [],
      showSuggestions: false
    })
  },

  // 提交绑定
  async onSubmit() {
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    if (!this.data.enterpriseName.trim()) {
      wx.showToast({
        title: '请输入企业名称',
        icon: 'none'
      })
      return
    }

    const cityCode = String(this.data.selectedCityCode || '').trim()
    if (!cityCode) {
      wx.showToast({ title: '请选择城市', icon: 'none' })
      return
    }

    try {
      const data = await api.post('/api/v1/auth/bind-enterprise', {
        enterpriseName: this.data.enterpriseName,
        enterpriseId: this.data.enterpriseId || null,
        cityCode,
      })

      wx.showToast({
        title: '绑定申请已提交，等待审核',
        icon: 'success'
      })

      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (error) {
      console.error('提交绑定失败:', error)
      wx.showToast({
        title: error.message || '提交失败',
        icon: 'none'
      })
    }
  }
})

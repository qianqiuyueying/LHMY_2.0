// pages/support/support.js

const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    loading: true,
    errorMessage: '',
    items: [],
    termsText: '',
    openIndex: -1,
  },

  onLoad() {
    this.loadFaq()
  },

  async loadFaq() {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const data = await api.get('/api/v1/h5/landing/faq-terms', {}, false)
      const items = Array.isArray(data?.items) ? data.items : []
      const termsText = String(data?.termsText || '')
      this.setData({
        loading: false,
        items,
        termsText,
        openIndex: items.length ? 0 : -1,
      })
    } catch (e) {
      this.setData({
        loading: false,
        errorMessage: '加载失败，请稍后重试',
      })
    }
  },

  onToggleItem(e) {
    const idx = Number(e.currentTarget.dataset.index)
    if (Number.isNaN(idx)) return
    this.setData({ openIndex: this.data.openIndex === idx ? -1 : idx })
  },

  onCopyDiagnostics() {
    const apiBaseUrl = app.globalData.apiBaseUrl || ''
    const hasToken = !!(app.globalData.token || wx.getStorageSync('token'))
    const lastApiEvent = wx.getStorageSync('lastApiEvent') || null
    const now = new Date().toISOString()

    const text = [
      'LHMY Mini Program Diagnostics',
      `time=${now}`,
      `apiBaseUrl=${apiBaseUrl}`,
      `hasToken=${hasToken}`,
      lastApiEvent ? `lastApiEvent=${JSON.stringify(lastApiEvent)}` : 'lastApiEvent=none',
    ].join('\n')

    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },

  onBackTap() {
    wx.navigateBack()
  },
})

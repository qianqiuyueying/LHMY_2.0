// pages/legal/agreement/agreement.js
const api = require('../../../utils/api')
const app = getApp()

Page({
  data: {
    code: 'MP_LOGIN_AGREEMENT',
    title: '',
    version: '0',
    loading: false,
    error: '',
    contentHtml: '',
    mode: '',
    canAccept: false,
    canContinueLogin: false,
    accepting: false,
  },

  onLoad(query) {
    const code = String(query?.code || 'MP_LOGIN_AGREEMENT').trim() || 'MP_LOGIN_AGREEMENT'
    const mode = String(query?.mode || '').trim()
    const accepted = !!wx.getStorageSync('mp_login_agreement_accepted')
    const hasToken = !!(app.globalData.token || wx.getStorageSync('token'))
    const isLoginMode = mode === 'login' && code === 'MP_LOGIN_AGREEMENT' && !hasToken
    const canAccept = isLoginMode && !accepted
    const canContinueLogin = isLoginMode && accepted
    this.setData({ code, mode, canAccept, canContinueLogin })
    this.loadAgreement()
  },

  onShow() {
    // 处理“退出登录后返回协议页/再次进入协议页”的状态刷新
    try {
      const accepted = !!wx.getStorageSync('mp_login_agreement_accepted')
      const hasToken = !!(app.globalData.token || wx.getStorageSync('token'))
      const isLoginMode = this.data.mode === 'login' && this.data.code === 'MP_LOGIN_AGREEMENT' && !hasToken
      this.setData({
        canAccept: isLoginMode && !accepted,
        canContinueLogin: isLoginMode && accepted,
      })
    } catch (e) {}
  },

  async loadAgreement() {
    this.setData({ loading: true, error: '' })
    try {
      const data = await api.get(`/api/v1/legal/${encodeURIComponent(this.data.code)}`, false)
      const title = String(data?.title || '服务协议')
      const version = String(data?.version || '0')
      const html = String(data?.contentHtml || '')
      // 与 info 页一致：rich-text 直接接收 HTML 字符串（后端已将 Markdown 转安全 HTML）
      this.setData({
        title,
        version,
        contentHtml: html || '<p>暂无协议内容</p>',
      })
    } catch (e) {
      this.setData({ error: '加载失败，请稍后重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onRetry() {
    this.loadAgreement()
  },

  onDecline() {
    wx.navigateBack({ delta: 1 })
  },

  async onAcceptAndLogin() {
    if (!this.data.canAccept) return
    if (this.data.accepting) return
    this.setData({ accepting: true })
    try {
      wx.setStorageSync('mp_login_agreement_accepted', true)
      wx.showLoading({ title: '登录中...', mask: true })
      await app.login()
      wx.hideLoading()
      wx.showToast({ title: '已同意并登录', icon: 'success' })
      // profile 是 tab 页，用 switchTab 保持一致
      wx.switchTab({ url: '/pages/profile/profile' })
    } catch (e) {
      try { wx.hideLoading() } catch (_) {}
      wx.showToast({ title: e?.message || '登录失败', icon: 'none' })
    } finally {
      this.setData({ accepting: false, canAccept: false, canContinueLogin: false })
    }
  },

  async onContinueLogin() {
    if (!this.data.canContinueLogin) return
    if (this.data.accepting) return
    this.setData({ accepting: true })
    try {
      wx.showLoading({ title: '登录中...', mask: true })
      await app.login()
      wx.hideLoading()
      wx.showToast({ title: '登录成功', icon: 'success' })
      wx.switchTab({ url: '/pages/profile/profile' })
    } catch (e) {
      try { wx.hideLoading() } catch (_) {}
      wx.showToast({ title: e?.message || '登录失败', icon: 'none' })
    } finally {
      this.setData({ accepting: false, canContinueLogin: false })
    }
  },
})



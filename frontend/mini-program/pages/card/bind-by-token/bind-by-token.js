// pages/card/bind-by-token/bind-by-token.js
// 通过 bind_token 绑定卡（v1）

const api = require('../../../utils/api')
const app = getApp()

Page({
  data: {
    token: '',
    loading: false,
  },

  onLoad(options) {
    const token = String(options?.token || '').trim()
    this.setData({ token })
    if (!token) {
      wx.showToast({ title: '缺少 token', icon: 'none' })
    }
  },

  onGoProfile() {
    // profile 是 Tab 页，使用 switchTab
    wx.switchTab({ url: '/pages/profile/profile' })
  },

  async onBind() {
    const token = String(this.data.token || '').trim()
    if (!token) return

    const mpToken = app.globalData.token || wx.getStorageSync('token')
    if (!mpToken) {
      wx.showModal({
        title: '提示',
        content: '请先登录小程序后再绑定',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) this.onGoProfile()
        },
      })
      return
    }

    this.setData({ loading: true })
    try {
      const res = await api.post('/api/v1/mini-program/cards/bind-by-token', { token }, true, {}, false)
      const already = !!res?.alreadyBound
      wx.showModal({
        title: '绑定成功',
        content: already ? '该卡已绑定到当前账号（无需重复绑定）。' : '卡已绑定到当前账号，可在“权益”中查看。',
        showCancel: false,
        confirmText: '去查看权益',
        success: () => {
          wx.switchTab({ url: '/pages/entitlement/entitlement' })
        },
      })
    } catch (e) {
      // api.js 已按非 silent 展示 toast，这里只兜底
      console.error('bind-by-token failed', e)
    } finally {
      this.setData({ loading: false })
    }
  },
})



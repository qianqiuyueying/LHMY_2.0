// pages/profile/profile-edit/profile-edit.js
// 个人资料（vNow：集中维护头像/昵称/手机号/企业绑定入口）

const api = require('../../../utils/api')
const app = getApp()

Page({
  data: {
    userInfo: null,
    isEmployee: false,
    nicknameDraft: '',
    avatarLocal: '',
    avatarPreview: '',
    saving: false,
  },

  _ensureApiBaseUrlOrGuide() {
    const base = String(app.globalData.apiBaseUrl || '').trim()
    if (base) return true
    wx.showModal({
      title: '未配置后端地址',
      content:
        '当前未配置 apiBaseUrl（release 环境必须配置）。\n\n你可以在开发者工具 Storage 中设置：key=apiBaseUrl，value=你的后端地址（如 https://xxx.com）。',
      showCancel: false,
      confirmText: '知道了',
    })
    return false
  },

  _toAbsoluteUrl(maybePath) {
    const x = String(maybePath || '').trim()
    if (!x) return ''
    if (x.startsWith('http://') || x.startsWith('https://')) return x
    const base = String(app.globalData.apiBaseUrl || '').trim()
    if (!base) return x
    return `${base}${x.startsWith('/') ? x : `/${x}`}`
  },

  onLoad() {
    this.loadUserProfile()
  },

  async loadUserProfile() {
    if (!this._ensureApiBaseUrlOrGuide()) return
    const token = app.globalData.token || wx.getStorageSync('token')
    if (!token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 300)
      return
    }
    try {
      const userInfo = await api.get('/api/v1/users/profile')
      const isEmployee = userInfo?.identities?.includes('EMPLOYEE') || false
      this.setData({
        userInfo: { ...(userInfo || {}), avatar: this._toAbsoluteUrl(userInfo?.avatar) || userInfo?.avatar || null },
        isEmployee,
        nicknameDraft: String(userInfo?.nickname || '').trim(),
        avatarLocal: '',
        avatarPreview: '',
      })
    } catch (e) {
      wx.showToast({ title: e?.message || '加载失败', icon: 'none' })
    }
  },

  onChooseAvatar(e) {
    const p = String(e?.detail?.avatarUrl || '').trim()
    if (!p) return
    this.setData({ avatarLocal: p, avatarPreview: p })
  },

  onNicknameInput(e) {
    const v = String(e?.detail?.value || '')
    this.setData({ nicknameDraft: v })
  },

  onBindPhone() {
    if (!app.globalData.token) {
      wx.showToast({
        title: '请先登录',
        icon: 'none'
      })
      return
    }

    wx.showModal({
      title: '输入手机号',
      content: '',
      editable: true,
      placeholderText: '请输入手机号',
      success: async (res) => {
        if (res.confirm && res.content) {
          const phone = String(res.content || '').trim()
          if (!/^1\d{10}$/.test(phone)) {
            wx.showToast({ title: '请输入正确的11位手机号', icon: 'none' })
            return
          }

          try {
            await api.post('/api/v1/auth/request-sms-code', {
              phone,
              scene: 'MP_BIND_PHONE'
            }, false)

            wx.showModal({
              title: '输入验证码',
              content: '',
              editable: true,
              placeholderText: '请输入验证码',
              success: async (verifyRes) => {
                if (verifyRes.confirm && verifyRes.content) {
                  try {
                    const smsCode = String(verifyRes.content || '').trim()
                    await api.post('/api/v1/mini-program/auth/bind-phone', {
                      phone,
                      smsCode
                    })
                    wx.showToast({
                      title: '绑定成功',
                      icon: 'success'
                    })
                    this.loadUserProfile()
                  } catch (error) {
                    wx.showToast({
                      title: '绑定失败',
                      icon: 'none'
                    })
                  }
                }
              }
            })
          } catch (error) {
            wx.showToast({
              title: '发送验证码失败',
              icon: 'none'
            })
          }
        }
      }
    })
  },

  onEnterpriseBind() {
    wx.navigateTo({ url: '/pages/profile/enterprise-bind/enterprise-bind' })
  },

  async onSave() {
    if (this.data.saving) return
    if (!this._ensureApiBaseUrlOrGuide()) return
    const token = app.globalData.token || wx.getStorageSync('token')
    if (!token) return wx.showToast({ title: '请先登录', icon: 'none' })

    const nickname = String(this.data.nicknameDraft || '').trim()
    if (nickname && nickname.length > 64) {
      wx.showToast({ title: '昵称过长（最多64字符）', icon: 'none' })
      return
    }

    this.setData({ saving: true })
    try {
      const body = {}
      const currentNickname = String(this.data.userInfo?.nickname || '').trim()
      if (nickname !== currentNickname) body.nickname = nickname

      const local = String(this.data.avatarLocal || '').trim()
      if (local) {
        const uploaded = await api.uploadImage(local, { needAuth: true, silent: false })
        const relUrl = String(uploaded?.url || '').trim()
        if (!relUrl) throw new Error('上传成功但未返回 url')
        body.avatar = this._toAbsoluteUrl(relUrl)
      }

      if (Object.keys(body).length === 0) {
        wx.showToast({ title: '未修改', icon: 'none' })
        return
      }

      await api.put('/api/v1/users/profile', body)
      wx.showToast({ title: '已保存', icon: 'success' })
      // 保存后回到“我的”，让 onShow 刷新展示
      wx.navigateBack()
    } catch (e) {
      wx.showToast({ title: e?.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false, avatarLocal: '' })
    }
  },
})



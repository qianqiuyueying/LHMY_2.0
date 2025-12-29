// pages/profile/profile.js
// 个人中心

const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    userInfo: null,
    isMember: false,
    isEmployee: false,
    memberValidUntil: null,
    enterpriseName: null,
    hasToken: false,
    loginAgreementAccepted: false,
    loginLoading: false,
    agreementTitle: '服务协议',
    agreementVersion: '0',
    agreementAccepting: false,
    agreementDialogVisible: false,
    _pendingLoginAfterAgree: false,
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

  onLoad() {
    const agreedVersion = String(wx.getStorageSync('mp_login_agreement_accepted_version') || '').trim()
    this.setData({ loginAgreementAccepted: !!agreedVersion })
    this.checkLogin()
    // 预取协议版本（用于“更新协议后需要重新同意”）
    this.prefetchLoginAgreementMeta()
  },

  onShow() {
    // 自定义 TabBar：每次显示时同步选中态
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tabBar && tabBar.setData) {
      tabBar.setData({ selected: 4 })
    }

    // 每次显示时刷新用户信息
    // 同步协议同意状态（避免“退出登录后/返回页面后状态不一致”）
    const agreedVersion = String(wx.getStorageSync('mp_login_agreement_accepted_version') || '').trim()
    const currentVersion = String(this.data.agreementVersion || '').trim()
    const accepted = !!agreedVersion && !!currentVersion && agreedVersion === currentVersion
    if (accepted !== this.data.loginAgreementAccepted) this.setData({ loginAgreementAccepted: accepted })
    this.loadUserProfile()
  },

  // 检查登录状态
  checkLogin() {
    const token = app.globalData.token || wx.getStorageSync('token')
    if (token) {
      // setData 异步：不要用 this.data.hasToken 做门禁
      this.setData({ hasToken: true }, () => this.loadUserProfile())
    } else {
      // 无 token 时不做静默自动登录（会绕过协议确认/也不符合预期）
      this.setData({ hasToken: false })
    }
  },

  async prefetchLoginAgreementMeta() {
    try {
      const data = await api.get('/api/v1/legal/MP_LOGIN_AGREEMENT', {}, false, true)
      const title = String(data?.title || '服务协议')
      const version = String(data?.version || '0')
      const agreedVersion = String(wx.getStorageSync('mp_login_agreement_accepted_version') || '').trim()
      const accepted = !!agreedVersion && agreedVersion === version
      this.setData({
        agreementTitle: title,
        agreementVersion: version,
        loginAgreementAccepted: accepted,
      })
    } catch (e) {
      // 预取失败不影响主流程；弹层打开时会再次加载
    }
  },

  // 加载用户信息
  async loadUserProfile() {
    // 以 token 是否存在为准（避免 setData 异步导致门禁误判）
    const token = app.globalData.token || wx.getStorageSync('token')
    if (!token) {
      this.setData({ hasToken: false, userInfo: null })
      return
    }

    try {
      const userInfo = await api.get('/api/v1/users/profile')
      // 若拿到了 profile，则同步认为已登录
      if (!this.data.hasToken) this.setData({ hasToken: true })
      this.applyUserProfile(userInfo)
    } catch (error) {
      console.error('加载用户信息失败:', error)
      // 关键：不要静默失败，否则用户会觉得“按钮没反应”
      wx.showToast({ title: error?.message || '获取用户信息失败', icon: 'none' })
      // 若后端判定未登录，这里会在 api.js 中触发 app.logout()；我们这里也做一次 UI 收敛
      const still = app.globalData.token || wx.getStorageSync('token')
      if (!still) this.setData({ hasToken: false, userInfo: null })
    }
  },

  applyUserProfile(userInfo) {
    const isMember = userInfo?.identities?.includes('MEMBER') || false
    const isEmployee = userInfo?.identities?.includes('EMPLOYEE') || false
    const normalizedAvatar = this._toAbsoluteUrl(userInfo?.avatar)
    this.setData({
      userInfo: { ...(userInfo || {}), avatar: normalizedAvatar || (userInfo?.avatar || null) },
      isMember,
      isEmployee,
      memberValidUntil: userInfo?.memberValidUntil || null,
      enterpriseName: userInfo?.enterpriseName || null,
    })
  },

  // 占位：用于阻止弹层点击冒泡
  noop() {},

  // --- 协议确认（官方推荐交互：勾选 + 弹窗同意/拒绝 + 可点击协议链接） ---
  onTapAgreementCheckbox() {
    // 已同意：允许取消（清除本地同意状态），下次登录会再次要求同意
    if (this.data.loginAgreementAccepted) {
      try { wx.removeStorageSync('mp_login_agreement_accepted_version') } catch (e) {}
      this.setData({ loginAgreementAccepted: false })
      return
    }
    this.openAgreementDialog(false)
  },

  openAgreementDialog(pendingLoginAfterAgree = false) {
    this._pendingLoginAfterAgree = !!pendingLoginAfterAgree
    this.setData({ agreementDialogVisible: true, agreementAccepting: false })
    // 若版本还没取到，这里尝试预取（失败不阻塞弹窗，点“同意”时会再兜底拉一次）
    if (!String(this.data.agreementVersion || '').trim() || String(this.data.agreementVersion || '').trim() === '0') {
      this.prefetchLoginAgreementMeta()
    }
  },

  async _ensureAgreementMeta() {
    const v0 = String(this.data.agreementVersion || '').trim()
    if (v0 && v0 !== '0') return { title: this.data.agreementTitle, version: v0 }
    const data = await api.get('/api/v1/legal/MP_LOGIN_AGREEMENT', {}, false, true)
    const title = String(data?.title || '服务协议')
    const version = String(data?.version || '0')
    this.setData({ agreementTitle: title, agreementVersion: version })
    return { title, version }
  },

  async onAgreementAcceptAndMaybeLogin() {
    if (this.data.agreementAccepting) return
    this.setData({ agreementAccepting: true })
    try {
      const { version } = await this._ensureAgreementMeta()
      if (!version || version === '0') {
        wx.showToast({ title: '协议加载失败，请稍后重试', icon: 'none' })
        return
      }
      wx.setStorageSync('mp_login_agreement_accepted_version', String(version))
      this.setData({ loginAgreementAccepted: true, agreementDialogVisible: false })
      if (this._pendingLoginAfterAgree) {
        this._pendingLoginAfterAgree = false
        await this.onLogin()
      }
    } catch (e) {
      wx.showToast({ title: e?.message || '协议加载失败', icon: 'none' })
    } finally {
      this.setData({ agreementAccepting: false })
    }
  },

  onAgreementDecline() {
    this._pendingLoginAfterAgree = false
    this.setData({ agreementDialogVisible: false })
  },

  // 登录
  async onLogin() {
    if (this.data.loginLoading) return
    if (!this._ensureApiBaseUrlOrGuide()) return
    let loadingShown = false
    try {
      // 1) 若本地已有 token：先尝试用它拉 profile；若已失效则走真正登录
      const existing = app.globalData.token || wx.getStorageSync('token')
      if (existing) {
        app.globalData.token = existing
        this.setData({ hasToken: true })
        try {
          const userInfo = await api.get('/api/v1/users/profile')
          this.applyUserProfile(userInfo)
          return
        } catch (e) {
          // token 已失效：清理后继续走 app.login()
          app.logout()
          this.setData({ hasToken: false, userInfo: null })
        }
      }

      // 2) 登录前协议确认：官方推荐（勾选 + 弹窗同意/拒绝）
      // 以“协议版本”为准：版本未知时也必须弹窗确认（避免异步导致跳过同意流程）
      const currentVersion = String(this.data.agreementVersion || '').trim()
      const agreedVersion = String(wx.getStorageSync('mp_login_agreement_accepted_version') || '').trim()
      const accepted = !!currentVersion && currentVersion !== '0' && agreedVersion === currentVersion
      if (!accepted) {
        this.openAgreementDialog(true)
        return
      }

      // 3) 真正登录
      this.setData({ loginLoading: true })
      wx.showLoading({ title: '登录中...', mask: true })
      loadingShown = true
      await app.login()

      // setData 异步：用回调保证 loadUserProfile 不会被“hasToken 旧值”挡住
      this.setData({ hasToken: true }, async () => {
        await this.loadUserProfile()
      })
    } catch (error) {
      console.error('登录失败:', error)
      wx.showToast({
        title: error?.message || '登录失败',
        icon: 'none'
      })
    } finally {
      if (loadingShown) {
        try { wx.hideLoading() } catch (e) {}
      }
      this.setData({ loginLoading: false })
    }
  },

  // 查看服务协议（MP_LOGIN_AGREEMENT）
  onViewLoginAgreement() {
    wx.navigateTo({ url: '/pages/legal/agreement/agreement?code=MP_LOGIN_AGREEMENT' })
  },

  // 个人资料页
  onGoProfileEdit() {
    wx.navigateTo({ url: '/pages/profile/profile-edit/profile-edit' })
  },

  _toAbsoluteUrl(maybePath) {
    const x = String(maybePath || '').trim()
    if (!x) return ''
    if (x.startsWith('http://') || x.startsWith('https://')) return x
    const base = String(app.globalData.apiBaseUrl || '').trim()
    if (!base) return x
    return `${base}${x.startsWith('/') ? x : `/${x}`}`
  },

  // 保存资料已迁移到“个人资料”页

  // 绑定手机号
  async onBindPhone() {
    if (!app.globalData.token) {
      wx.showToast({
        title: '请先登录',
        icon: 'none'
      })
      return
    }

    // 跳转到绑定手机号页（简化处理，直接调用API）
    wx.showModal({
      title: '输入手机号',
      content: '',
      editable: true,
      placeholderText: '请输入手机号',
      success: async (res) => {
        if (res.confirm && res.content) {
          const phone = String(res.content || '').trim()
          // v1：后端校验中国大陆 11 位手机号格式
          if (!/^1\d{10}$/.test(phone)) {
            wx.showToast({ title: '请输入正确的11位手机号', icon: 'none' })
            return
          }

          // 请求验证码
          try {
            // 该接口不要求登录（needAuth=false），避免带无关 Authorization
            await api.post('/api/v1/auth/request-sms-code', {
              phone,
              scene: 'MP_BIND_PHONE'
            }, false)
            
            // 输入验证码
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

  // 企业绑定
  onEnterpriseBind() {
    wx.navigateTo({
      url: '/pages/profile/enterprise-bind/enterprise-bind'
    })
  },

  // 我的权益
  onMyEntitlements() {
    wx.switchTab({
      url: '/pages/entitlement/entitlement'
    })
  },

  // 我的预约
  onMyBookings() {
    wx.navigateTo({
      url: '/pages/booking/booking'
    })
  },

  // 收货地址
  onMyAddresses() {
    wx.navigateTo({ url: '/pages/address/address-list/address-list' })
  },

  // 客服与帮助
  onSupport() {
    wx.navigateTo({ url: '/pages/support/support' })
  },

  // 查看服务协议（MP_LOGIN_AGREEMENT）
  // 已移除“底部协议弹层”；登录前在本页弹窗确认，协议全文页单独查看

  // 复制诊断信息（用户支持：可复现问题时提供最小诊断上下文）
  onCopyDiagnostics() {
    const apiBaseUrl = app.globalData.apiBaseUrl || ''
    const hasToken = !!(app.globalData.token || wx.getStorageSync('token'))
    const lastApiEvent = wx.getStorageSync('lastApiEvent') || null
    const agreedVersion = String(wx.getStorageSync('mp_login_agreement_accepted_version') || '').trim()
    const loginAgreementAccepted = !!agreedVersion
    const now = new Date().toISOString()

    const text = [
      'LHMY Mini Program Diagnostics',
      `time=${now}`,
      `apiBaseUrl=${apiBaseUrl}`,
      `hasToken=${hasToken}`,
      `loginAgreementAccepted=${loginAgreementAccepted}`,
      `loginAgreementAcceptedVersion=${agreedVersion || ''}`,
      lastApiEvent ? `lastApiEvent=${JSON.stringify(lastApiEvent)}` : 'lastApiEvent=none',
    ].join('\n')

    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },

  // 退出登录
  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出当前账号吗？',
      confirmText: '退出',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return
        app.logout()
        // 退出登录不清“协议同意”，避免每次重复确认；但允许用户手动取消勾选来撤回
        this.setData({
          hasToken: false,
          userInfo: null,
          isMember: false,
          isEmployee: false,
          memberValidUntil: null,
          enterpriseName: null,
        })
        wx.showToast({ title: '已退出', icon: 'success' })
      },
    })
  }
})

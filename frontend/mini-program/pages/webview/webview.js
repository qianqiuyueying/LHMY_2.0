// pages/webview/webview.js

Page({
  _loadTimer: null,
  data: {
    url: '',
    loading: true,
    errorMessage: '',
  },

  onLoad(options) {
    if (this._loadTimer) {
      clearTimeout(this._loadTimer)
      this._loadTimer = null
    }
    let url = ''
    let title = ''
    try {
      url = decodeURIComponent(options.url || '')
    } catch (e) {
      url = String(options.url || '')
    }
    try {
      title = options.title ? decodeURIComponent(options.title) : ''
    } catch (e) {
      title = String(options.title || '')
    }

    if (title) {
      wx.setNavigationBarTitle({ title })
    }

    if (!url) {
      this.setData({
        url: '',
        loading: false,
        errorMessage: '链接为空，无法打开页面',
      })
      return
    }

    // 基础校验：必须是 http(s)
    // 注意：小程序构建器对正则字面量转义较严格，这里使用标准写法
    if (!/^https?:\/\//i.test(url)) {
      this.setData({
        url: '',
        loading: false,
        errorMessage: '链接格式不正确，无法打开页面',
      })
      return
    }

    // 注意：web-view 内页脚本错误（webviewScriptError）无法由我们修复，
    // 但可通过 binderror 显示统一错误态，避免用户看到空白页。
    this.setData({ url, loading: true, errorMessage: '' })

    // 关键兜底：部分“业务域名不合法/未配置”等场景不会触发 binderror，导致一直停在“加载中”
    // 因此加一个超时提示，避免用户无反馈。
    this._loadTimer = setTimeout(() => {
      if (!this.data.loading) return
      let host = ''
      try {
        host = String(url).replace(/^https?:\/\//i, '').split('/')[0]
      } catch (e) {}
      const hint = [
        '页面长时间未响应。',
        host ? `域名：${host}` : '',
        '请确认：',
        '1) 已在微信公众平台配置 web-view（业务域名）白名单（通常只能配置你自己可验证的域名）',
        '2) 开发者工具可在“项目设置→本地设置”勾选“不校验合法域名、web-view（业务域名）…”用于本地联调',
      ].filter(Boolean).join('\n')
      this.setData({ loading: false, errorMessage: hint })
    }, 9000)
  },

  onWebViewLoad() {
    if (this._loadTimer) {
      clearTimeout(this._loadTimer)
      this._loadTimer = null
    }
    this.setData({ loading: false })
  },

  onWebViewError(e) {
    console.warn('web-view error:', e)
    if (this._loadTimer) {
      clearTimeout(this._loadTimer)
      this._loadTimer = null
    }
    this.setData({
      loading: false,
      errorMessage:
        '页面加载失败。\n\n常见原因：未配置 web-view（业务域名）白名单，或目标站点不允许被小程序打开。\n你可以先换成你自己可配置的测试域名，或在开发者工具里勾选“不校验合法域名…”进行联调。',
    })
  },

  onRetryTap() {
    if (!this.data.url) return
    // 通过重置 url 触发重新加载
    const url = this.data.url
    if (this._loadTimer) {
      clearTimeout(this._loadTimer)
      this._loadTimer = null
    }
    this.setData({ loading: true, errorMessage: '', url: '' })
    setTimeout(() => {
      this.setData({ url })
    }, 50)
  },

  onBackTap() {
    wx.navigateBack()
  },

  onUnload() {
    if (this._loadTimer) {
      clearTimeout(this._loadTimer)
      this._loadTimer = null
    }
  },
})

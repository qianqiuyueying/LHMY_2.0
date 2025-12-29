// app.js
// 小程序应用入口

App({
  _getApiBaseUrlSafe() {
    // 兼容不同导出形态：CommonJS 直接导出 / default 包装
    // - 直接：require('./utils/config').getApiBaseUrl
    // - 包装：require('./utils/config').default.getApiBaseUrl
    try {
      const cfg = require('./utils/config') || {}
      const fn =
        (typeof cfg.getApiBaseUrl === 'function' && cfg.getApiBaseUrl) ||
        (cfg.default && typeof cfg.default.getApiBaseUrl === 'function' && cfg.default.getApiBaseUrl)
      return fn ? fn() : ''
    } catch (e) {
      return ''
    }
  },
  onLaunch() {
    // 小程序启动时执行
    console.log('小程序启动')

    // 初始化 API BaseUrl（避免 require 导出形态差异导致启动报错）
    this.globalData.apiBaseUrl = this._getApiBaseUrlSafe()
    
    // 检查登录状态
    this.checkLogin()
  },

  onShow() {
    // 小程序显示时执行
  },

  onHide() {
    // 小程序隐藏时执行
  },

  onError(msg) {
    console.error('小程序错误:', msg)
  },

  // 全局数据
  globalData: {
    userInfo: null,
    token: null,
    apiBaseUrl: '',
  },
  // 登录并发控制：避免重复点击/并行调用导致 wx.login/请求行为异常
  _loginPromise: null,

  // 将 wx.request 包一层 Promise（避免直接 await wx.request 导致无效）
  _request(options) {
    return new Promise((resolve, reject) => {
      const startedAt = Date.now()
      wx.request({
        ...options,
        success: (res) => {
          try {
            wx.setStorageSync('lastApiEvent', {
              ok: res?.statusCode >= 200 && res?.statusCode < 300,
              at: Date.now(),
              method: options?.method || 'GET',
              url: options?.url || '',
              statusCode: res?.statusCode,
              durationMs: Date.now() - startedAt,
              // 兼容后端 envelope 的 requestId
              responseRequestId: res?.data?.requestId || '',
            })
          } catch (e) {}
          resolve(res)
        },
        fail: (err) => {
          try {
            wx.setStorageSync('lastApiEvent', {
              ok: false,
              at: Date.now(),
              method: options?.method || 'GET',
              url: options?.url || '',
              statusCode: 0,
              durationMs: Date.now() - startedAt,
              message: err?.errMsg || 'request:fail',
            })
          } catch (e) {}
          reject(err)
        }
      })
    })
  },

  // 检查登录状态
  checkLogin() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      // 验证token有效性
      this.validateToken()
    }
  },

  // 验证token
  async validateToken() {
    try {
      const res = await this._request({
        url: `${this.globalData.apiBaseUrl}/api/v1/users/profile`,
        header: {
          'Authorization': `Bearer ${this.globalData.token}`
        }
      })
      if (res.statusCode === 200 && res.data.success) {
        this.globalData.userInfo = res.data.data
      } else {
        // token失效，清除
        this.logout()
      }
    } catch (error) {
      console.error('验证token失败:', error)
      this.logout()
    }
  },

  // 登录
  async login() {
    if (this._loginPromise) return this._loginPromise

    const p = new Promise((resolve, reject) => {
      let finished = false
      const timer = setTimeout(() => {
        if (finished) return
        finished = true
        reject(new Error('登录超时，请重试'))
      }, 12000)

      const finish = (fn) => (arg) => {
        if (finished) return
        finished = true
        clearTimeout(timer)
        fn(arg)
      }

      wx.login({
        success: async (res) => {
          if (!res.code) return finish(reject)(new Error('获取微信code失败'))
          try {
            let loginCode = res.code
            try {
              const loginRes = await this._request({
                url: `${this.globalData.apiBaseUrl}/api/v1/mini-program/auth/login`,
                method: 'POST',
                data: { code: loginCode },
              })
              if (loginRes.statusCode === 200 && loginRes.data.success) {
                const { token, user } = loginRes.data.data
                this.globalData.token = token
                this.globalData.userInfo = user
                wx.setStorageSync('token', token)
                return finish(resolve)({ token, user })
              }
              return finish(reject)(new Error(loginRes.data.error?.message || '登录失败'))
            } catch (error) {
              // 开发环境兜底：配置缺失则 mock 重试
              if (
                error?.statusCode === 500 ||
                (error?.data && error.data.error && String(error.data.error.message || '').includes('微信登录配置缺失'))
              ) {
                console.warn('检测到微信登录配置缺失，使用mock模式登录（仅开发环境）')
                loginCode = `mock:unionid:${Date.now()}`
              } else {
                return finish(reject)(error)
              }
            }

            const mockRes = await this._request({
              url: `${this.globalData.apiBaseUrl}/api/v1/mini-program/auth/login`,
              method: 'POST',
              data: { code: loginCode },
            })
            if (mockRes.statusCode === 200 && mockRes.data.success) {
              const { token, user } = mockRes.data.data
              this.globalData.token = token
              this.globalData.userInfo = user
              wx.setStorageSync('token', token)
              return finish(resolve)({ token, user })
            }
            return finish(reject)(new Error(mockRes.data.error?.message || '登录失败'))
          } catch (error) {
            console.error('登录失败:', error)
            if (error?.statusCode === 500) return finish(reject)(new Error('登录服务异常，请检查后端配置或联系管理员'))
            return finish(reject)(error)
          }
        },
        fail: (e) => finish(reject)(e),
      })
    })

    // 确保 promise 结束后释放锁（无论成功/失败/超时）
    this._loginPromise = p.finally(() => {
      this._loginPromise = null
    })
    return this._loginPromise
  },

  // 登出
  logout() {
    this.globalData.token = null
    this.globalData.userInfo = null
    wx.removeStorageSync('token')
    this._loginPromise = null
    try { wx.removeStorageSync('lastApiEvent') } catch (e) {}
    // 退出登录不清“协议同意”与“头像昵称授权结果”，避免每次都重复弹授权/重复确认协议
  }
})


// utils/api.js
// API调用封装

const app = getApp()

function _safeSetLastApiEvent(payload) {
  try {
    wx.setStorageSync('lastApiEvent', payload)
  } catch (e) {}
}

function genIdempotencyKey(prefix = 'mp') {
  // v1 最小：只需具备足够随机性用于请求去重
  const rand = Math.random().toString(16).slice(2)
  return `${prefix}:${Date.now()}:${rand}`
}

function genRequestId(prefix = 'mp') {
  const rand = Math.random().toString(16).slice(2)
  return `${prefix}-${Date.now()}-${rand}`
}

/**
 * 上传图片（wx.uploadFile）
 * - 统一注入 Authorization / X-Request-Id
 * - 解析后端统一 envelope：{ success, data, error, requestId }
 */
function uploadImage(filePath, { needAuth = true, silent = false } = {}) {
  return new Promise((resolve, reject) => {
    if (!filePath) return reject(new Error('filePath 不能为空'))

    const token = app.globalData.token || wx.getStorageSync('token')
    if (needAuth && !token) return reject(new Error('未登录'))

    const requestId = genRequestId()
    const base = String(app.globalData.apiBaseUrl || '').trim()
    if (!base) return reject(new Error('未配置 apiBaseUrl'))
    const fullUrl = `${base}/api/v1/uploads/images`

    wx.uploadFile({
      url: fullUrl,
      filePath,
      name: 'file',
      header: {
        ...(needAuth && token ? { Authorization: `Bearer ${token}` } : {}),
        'X-Request-Id': requestId,
      },
      success: (res) => {
        let payload = null
        try {
          payload = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
        } catch (e) {}

        if (res.statusCode === 200 && payload && payload.success) {
          _safeSetLastApiEvent({
            ok: true,
            at: Date.now(),
            method: 'UPLOAD',
            url: fullUrl,
            statusCode: res.statusCode,
            durationMs: 0,
            requestId,
            responseRequestId: payload?.requestId || '',
          })
          resolve(payload.data)
          return
        }

        // 兼容 FastAPI HTTPException 默认形态：{ detail: { code, message } }
        const detail = payload?.detail
        const error = payload?.error
        const msg =
          error?.message ||
          detail?.message ||
          `上传失败: ${res.statusCode}`

        _safeSetLastApiEvent({
          ok: false,
          at: Date.now(),
          method: 'UPLOAD',
          url: fullUrl,
          statusCode: res.statusCode,
          durationMs: 0,
          code: error?.code || detail?.code || '',
          message: msg,
          requestId,
          responseRequestId: payload?.requestId || '',
        })

        if (!silent) wx.showToast({ title: msg, icon: 'none' })
        reject(new Error(msg))
      },
      fail: (err) => {
        const msg = err?.errMsg || '上传失败'
        _safeSetLastApiEvent({
          ok: false,
          at: Date.now(),
          method: 'UPLOAD',
          url: fullUrl,
          statusCode: 0,
          durationMs: 0,
          code: 'NETWORK_ERROR',
          message: msg,
          requestId,
        })
        if (!silent) wx.showToast({ title: msg, icon: 'none' })
        reject(new Error(msg))
      },
    })
  })
}

/**
 * 统一请求方法
 */
function request(options) {
  return new Promise((resolve, reject) => {
    const { url, method = 'GET', data = {}, needAuth = true, headers = {}, silent = false } = options
    
    // 构建请求头
    const header = {
      'Content-Type': 'application/json'
    }
    
    // 添加认证token
    if (needAuth) {
      const token = app.globalData.token || wx.getStorageSync('token')
      if (token) {
        header['Authorization'] = `Bearer ${token}`
      }
    }
    
    // RequestId：用于端到端定位（后端默认读取 X-Request-Id）
    const requestId = headers?.['X-Request-Id'] || headers?.['x-request-id'] || genRequestId()
    header['X-Request-Id'] = requestId

    // 合并自定义 header（如 Idempotency-Key）
    Object.assign(header, headers || {})

    // 构建完整URL
    const fullUrl = url.startsWith('http') ? url : `${app.globalData.apiBaseUrl}${url}`
    const startedAt = Date.now()
    
    wx.request({
      url: fullUrl,
      method: method,
      data: data,
      header: header,
      success: (res) => {
        const durationMs = Date.now() - startedAt
        const responseRequestId = res?.data?.requestId || ''
        if (res.statusCode === 200) {
          if (res.data.success) {
            _safeSetLastApiEvent({
              ok: true,
              at: Date.now(),
              method,
              url: fullUrl,
              statusCode: res.statusCode,
              durationMs,
              requestId,
              responseRequestId,
            })
            resolve(res.data.data)
          } else {
            // 业务错误
            const error = res.data.error
            _safeSetLastApiEvent({
              ok: false,
              at: Date.now(),
              method,
              url: fullUrl,
              statusCode: res.statusCode,
              durationMs,
              code: error?.code || '',
              message: error?.message || '请求失败',
              requestId,
              responseRequestId,
            })
            if (error?.code === 'UNAUTHENTICATED') {
              // token失效，清除并跳转登录（认证错误总是显示提示）
              app.logout()
              if (!options.silent) {
                wx.showToast({
                  title: '请重新登录',
                  icon: 'none'
                })
                setTimeout(() => {
                  // profile 是 Tab 页，使用 switchTab 保持行为一致
                  wx.switchTab({ url: '/pages/profile/profile' })
                }, 1500)
              } else {
                // 静默模式下也跳转，但不显示提示
                setTimeout(() => {
                  wx.switchTab({ url: '/pages/profile/profile' })
                }, 100)
              }
            } else {
              // 只在非静默模式下显示错误提示
              if (!options.silent) {
                wx.showToast({
                  title: error?.message || '请求失败',
                  icon: 'none'
                })
              }
            }
            const e = new Error(error?.message || '请求失败')
            e.code = error?.code || ''
            e.requestId = requestId
            e.responseRequestId = responseRequestId
            reject(e)
          }
        } else if (res.statusCode === 401) {
          // 未授权
          app.logout()
          if (!options.silent) {
            wx.showToast({
              title: '请重新登录',
              icon: 'none'
            })
          }
          _safeSetLastApiEvent({
            ok: false,
            at: Date.now(),
            method,
            url: fullUrl,
            statusCode: res.statusCode,
            durationMs,
            code: 'UNAUTHORIZED',
            message: '未授权',
            requestId,
            responseRequestId,
          })
          // 401 时也引导回“我的”
          setTimeout(() => {
            wx.switchTab({ url: '/pages/profile/profile' })
          }, options.silent ? 100 : 1500)
          reject(new Error('未授权'))
        } else {
          // 非 200：优先按统一 envelope 解析（后端统一返回 success/data/error/requestId）
          if (res?.data && typeof res.data.success === 'boolean') {
            const error = res.data.error || {}
            const msg = error?.message || `请求失败: ${res.statusCode}`
            _safeSetLastApiEvent({
              ok: false,
              at: Date.now(),
              method,
              url: fullUrl,
              statusCode: res.statusCode,
              durationMs,
              code: error?.code || '',
              message: msg,
              requestId,
              responseRequestId,
            })
            if (!options.silent) {
              wx.showToast({ title: msg, icon: 'none' })
            }
            const e = new Error(msg)
            e.code = error?.code || ''
            e.requestId = requestId
            e.responseRequestId = responseRequestId
            reject(e)
            return
          }

          // 兼容 FastAPI HTTPException 默认形态：{ detail: { code, message, ... } }
          const detail = res.data?.detail
          const msg = detail?.message || `请求失败: ${res.statusCode}`
          _safeSetLastApiEvent({
            ok: false,
            at: Date.now(),
            method,
            url: fullUrl,
            statusCode: res.statusCode,
            durationMs,
            code: detail?.code || '',
            message: msg,
            requestId,
            responseRequestId,
          })
          if (!options.silent) {
            wx.showToast({ title: msg, icon: 'none' })
          }
          const e = new Error(msg)
          e.code = detail?.code || ''
          e.requestId = requestId
          e.responseRequestId = responseRequestId
          reject(e)
        }
      },
      fail: (err) => {
        // 网络错误处理
        let errorMessage = '网络错误'
        
        // 根据错误类型提供更具体的提示
        if (err.errMsg) {
          if (err.errMsg.includes('ERR_EMPTY_RESPONSE') || err.errMsg.includes('request:fail')) {
            errorMessage = '无法连接到服务器，请检查后端服务是否运行'
          } else if (err.errMsg.includes('timeout')) {
            errorMessage = '请求超时，请稍后重试'
          } else if (err.errMsg.includes('network')) {
            errorMessage = '网络连接失败，请检查网络设置'
          }
        }
        
        // 只在非静默模式下显示错误提示
        if (!options.silent) {
          wx.showToast({
            title: errorMessage,
            icon: 'none',
            duration: 2000
          })
        }

        _safeSetLastApiEvent({
          ok: false,
          at: Date.now(),
          method,
          url: fullUrl,
          statusCode: 0,
          durationMs: Date.now() - startedAt,
          code: 'NETWORK_ERROR',
          message: errorMessage,
          errMsg: err?.errMsg || '',
          requestId,
        })

        const e = new Error(errorMessage)
        e.code = 'NETWORK_ERROR'
        e.requestId = requestId
        reject(e)
      }
    })
  })
}

/**
 * GET请求
 * @param {string} url - 请求URL
 * @param {object} data - 请求参数
 * @param {boolean} needAuth - 是否需要认证
 * @param {boolean} silent - 是否静默模式（不显示错误提示）
 */
function get(url, data = {}, needAuth = true, silent = false) {
  return request({ url, method: 'GET', data, needAuth, silent })
}

/**
 * POST请求
 * @param {string} url - 请求URL
 * @param {object} data - 请求数据
 * @param {boolean} needAuth - 是否需要认证
 * @param {object} headers - 自定义请求头
 * @param {boolean} silent - 是否静默模式（不显示错误提示）
 */
function post(url, data = {}, needAuth = true, headers = {}, silent = false) {
  return request({ url, method: 'POST', data, needAuth, headers, silent })
}

/**
 * PUT请求
 */
function put(url, data = {}, needAuth = true, headers = {}) {
  return request({ url, method: 'PUT', data, needAuth, headers })
}

/**
 * DELETE请求
 */
function del(url, data = {}, needAuth = true, headers = {}) {
  return request({ url, method: 'DELETE', data, needAuth, headers })
}

module.exports = {
  genIdempotencyKey,
  genRequestId,
  request,
  get,
  post,
  put,
  del,
  uploadImage,
}

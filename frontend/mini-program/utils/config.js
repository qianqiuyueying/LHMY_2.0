// utils/config.js
// 配置文件

// API基础URL
// - 默认：开发环境使用 127.0.0.1（避免 localhost 在部分环境下 ERR_EMPTY_RESPONSE）
// - 可覆写：通过本地存储键 `apiBaseUrl`（便于在开发者工具/测试环境快速切换）
function getApiBaseUrl() {
  // v1 约束：release 环境不允许默认指向 localhost/127.0.0.1（避免“上线后不可用”）
  // - develop/trial：允许本地默认
  // - release：要求显式配置（storage 覆写）
  const fallbackLocal = 'http://192.168.2.1:8000'
  let envVersion = ''
  try {
    // 避免可选链语法在部分基础库/构建配置下导致模块解析失败
    const info = wx.getAccountInfoSync && wx.getAccountInfoSync()
    envVersion = (info && info.miniProgram && info.miniProgram.envVersion) || ''
  } catch (e) {}
  const isRelease = String(envVersion || '').toLowerCase() === 'release'
  try {
    const v = String(wx.getStorageSync('apiBaseUrl') || '').trim()
    if (v) return v
  } catch (e) {}
  if (isRelease) return ''
  return fallbackLocal
}

const API_BASE_URL = getApiBaseUrl()

module.exports = {
  API_BASE_URL,
  getApiBaseUrl,
}

// 兼容部分构建/运行时对 CommonJS 的 default 包装（避免 require(...).getApiBaseUrl 为 undefined）
module.exports.default = module.exports

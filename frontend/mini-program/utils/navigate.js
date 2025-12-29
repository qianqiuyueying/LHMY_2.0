// utils/navigate.js

const TAB_ROUTES = new Set([
  '/pages/index/index',
  '/pages/mall/mall',
  '/pages/entitlement/entitlement',
  '/pages/order/order',
  '/pages/profile/profile',
])

function navigateByJump({ jumpType, targetId, title }) {
  if (!jumpType || !targetId) {
    // 避免“点击无反应且无任何线索”
    console.warn('navigateByJump: 缺少参数，已忽略跳转', { jumpType, targetId, title })
    return
  }

  switch (jumpType) {
    case 'AGG_PAGE':
      wx.navigateTo({ url: `/pages/aggregate/aggregate?pageId=${encodeURIComponent(targetId)}` })
      return
    case 'INFO_PAGE':
      wx.navigateTo({ url: `/pages/info/info?pageId=${encodeURIComponent(targetId)}` })
      return
    case 'WEBVIEW':
      wx.navigateTo({
        url: `/pages/webview/webview?url=${encodeURIComponent(targetId)}${title ? `&title=${encodeURIComponent(title)}` : ''}`,
      })
      return
    case 'MINI_PROGRAM': {
      // vNow：targetId 约定为 "appid|path"
      const raw = String(targetId || '')
      const parts = raw.split('|')
      const appId = (parts[0] || '').trim()
      const path = (parts[1] || '').trim()
      if (!appId) return
      wx.navigateToMiniProgram({
        appId,
        path: path || undefined,
        fail: (e) => console.warn('打开其他小程序失败:', e),
      })
      return
    }
    case 'ROUTE':
    case 'FIXED_ROUTE':
      // v1：targetId 为小程序固定路由标识，由端侧解释
      if (TAB_ROUTES.has(targetId)) {
        wx.switchTab({ url: targetId })
      } else {
        wx.navigateTo({
          url: targetId,
          fail: (e) => console.warn('navigateTo 失败:', { targetId, e }),
        })
      }
      return
    default:
      console.warn('未知的跳转类型:', jumpType)
  }
}

module.exports = {
  navigateByJump,
}

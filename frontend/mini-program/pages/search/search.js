// pages/search/search.js
// 搜索页（v1）：带历史记录，确认后跳转到商城 tab 页并传递 keyword（通过 storage）

const HISTORY_KEY = 'mp_search_history'
const NEXT_KEYWORD_KEY = 'mp_mall_next_keyword'

function _readHistory() {
  try {
    const v = wx.getStorageSync(HISTORY_KEY)
    return Array.isArray(v) ? v.filter(Boolean).map((x) => String(x)) : []
  } catch (e) {
    return []
  }
}

function _writeHistory(list) {
  try {
    wx.setStorageSync(HISTORY_KEY, list)
  } catch (e) {}
}

function _pushHistory(keyword) {
  const k = String(keyword || '').trim()
  if (!k) return
  const list = _readHistory()
  const next = [k, ...list.filter((x) => x !== k)].slice(0, 12)
  _writeHistory(next)
  return next
}

Page({
  data: {
    keyword: '',
    history: [],
    autoFocus: true,
  },

  onLoad(options) {
    const init = String(options.keyword || '').trim()
    const history = _readHistory()
    this.setData({
      keyword: init,
      history,
      autoFocus: true,
    })
  },

  onShow() {
    this.setData({ history: _readHistory() })
  },

  onInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  onHistoryTap(e) {
    const kw = String(e.currentTarget.dataset.keyword || '').trim()
    if (!kw) return
    this.setData({ keyword: kw })
    this.onConfirm()
  },

  onClearHistory() {
    _writeHistory([])
    this.setData({ history: [] })
  },

  onConfirm() {
    const kw = String(this.data.keyword || '').trim()
    if (!kw) {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }

    const nextHistory = _pushHistory(kw) || _readHistory()
    this.setData({ history: nextHistory })

    // TabBar 页不能带 query：用 storage 传递
    try {
      wx.setStorageSync(NEXT_KEYWORD_KEY, kw)
    } catch (e) {}

    wx.switchTab({ url: '/pages/mall/mall' })
  },
})



// pages/index/entries-more/entries-more.js
// 更多入口（展示全部 SHORTCUT entries）

const api = require('../../../utils/api')
const { navigateByJump } = require('../../../utils/navigate')

Page({
  data: {
    items: [],
  },

  onLoad() {
    // 优先读 storage（由首页写入），失败则回源请求
    let cached = []
    try { cached = wx.getStorageSync('mp_entries_all') || [] } catch (e) {}
    if (Array.isArray(cached) && cached.length > 0) {
      this.setData({ items: cached })
      return
    }
    this.loadEntries()
  },

  async loadEntries() {
    try {
      const data = await api.get('/api/v1/mini-program/entries', {}, false, true)
      const all = data?.items || []
      const shortcuts = all.filter((x) => x && x.position === 'SHORTCUT')
      this.setData({ items: shortcuts })
    } catch (e) {
      this.setData({ items: [] })
    }
  },

  onItemTap(e) {
    const { item } = e.currentTarget.dataset
    if (!item) return
    navigateByJump({ jumpType: item.jumpType, targetId: item.targetId, title: item.name })
  },
})



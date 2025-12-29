// pages/entitlement/entitlement.js
// 权益列表

const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    entitlements: [],
    // 筛选条件
    typeFilter: null, // SERVICE_PACKAGE
    statusFilter: null, // ACTIVE/USED/EXPIRED/REFUNDED
    loading: true
  },

  onLoad() {
    this.loadEntitlements()
  },

  onShow() {
    // 自定义 TabBar：每次显示时同步选中态
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tabBar && tabBar.setData) {
      tabBar.setData({ selected: 2 })
    }

    // 每次显示时刷新权益列表
    this.loadEntitlements()
  },

  onPullDownRefresh() {
    this.loadEntitlements().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 加载权益列表
  async loadEntitlements() {
    if (!app.globalData.token) {
      wx.showModal({
        title: '提示',
        content: '请先登录',
        showCancel: true,
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            // 使用switchTab跳转到TabBar页面
            wx.switchTab({
              url: '/pages/profile/profile'
            })
          }
          // 无论确认还是取消，都设置loading为false
          this.setData({ loading: false })
        },
        fail: () => {
          // 弹窗失败时也要设置loading为false
          this.setData({ loading: false })
        }
      })
      return
    }

    try {
      const params = {}
      if (this.data.typeFilter) {
        params.entitlementType = this.data.typeFilter
      }
      if (this.data.statusFilter) {
        params.status = this.data.statusFilter
      }

      const data = await api.get('/api/v1/entitlements', params)
      this.setData({
        entitlements: data?.items || [],
        loading: false
      })
    } catch (error) {
      console.error('加载权益列表失败:', error)
      this.setData({ loading: false })
    }
  },

  // 选择类型筛选
  onTypeFilterTap(e) {
    const { type } = e.currentTarget.dataset
    this.setData({
      typeFilter: type === this.data.typeFilter ? null : type
    })
    this.loadEntitlements()
  },

  // 选择状态筛选
  onStatusFilterTap(e) {
    const { status } = e.currentTarget.dataset
    this.setData({
      statusFilter: status === this.data.statusFilter ? null : status
    })
    this.loadEntitlements()
  },

  // 权益点击
  onEntitlementTap(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/entitlement/entitlement-detail/entitlement-detail?id=${id}`
    })
  }
})

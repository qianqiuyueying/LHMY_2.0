// pages/order/order.js
// 订单列表

const api = require('../../utils/api')
const app = getApp()
const { formatLocalDateTime } = require('../../utils/time')

Page({
  data: {
    orders: [],
    // Tab筛选
    currentTab: 'all', // all/pending/paid/refunded
    // 类型筛选：all/PRODUCT/SERVICE_PACKAGE
    currentType: 'all',
    loading: true
  },

  onLoad() {
    this.loadOrders()
  },

  onShow() {
    // 自定义 TabBar：每次显示时同步选中态
    const tabBar = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tabBar && tabBar.setData) {
      tabBar.setData({ selected: 3 })
    }

    // 每次显示时刷新订单列表
    this.loadOrders()
  },

  onPullDownRefresh() {
    this.loadOrders().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 切换Tab
  onTabTap(e) {
    const { tab } = e.currentTarget.dataset
    this.setData({
      currentTab: tab,
      page: 1,
      hasMore: true
    })
    this.loadOrders()
  },

  // 切换订单类型
  onTypeTap(e) {
    const { type } = e.currentTarget.dataset
    this.setData({
      currentType: type,
      page: 1,
      hasMore: true
    })
    this.loadOrders()
  },

  // 加载订单列表
  async loadOrders() {
    if (!app.globalData.token) {
      wx.showModal({
        title: '提示',
        content: '请先登录',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/profile/profile' })
          }
        }
      })
      this.setData({ loading: false })
      return
    }

    try {
      const params = {
        page: 1,
        pageSize: 20
      }

      // 根据Tab筛选状态
      if (this.data.currentTab === 'pending') {
        params.paymentStatus = 'PENDING'
      } else if (this.data.currentTab === 'paid') {
        params.paymentStatus = 'PAID'
      } else if (this.data.currentTab === 'refunded') {
        params.paymentStatus = 'REFUNDED'
      }

      // 订单类型筛选
      if (this.data.currentType === 'PRODUCT') {
        params.orderType = 'PRODUCT'
      } else if (this.data.currentType === 'SERVICE_PACKAGE') {
        params.orderType = 'SERVICE_PACKAGE'
      }

      const data = await api.get('/api/v1/orders', params)
      const items = (data?.items || []).map((x) => ({
        ...x,
        // timestamp fields are UTC+Z; display as local time on user-side
        createdAt: formatLocalDateTime(x.createdAt)
      }))
      this.setData({
        orders: items,
        loading: false
      })
    } catch (error) {
      console.error('加载订单列表失败:', error)
      this.setData({ loading: false })
    }
  },

  // 订单点击
  onOrderTap(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/order/order-detail/order-detail?id=${id}`
    })
  }
})

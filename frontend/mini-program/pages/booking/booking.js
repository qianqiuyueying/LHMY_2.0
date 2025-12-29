// pages/booking/booking.js
// 预约列表

const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    bookings: [],
    // 筛选条件
    statusFilter: null,
    loading: true,
    entitlementId: null
  },

  onLoad(options) {
    if (options.entitlementId) {
      this.setData({ entitlementId: options.entitlementId })
    }
    this.loadBookings()
  },

  onShow() {
    this.loadBookings()
  },

  onPullDownRefresh() {
    this.loadBookings().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 加载预约列表
  async loadBookings() {
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
      const params = {}
      if (this.data.statusFilter) {
        params.status = this.data.statusFilter
      }

      const data = await api.get('/api/v1/bookings', params)
      this.setData({
        bookings: data?.items || [],
        loading: false
      })
    } catch (error) {
      console.error('加载预约列表失败:', error)
      this.setData({ loading: false })
    }
  },

  // 选择状态筛选
  onStatusFilterTap(e) {
    const { status } = e.currentTarget.dataset
    this.setData({
      statusFilter: status === this.data.statusFilter ? null : status,
      loading: true
    })
    this.loadBookings()
  },

  // 创建预约
  onCreateBooking() {
    if (!this.data.entitlementId) {
      wx.showModal({
        title: '如何发起预约',
        content: '预约需要先选择一张可用权益。请先到【权益】里打开可用权益详情，再从详情页进入预约。',
        confirmText: '去权益',
        cancelText: '知道了',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/entitlement/entitlement' })
          }
        },
      })
      return
    }
    wx.navigateTo({
      url: `/pages/booking/venue-select/venue-select?entitlementId=${this.data.entitlementId}`
    })
  },

  // 取消预约
  async onCancelBooking(e) {
    const { id } = e.currentTarget.dataset
    
    wx.showModal({
      title: '确认取消',
      content: '确定要取消这个预约吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.del(`/api/v1/bookings/${id}`)
            wx.showToast({
              title: '取消成功',
              icon: 'success'
            })
            this.loadBookings()
          } catch (error) {
            console.error('取消预约失败:', error)
            wx.showToast({
              title: error.message || '取消失败',
              icon: 'none'
            })
          }
        }
      }
    })
  }
})

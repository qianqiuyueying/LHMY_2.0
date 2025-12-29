// pages/booking/booking-result/booking-result.js
// 预约结果页

const api = require('../../../utils/api')

Page({
  data: {
    bookingId: null,
    booking: null,
    venue: null,
    loading: true
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ bookingId: options.id })
      this.loadBookingDetail()
    }
  },

  // 加载预约详情
  async loadBookingDetail() {
    try {
      let booking = null
      const cached = wx.getStorageSync(`booking:${this.data.bookingId}`)
      if (cached && cached.id === this.data.bookingId) {
        booking = cached
      } else {
        // 后端 v1 仅定义 GET /bookings（无 /bookings/{id}），这里用列表兜底查找
        const list = await api.get('/api/v1/bookings', { page: 1, pageSize: 50 })
        booking = (list?.items || []).find(x => x.id === this.data.bookingId) || null
      }

      if (!booking) {
        wx.showToast({ title: '预约信息不存在', icon: 'none' })
        this.setData({ loading: false })
        return
      }

      let venue = null
      if (booking?.venueId) {
        try {
          venue = await api.get(`/api/v1/venues/${booking.venueId}`, {}, false)
        } catch (e) {
          venue = null
        }
      }
      this.setData({
        booking: {
          ...booking,
          venueName: venue?.name || ''
        },
        venue,
        loading: false
      })
    } catch (error) {
      console.error('加载预约详情失败:', error)
      this.setData({ loading: false })
    }
  },

  // 返回预约列表
  onBackToList() {
    wx.navigateBack()
  }
})

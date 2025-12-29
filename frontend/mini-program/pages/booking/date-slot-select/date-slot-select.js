// pages/booking/date-slot-select/date-slot-select.js
// 日期时段选择页

const api = require('../../../utils/api')

function _formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function _nextNDates(n) {
  const list = []
  const now = new Date()
  for (let i = 0; i < n; i++) {
    const d = new Date(now.getTime())
    d.setDate(now.getDate() + i)
    list.push(_formatDate(d))
  }
  return list
}

Page({
  data: {
    venueId: null,
    entitlementId: null,
    orderId: null,
    orderItemId: null,
    serviceType: null,
    selectedDate: null,
    selectedSlot: null,
    dateList: [],
    slots: [],
    loading: true
  },

  onLoad(options) {
    if (options.venueId) {
      this.setData({ venueId: options.venueId })
    }
    if (options.entitlementId) {
      this.setData({ entitlementId: options.entitlementId })
    }
    if (options.orderId) {
      this.setData({ orderId: options.orderId })
    }
    if (options.orderItemId) {
      this.setData({ orderItemId: options.orderItemId })
    }
    if (options.serviceType) {
      this.setData({ serviceType: decodeURIComponent(options.serviceType) })
    }

    const dateList = _nextNDates(7)
    this.setData({
      dateList,
      selectedDate: dateList[0] || null
    })

    this.loadSlotsForSelectedDate()
  },

  async _ensureOrderItemContext() {
    if (this.data.entitlementId) return
    if (!this.data.orderId || !this.data.orderItemId) return
    if (this.data.venueId && this.data.serviceType) return

    const ctx = await api.get(
      '/api/v1/bookings/order-item-context',
      { orderId: this.data.orderId, orderItemId: this.data.orderItemId },
      true
    )
    this.setData({ venueId: ctx.venueId, serviceType: ctx.serviceType })
  },

  async loadSlotsForSelectedDate() {
    if (!this.data.selectedDate) return

    try {
      // ORDER_ITEM 模式：先解析场所与服务类目
      await this._ensureOrderItemContext()
      if (!this.data.venueId) {
        this.setData({ loading: false })
        wx.showToast({ title: '无法获取场所信息', icon: 'none' })
        return
      }

      // 若未携带 serviceType，则兜底从权益读取
      let serviceType = this.data.serviceType
      if (!serviceType) {
        if (!this.data.entitlementId) {
          this.setData({ loading: false })
          wx.showModal({
            title: '无法继续',
            content: '请选择一张可用权益后再选择预约时段。',
            confirmText: '去权益',
            cancelText: '返回',
            success: (res) => {
              if (res.confirm) {
                wx.switchTab({ url: '/pages/entitlement/entitlement' })
              } else {
                wx.navigateBack()
              }
            },
          })
          return
        }
        const entitlement = await api.get(`/api/v1/entitlements/${this.data.entitlementId}`)
        serviceType = entitlement?.serviceType
        this.setData({ serviceType })
      }

      const data = await api.get(
        `/api/v1/venues/${this.data.venueId}/available-slots`,
        { serviceType, date: this.data.selectedDate },
        true
      )

      this.setData({
        slots: data?.slots || [],
        loading: false
      })
    } catch (error) {
      console.error('加载可用时段失败:', error)
      this.setData({ loading: false })
    }
  },

  // 选择日期
  onDateSelect(e) {
    const { date } = e.currentTarget.dataset
    this.setData({ selectedDate: date, selectedSlot: null, loading: true })
    this.loadSlotsForSelectedDate()
  },

  // 选择时段
  onSlotSelect(e) {
    const { slot } = e.currentTarget.dataset
    // 已满不可选
    const found = (this.data.slots || []).find(x => x.timeSlot === slot)
    if (found && Number(found.remainingCapacity) <= 0) return
    this.setData({ selectedSlot: slot })
  },

  // 提交预约
  async onSubmit() {
    if (!this.data.selectedDate || !this.data.selectedSlot) {
      wx.showToast({
        title: '请选择日期和时段',
        icon: 'none'
      })
      return
    }

    // vNow：支持两种预约来源：ENTITLEMENT 或 ORDER_ITEM（基建联防服务型商品）
    if (!this.data.entitlementId && !(this.data.orderId && this.data.orderItemId)) {
      wx.showModal({
        title: '无法提交预约',
        content: '预约需要基于【服务包权益】或【已支付的服务型商品订单】。',
        confirmText: '去权益',
        cancelText: '返回',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/entitlement/entitlement' })
          } else {
            wx.navigateBack()
          }
        },
      })
      return
    }

    try {
      const body = {
        venueId: this.data.venueId,
        bookingDate: this.data.selectedDate,
        timeSlot: this.data.selectedSlot,
      }
      if (this.data.entitlementId) {
        body.entitlementId = this.data.entitlementId
      } else {
        body.orderId = this.data.orderId
        body.orderItemId = this.data.orderItemId
      }

      const booking = await api.post('/api/v1/bookings', body, true, {
        'Idempotency-Key': api.genIdempotencyKey('mp:booking:create')
      })

      // v1：后端未定义 GET /bookings/{id}，预约结果页使用本地缓存回显
      try {
        wx.setStorageSync(`booking:${booking.id}`, booking)
        wx.setStorageSync('lastBookingId', booking.id)
      } catch (e) {}

      wx.redirectTo({
        url: `/pages/booking/booking-result/booking-result?id=${booking.id}`
      })
    } catch (error) {
      console.error('创建预约失败:', error)
      wx.showToast({
        title: error.message || '预约失败',
        icon: 'none'
      })
    }
  }
})

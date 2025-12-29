// pages/order/order-detail/order-detail.js
// 订单详情

const api = require('../../../utils/api')

Page({
  data: {
    orderId: null,
    order: null,
    loading: true,
    paying: false,
    confirming: false,
    paymentStatusText: '',
    fulfillmentStatusText: ''
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ orderId: options.id })
      this.loadOrderDetail()
    }
  },

  // 加载订单详情
  async loadOrderDetail() {
    try {
      const order = await api.get(`/api/v1/orders/${this.data.orderId}`)
      const paymentStatusText =
        order.paymentStatus === 'PENDING'
          ? '待支付'
          : order.paymentStatus === 'PAID'
          ? '已支付'
          : order.paymentStatus === 'REFUNDED'
          ? '已退款'
          : order.paymentStatus === 'FAILED'
          ? '失败'
          : '未知状态'

      const fulfillmentStatusText =
        order.fulfillmentStatus === 'NOT_SHIPPED'
          ? '待发货'
          : order.fulfillmentStatus === 'SHIPPED'
          ? '已发货'
          : order.fulfillmentStatus === 'DELIVERED'
          ? '已妥投'
          : order.fulfillmentStatus === 'RECEIVED'
          ? '已签收'
          : ''
      this.setData({
        order,
        paymentStatusText,
        fulfillmentStatusText,
        loading: false
      })
    } catch (error) {
      console.error('加载订单详情失败:', error)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  // 支付订单
  async onPay() {
    try {
      if (this.data.paying) return
      this.setData({ paying: true })
      const data = await api.post(`/api/v1/orders/${this.data.orderId}/pay`, {
        paymentMethod: 'WECHAT'
      }, true, {
        'Idempotency-Key': api.genIdempotencyKey('mp:order:pay')
      })
      
      // 调用微信支付
      if (data && data.paymentStatus === 'FAILED') {
        wx.showToast({
          title: data.failureReason || '支付失败',
          icon: 'none'
        })
        this.setData({ paying: false })
        return
      }

      if (!data || !data.wechatPayParams) {
        wx.showToast({
          title: data?.failureReason || '支付暂不可用，请稍后重试',
          icon: 'none'
        })
        this.setData({ paying: false })
        return
      }

      if (data.wechatPayParams) {
        wx.requestPayment({
          ...data.wechatPayParams,
          success: () => {
            wx.showToast({
              title: '支付成功',
              icon: 'success'
            })
            // 刷新订单详情
            this.loadOrderDetail()
            this.setData({ paying: false })
          },
          fail: (err) => {
            console.error('支付失败:', err)
            const msg = (err && err.errMsg && err.errMsg.includes('cancel')) ? '已取消支付' : '支付失败'
            wx.showToast({
              title: msg,
              icon: 'none'
            })
            this.setData({ paying: false })
          }
        })
      }
    } catch (error) {
      console.error('发起支付失败:', error)
      wx.showToast({
        title: error.message || '支付失败',
        icon: 'none'
      })
      this.setData({ paying: false })
    }
  }

  ,

  onBookService(e) {
    try {
      const itemId = e?.currentTarget?.dataset?.itemId
      if (!this.data.orderId || !itemId) return
      wx.navigateTo({
        url: `/pages/booking/date-slot-select/date-slot-select?orderId=${this.data.orderId}&orderItemId=${itemId}`
      })
    } catch (err) {
      console.error('跳转预约失败:', err)
      wx.showToast({ title: '无法进入预约', icon: 'none' })
    }
  },

  async onConfirmReceived() {
    try {
      if (this.data.confirming) return
      this.setData({ confirming: true })
      await api.post(
        `/api/v1/orders/${this.data.orderId}/confirm-received`,
        {},
        true,
        { 'Idempotency-Key': api.genIdempotencyKey('mp:order:confirm-received') }
      )
      wx.showToast({ title: '已确认收货', icon: 'success' })
      this.loadOrderDetail()
      this.setData({ confirming: false })
    } catch (error) {
      console.error('确认收货失败:', error)
      wx.showToast({ title: error?.message || '操作失败', icon: 'none' })
      this.setData({ confirming: false })
    }
  }
})

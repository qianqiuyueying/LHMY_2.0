// pages/mall/cart/cart.js
// 购物车

const api = require('../../../utils/api')
const app = getApp()

Page({
  data: {
    cartItems: [],
    selectedItems: [],
    totalAmount: 0,
    loading: true,
    selectedAddress: null,
    selectedAddressId: '',
    needShipping: false,
    mixedFulfillment: false
  },

  onLoad() {
    this.loadCart()
  },

  onShow() {
    // 每次显示时刷新购物车
    this.loadCart()

    // 回跳：地址选择
    try {
      const addr = wx.getStorageSync('mp_selected_address') || null
      const addrId = wx.getStorageSync('mp_selected_address_id') || ''
      if (addr && addrId) {
        this.setData({ selectedAddress: addr, selectedAddressId: String(addrId) })
      }

      const pending = wx.getStorageSync('mp_pending_cart_checkout') || null
      if (pending && addrId) {
        wx.removeStorageSync('mp_pending_cart_checkout')
        wx.removeStorageSync('mp_selected_address_id')
        // selectedAddress 保留，便于用户下次继续用
        this.createOrderFromCartWithAddress(String(addrId))
      }
    } catch (e) {}
  },

  // 加载购物车
  async loadCart() {
    // TODO: 实现购物车API
    // 当前简化处理，使用本地存储
    try {
      this.setData({ loading: true })
      const cartItems = wx.getStorageSync('cart') || []
      this.setData({
        cartItems,
        loading: false
      })
      this.calculateTotal()
    } catch (error) {
      console.error('加载购物车失败:', error)
      this.setData({ loading: false })
    }
  },

  // 切换选中状态
  onToggleSelect(e) {
    const { id } = e.currentTarget.dataset
    const selectedItems = [...this.data.selectedItems]
    const index = selectedItems.indexOf(id)
    
    if (index > -1) {
      selectedItems.splice(index, 1)
    } else {
      selectedItems.push(id)
    }
    
    this.setData({ selectedItems })
    this.calculateTotal()
  },

  // 数量减少
  onQuantityDecrease(e) {
    const { id } = e.currentTarget.dataset
    const cartItems = this.data.cartItems.map(item => {
      if (item.id === id && item.quantity > 1) {
        return { ...item, quantity: item.quantity - 1 }
      }
      return item
    })
    this.setData({ cartItems })
    wx.setStorageSync('cart', cartItems)
    this.calculateTotal()
  },

  // 数量增加
  onQuantityIncrease(e) {
    const { id } = e.currentTarget.dataset
    const cartItems = this.data.cartItems.map(item => {
      if (item.id === id) {
        return { ...item, quantity: item.quantity + 1 }
      }
      return item
    })
    this.setData({ cartItems })
    wx.setStorageSync('cart', cartItems)
    this.calculateTotal()
  },

  // 计算总价
  calculateTotal() {
    let total = 0
    this.data.cartItems.forEach(item => {
      if (this.data.selectedItems.includes(item.id)) {
        total += (item.price || 0) * item.quantity
      }
    })
    this.setData({ totalAmount: total })
    this.refreshCheckoutMeta()
  },

  refreshCheckoutMeta() {
    const selected = (this.data.cartItems || []).filter((x) => this.data.selectedItems.includes(x.id))
    const types = new Set()
    selected.forEach((x) => {
      const t = String(x.fulfillmentType || '').trim()
      types.add(t || 'UNKNOWN')
    })
    const hasPhysical = types.has('PHYSICAL_GOODS')
    const hasService = types.has('SERVICE')
    const hasUnknown = types.has('UNKNOWN')
    this.setData({
      needShipping: hasPhysical || hasUnknown,
      mixedFulfillment: (hasPhysical && hasService) || (types.size > 1 && hasUnknown),
    })
  },

  // 全选/取消全选
  onToggleSelectAll() {
    if (this.data.selectedItems.length === this.data.cartItems.length) {
      // 取消全选
      this.setData({ selectedItems: [] })
    } else {
      // 全选
      const allIds = this.data.cartItems.map(item => item.id)
      this.setData({ selectedItems: allIds })
    }
    this.calculateTotal()
  },

  onChooseAddress() {
    wx.navigateTo({ url: '/pages/address/address-list/address-list?mode=select' })
  },

  // 去结算
  async onCheckout() {
    if (this.data.selectedItems.length === 0) {
      wx.showToast({
        title: '请选择商品',
        icon: 'none'
      })
      return
    }

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
      return
    }

    try {
      // 不允许混合下单（后端 v2 最小：同单不混 SERVICE 与 PHYSICAL_GOODS）
      this.refreshCheckoutMeta()
      if (this.data.mixedFulfillment) {
        wx.showToast({ title: '请分开选择：服务与物流商品不能混合下单', icon: 'none' })
        return
      }

      // 物流商品需要先选地址
      if (this.data.needShipping && !this.data.selectedAddressId) {
        try {
          wx.setStorageSync('mp_pending_cart_checkout', {
            at: Date.now(),
          })
        } catch (e) {}
        wx.navigateTo({ url: '/pages/address/address-list/address-list?mode=select' })
        return
      }

      // 创建订单
      const items = this.data.cartItems
        .filter(item => this.data.selectedItems.includes(item.id))
        .map(item => ({
          itemType: 'PRODUCT',
          itemId: item.productId,
          quantity: item.quantity
        }))

      const body = { orderType: 'PRODUCT', items }
      if (this.data.needShipping && this.data.selectedAddressId) {
        body.shippingAddressId = this.data.selectedAddressId
      }

      const order = await api.post('/api/v1/orders', body, true, {
        'Idempotency-Key': api.genIdempotencyKey('mp:order:create')
      })

      // 清除已选中的购物车项
      const remainingItems = this.data.cartItems.filter(
        item => !this.data.selectedItems.includes(item.id)
      )
      wx.setStorageSync('cart', remainingItems)

      // 跳转到订单详情
      wx.redirectTo({
        url: `/pages/order/order-detail/order-detail?id=${order.id}`
      })
    } catch (error) {
      console.error('创建订单失败:', error)
      wx.showToast({
        title: '下单失败',
        icon: 'none'
      })
    }
  }

  ,

  async createOrderFromCartWithAddress(addressId) {
    // 使用当前选中的 cart 项创建订单（回跳自动触发）
    try {
      if (this.data.selectedItems.length === 0) return
      const items = this.data.cartItems
        .filter(item => this.data.selectedItems.includes(item.id))
        .map(item => ({
          itemType: 'PRODUCT',
          itemId: item.productId,
          quantity: item.quantity
        }))

      const order = await api.post('/api/v1/orders', {
        orderType: 'PRODUCT',
        shippingAddressId: addressId,
        items
      }, true, {
        'Idempotency-Key': api.genIdempotencyKey('mp:order:create')
      })

      // 清除已选中的购物车项
      const remainingItems = this.data.cartItems.filter(
        item => !this.data.selectedItems.includes(item.id)
      )
      wx.setStorageSync('cart', remainingItems)

      wx.redirectTo({ url: `/pages/order/order-detail/order-detail?id=${order.id}` })
    } catch (error) {
      console.error('创建订单失败:', error)
      wx.showToast({ title: error?.message || '下单失败', icon: 'none' })
    }
  }
})

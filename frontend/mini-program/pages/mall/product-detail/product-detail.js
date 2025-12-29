// pages/mall/product-detail/product-detail.js
// 商品详情

const api = require('../../../utils/api')
const app = getApp()
const { computeDisplayPrice } = require('../../../utils/price')
const _cfg = require('../../../utils/config') || {}
const getApiBaseUrl = _cfg.getApiBaseUrl || (_cfg.default && _cfg.default.getApiBaseUrl)

function _absStaticUrl(raw) {
  const u = String(raw || '').trim()
  if (!u) return ''
  if (u.startsWith('http://') || u.startsWith('https://')) return u
  if (!u.startsWith('/static/')) return u
  const base = String(getApiBaseUrl() || '').trim().replace(/\/$/, '')
  if (!base) return u
  return `${base}${u}`
}

Page({
  data: {
    productId: null,
    product: null,
    // 价格优先级：活动价 > 会员价 > 员工价 > 原价
    displayPrice: null,
    priceType: 'original', // original/member/employee/activity
    originalPrice: 0,
    hasMemberPrice: false,
    hasEmployeePrice: false,
    hasActivityPrice: false,
    quantity: 1,
    loading: true,
    heroUrlAbs: '',
    galleryUrlsAbs: [],
  },

  onPreviewImage(e) {
    try {
      const current = String(e?.currentTarget?.dataset?.url || '').trim()
      const urls = Array.isArray(this.data.galleryUrlsAbs) && this.data.galleryUrlsAbs.length > 0 ? this.data.galleryUrlsAbs : []
      const fallbackUrls = this.data.heroUrlAbs ? [this.data.heroUrlAbs] : []
      const previewUrls = urls.length > 0 ? urls : fallbackUrls
      if (previewUrls.length === 0) return
      wx.previewImage({ current: current || previewUrls[0], urls: previewUrls })
    } catch (err) {
      console.warn('previewImage failed:', err)
    }
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ productId: options.id })
      this.loadProductDetail()
    }
  },

  onShow() {
    // 处理“物流商品：先选地址再下单”的回跳
    try {
      const pending = wx.getStorageSync('mp_pending_buy_now') || null
      const addrId = wx.getStorageSync('mp_selected_address_id') || ''
      if (pending && addrId) {
        wx.removeStorageSync('mp_pending_buy_now')
        wx.removeStorageSync('mp_selected_address_id')
        this.createOrderWithAddress(pending, String(addrId))
      }
    } catch (e) {}
  },

  // 加载商品详情
  async loadProductDetail() {
    try {
      const product = await api.get(`/api/v1/products/${this.data.productId}`, {}, false)

      const gallery = Array.isArray(product?.imageUrls) ? product.imageUrls.map((x) => String(x || '').trim()).filter(Boolean) : []
      const cover = String(product?.coverImageUrl || '') || (gallery[0] || '') || ''
      const galleryUrlsAbs = gallery.map((u) => _absStaticUrl(u)).filter(Boolean)
      const heroUrlAbs = _absStaticUrl(cover)
      
      // 计算显示价格（价格优先级）
      const userInfo = app.globalData.userInfo
      const computed = computeDisplayPrice(product.price, userInfo?.identities || [])
      
      this.setData({
        product,
        displayPrice: computed.displayPrice,
        priceType: computed.priceType,
        originalPrice: computed.originalPrice,
        hasMemberPrice: computed.hasMemberPrice,
        hasEmployeePrice: computed.hasEmployeePrice,
        hasActivityPrice: computed.hasActivityPrice,
        loading: false,
        heroUrlAbs,
        galleryUrlsAbs,
      })
    } catch (error) {
      console.error('加载商品详情失败:', error)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    }
  },

  // 数量减少
  onQuantityDecrease() {
    if (this.data.quantity > 1) {
      this.setData({ quantity: this.data.quantity - 1 })
    }
  },

  // 数量增加
  onQuantityIncrease() {
    this.setData({ quantity: this.data.quantity + 1 })
  },

  // 加入购物车
  async onAddToCart() {
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
      // v1：使用本地存储实现购物车（事实清单：购物车 v1 简化处理）
      const product = this.data.product
      if (!product || !this.data.productId) {
        wx.showToast({ title: '商品信息缺失', icon: 'none' })
        return
      }

      const cartKey = 'cart'
      const cartItems = wx.getStorageSync(cartKey) || []

      const productId = String(this.data.productId)
      const displayPrice = Number(this.data.displayPrice || 0)
      const quantityToAdd = Number(this.data.quantity || 1)

      const imageUrl =
        product.imageUrl ||
        (Array.isArray(product.imageUrls) ? product.imageUrls[0] : '') ||
        ''

      const idx = cartItems.findIndex((x) => String(x.id) === productId)
      if (idx > -1) {
        const prevQty = Number(cartItems[idx]?.quantity || 0)
        cartItems[idx] = {
          ...cartItems[idx],
          // 同商品再次加入：数量累加（与购物车页数量控制保持一致口径）
          quantity: prevQty + quantityToAdd,
          // 价格/标题等以最新加载为准
          title: product.title || cartItems[idx].title,
          imageUrl: imageUrl || cartItems[idx].imageUrl,
          price: displayPrice,
          productId,
          fulfillmentType: product.fulfillmentType || cartItems[idx].fulfillmentType || null,
          shippingFee: product.shippingFee != null ? Number(product.shippingFee) : (cartItems[idx].shippingFee || 0),
        }
      } else {
        cartItems.push({
          // cart 页以 item.id 作为选择/数量变更主键
          id: productId,
          productId,
          title: product.title || '',
          imageUrl,
          price: displayPrice,
          quantity: quantityToAdd,
          fulfillmentType: product.fulfillmentType || null,
          shippingFee: product.shippingFee != null ? Number(product.shippingFee) : 0,
        })
      }

      wx.setStorageSync(cartKey, cartItems)

      wx.showToast({ title: '已加入购物车', icon: 'success' })
    } catch (error) {
      console.error('加入购物车失败:', error)
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  },

  // 立即购买
  async onBuyNow() {
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

    const product = this.data.product
    const isPhysical = String(product?.fulfillmentType || '') === 'PHYSICAL_GOODS'
    if (isPhysical) {
      // 物流商品：先选择收货地址
      try {
        wx.setStorageSync('mp_pending_buy_now', {
          productId: String(this.data.productId),
          quantity: Number(this.data.quantity || 1),
        })
      } catch (e) {}
      wx.navigateTo({ url: '/pages/address/address-list/address-list?mode=select' })
      return
    }

    // 立即创建订单（服务型无需地址）
    try {
      const order = await api.post('/api/v1/orders', {
        orderType: 'PRODUCT',
        items: [{
          itemType: 'PRODUCT',
          itemId: this.data.productId,
          quantity: this.data.quantity
        }]
      }, true, {
        'Idempotency-Key': api.genIdempotencyKey('mp:order:create')
      })
      
      // 跳转到支付页
      wx.navigateTo({
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

  async createOrderWithAddress(pending, addressId) {
    try {
      const productId = String(pending?.productId || '')
      const quantity = Number(pending?.quantity || 1)
      if (!productId || !addressId) return
      const order = await api.post(
        '/api/v1/orders',
        {
          orderType: 'PRODUCT',
          shippingAddressId: addressId,
          items: [{ itemType: 'PRODUCT', itemId: productId, quantity }],
        },
        true,
        { 'Idempotency-Key': api.genIdempotencyKey('mp:order:create') }
      )
      wx.navigateTo({ url: `/pages/order/order-detail/order-detail?id=${order.id}` })
    } catch (error) {
      console.error('创建订单失败:', error)
      wx.showToast({ title: error?.message || '下单失败', icon: 'none' })
    }
  }
})

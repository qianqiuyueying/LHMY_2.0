// pages/entitlement/entitlement-detail/entitlement-detail.js
// 权益详情

const api = require('../../../utils/api')
const qrcode = require('../../../utils/qrcode-generator')

Page({
  data: {
    entitlementId: null,
    entitlement: null,
    qrCodeImage: '',
    qrState: 'loading', // loading/ready/empty/error
    qrHint: '',
    loading: true
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ entitlementId: options.id })
      this.loadEntitlementDetail()
    }
  },

  // 加载权益详情
  async loadEntitlementDetail() {
    try {
      const entitlement = await api.get(`/api/v1/entitlements/${this.data.entitlementId}`)

      // v1 固化：Entitlement.qrCode 为“二维码 payload 文本”（不是图片 URL），由小程序端生成二维码图片展示
      // 用户视角：qrCode 缺失或生成失败必须呈现“明确状态”，不能长期显示“加载中”
      const payload = String(entitlement?.qrCode || '').trim()
      let qrCodeImage = ''
      let qrState = 'loading'
      let qrHint = '二维码生成中…'

      if (!payload) {
        qrState = 'empty'
        qrHint = '暂无核销二维码，可使用券码核销（如适用）'
      } else {
        qrCodeImage = await this.renderQr(payload)
        if (qrCodeImage) {
          qrState = 'ready'
          qrHint = '请向工作人员出示二维码或券码'
        } else {
          qrState = 'error'
          qrHint = '二维码生成失败，请使用券码核销或稍后重试'
        }
      }

      this.setData({
        entitlement,
        qrCodeImage,
        qrState,
        qrHint,
        loading: false
      })
    } catch (error) {
      console.error('加载权益详情失败:', error)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  onRetryQr() {
    // 仅重试二维码生成（不重新拉详情，避免额外请求；必要时可改为 reload）
    const payload = String(this.data.entitlement?.qrCode || '').trim()
    if (!payload) {
      this.setData({
        qrState: 'empty',
        qrHint: '暂无核销二维码，可使用券码核销（如适用）',
        qrCodeImage: '',
      })
      return
    }
    this.setData({ qrState: 'loading', qrHint: '二维码生成中…', qrCodeImage: '' })
    this.renderQr(payload).then((img) => {
      if (img) {
        this.setData({ qrState: 'ready', qrHint: '请向工作人员出示二维码或券码', qrCodeImage: img })
      } else {
        this.setData({ qrState: 'error', qrHint: '二维码生成失败，请使用券码核销或稍后重试', qrCodeImage: '' })
      }
    })
  },

  renderQr(payload) {
    const text = String(payload || '').trim()
    if (!text) return Promise.resolve('')

    // 兼容：若后端未来返回图片 URL，则直接展示
    if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('/')) {
      return Promise.resolve(text)
    }

    const sizePx = 200 // 与样式 400rpx 大致匹配（不追求像素级）

    return new Promise((resolve) => {
      try {
        const qr = qrcode(0, 'M')
        qr.addData(text, 'Byte')
        qr.make()

        const count = qr.getModuleCount()
        const ctx = wx.createCanvasContext('qrCanvas', this)
        const tileW = sizePx / count
        const tileH = sizePx / count

        // 背景
        ctx.setFillStyle('#ffffff')
        ctx.fillRect(0, 0, sizePx, sizePx)

        // 前景
        ctx.setFillStyle('#000000')
        for (let row = 0; row < count; row++) {
          for (let col = 0; col < count; col++) {
            if (qr.isDark(row, col)) {
              const x = Math.round(col * tileW)
              const y = Math.round(row * tileH)
              const w = Math.ceil(tileW)
              const h = Math.ceil(tileH)
              ctx.fillRect(x, y, w, h)
            }
          }
        }

        ctx.draw(false, () => {
          wx.canvasToTempFilePath(
            {
              canvasId: 'qrCanvas',
              width: sizePx,
              height: sizePx,
              destWidth: sizePx,
              destHeight: sizePx,
              success: (res) => resolve(res.tempFilePath || ''),
              fail: () => resolve(''),
            },
            this
          )
        })
      } catch (e) {
        console.error('生成二维码失败:', e)
        resolve('')
      }
    })
  },

  // 复制券码
  onCopyVoucherCode() {
    const code = this.data.entitlement?.voucherCode
    if (!code) {
      wx.showToast({ title: '暂无券码', icon: 'none' })
      return
    }
    wx.setClipboardData({
      data: code,
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success'
        })
      }
    })
  },

  // 查看适用场所
  onViewVenues() {
    wx.navigateTo({
      url: `/pages/booking/venue-select/venue-select?entitlementId=${this.data.entitlementId}`
    })
  },

  // 去预约
  onGoBooking() {
    wx.navigateTo({
      url: `/pages/booking/venue-select/venue-select?entitlementId=${this.data.entitlementId}`
    })
  }
})

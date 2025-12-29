// pages/address/address-list/address-list.js

const api = require('../../../utils/api')

const STORAGE_SELECTED_ADDR = 'mp_selected_address'
const STORAGE_SELECTED_ADDR_ID = 'mp_selected_address_id'

Page({
  data: {
    loading: true,
    addresses: [],
    mode: 'manage' // manage|select
  },

  onLoad(options) {
    const mode = (options && options.mode) ? String(options.mode) : 'manage'
    this.setData({ mode: mode === 'select' ? 'select' : 'manage' })
  },

  onShow() {
    this.loadAddresses()
  },

  async loadAddresses() {
    try {
      this.setData({ loading: true })
      const data = await api.get('/api/v1/user/addresses')
      this.setData({
        addresses: data?.items || [],
        loading: false
      })
    } catch (e) {
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onAdd() {
    wx.navigateTo({ url: '/pages/address/address-edit/address-edit' })
  },

  onEdit(e) {
    const id = e?.currentTarget?.dataset?.id
    if (!id) return
    wx.navigateTo({ url: `/pages/address/address-edit/address-edit?id=${id}` })
  },

  async onDelete(e) {
    const id = e?.currentTarget?.dataset?.id
    if (!id) return
    wx.showModal({
      title: '删除地址',
      content: '确定要删除该地址吗？',
      confirmText: '删除',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.del(`/api/v1/user/addresses/${id}`)
          wx.showToast({ title: '已删除', icon: 'success' })
          this.loadAddresses()
        } catch (err) {
          wx.showToast({ title: '删除失败', icon: 'none' })
        }
      }
    })
  },

  async onSetDefault(e) {
    const id = e?.currentTarget?.dataset?.id
    if (!id) return
    try {
      await api.post(`/api/v1/user/addresses/${id}/set-default`, {})
      wx.showToast({ title: '已设为默认', icon: 'success' })
      this.loadAddresses()
    } catch (err) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  onSelect(e) {
    if (this.data.mode !== 'select') return
    const id = e?.currentTarget?.dataset?.id
    if (!id) return
    const addr = (this.data.addresses || []).find((x) => String(x.id) === String(id))
    if (!addr) return
    try {
      wx.setStorageSync(STORAGE_SELECTED_ADDR, addr)
      wx.setStorageSync(STORAGE_SELECTED_ADDR_ID, addr.id)
    } catch (err) {}
    wx.navigateBack()
  }
})



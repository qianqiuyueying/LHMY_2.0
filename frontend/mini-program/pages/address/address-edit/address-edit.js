// pages/address/address-edit/address-edit.js

const api = require('../../../utils/api')

function _parseRegionCode(code) {
  const raw = String(code || '')
  const parts = raw.split(':')
  return { prefix: parts[0] || '', value: parts[1] || '' }
}

Page({
  data: {
    id: '',
    loading: true,
    saving: false,
    form: {
      receiverName: '',
      receiverPhone: '',
      countryCode: 'COUNTRY:CN',
      provinceCode: null,
      cityCode: null,
      addressLine: '',
      postalCode: null,
      isDefault: false
    },

    regionItems: [],
    provinceOptions: [],
    cityOptions: [],
    selectedProvinceName: '',
    selectedCityName: ''
  },

  onLoad(options) {
    const id = options && options.id ? String(options.id) : ''
    this.setData({ id })
    this.init()
  },

  async init() {
    await Promise.allSettled([this.loadRegionItems(), this.loadAddressIfEditing()])
    this.setData({ loading: false })
  },

  async loadRegionItems() {
    try {
      const data = await api.get('/api/v1/regions/cities', {}, false, true)
      const items = data?.items || []
      const provinces = items.filter((x) => String(x.code || '').startsWith('PROVINCE:'))
      const cities = items.filter((x) => String(x.code || '').startsWith('CITY:'))
      // 省份列表优先使用配置中的 PROVINCE；若缺失，则用 CITY 推导省级前缀（降级）
      const provinceOptions = provinces.length > 0 ? provinces : []

      this.setData({
        regionItems: items,
        provinceOptions,
        _citiesAll: cities
      })

      this.rebuildCityOptions()
    } catch (e) {
      // 配置缺失不影响最小地址簿可用：仅保存 addressLine
      this.setData({ regionItems: [], provinceOptions: [], cityOptions: [] })
    }
  },

  async loadAddressIfEditing() {
    if (!this.data.id) return
    try {
      const data = await api.get('/api/v1/user/addresses')
      const addr = (data?.items || []).find((x) => String(x.id) === String(this.data.id))
      if (!addr) return
      const form = {
        receiverName: addr.receiverName || '',
        receiverPhone: addr.receiverPhone || '',
        countryCode: addr.countryCode || 'COUNTRY:CN',
        provinceCode: addr.provinceCode || null,
        cityCode: addr.cityCode || null,
        addressLine: addr.addressLine || '',
        postalCode: addr.postalCode || null,
        isDefault: !!addr.isDefault
      }
      this.setData({ form })
      this.syncSelectedRegionNames()
      this.rebuildCityOptions()
    } catch (e) {}
  },

  rebuildCityOptions() {
    const provinces = this.data.provinceOptions || []
    const citiesAll = this.data._citiesAll || []
    const selectedProvinceCode = this.data.form?.provinceCode
    if (!provinces.length) {
      // 没有省份数据时不展示城市 picker
      this.setData({ cityOptions: [] })
      return
    }
    if (!selectedProvinceCode) {
      this.setData({ cityOptions: [] })
      return
    }
    const pv = _parseRegionCode(selectedProvinceCode).value
    const pvPrefix2 = pv.slice(0, 2)
    const cityOptions = citiesAll.filter((x) => {
      const v = _parseRegionCode(x.code).value
      return v.slice(0, 2) === pvPrefix2
    })
    this.setData({ cityOptions })
  },

  syncSelectedRegionNames() {
    const provinces = this.data.provinceOptions || []
    const citiesAll = this.data._citiesAll || []
    const province = provinces.find((x) => x.code === this.data.form.provinceCode)
    const city = citiesAll.find((x) => x.code === this.data.form.cityCode)
    this.setData({
      selectedProvinceName: province ? province.name : '',
      selectedCityName: city ? city.name : ''
    })
  },

  onInput(e) {
    const key = e?.currentTarget?.dataset?.key
    const val = e?.detail?.value
    if (!key) return
    this.setData({ [`form.${key}`]: val })
  },

  onDefaultToggle(e) {
    this.setData({ 'form.isDefault': !!e?.detail?.value })
  },

  onProvinceChange(e) {
    const idx = Number(e?.detail?.value || 0)
    const opt = (this.data.provinceOptions || [])[idx]
    if (!opt) return
    this.setData({
      'form.provinceCode': opt.code,
      'form.cityCode': null,
      selectedProvinceName: opt.name,
      selectedCityName: ''
    })
    this.rebuildCityOptions()
  },

  onCityChange(e) {
    const idx = Number(e?.detail?.value || 0)
    const opt = (this.data.cityOptions || [])[idx]
    if (!opt) return
    this.setData({
      'form.cityCode': opt.code,
      selectedCityName: opt.name
    })
  },

  async onSave() {
    if (this.data.saving) return
    const f = this.data.form || {}
    const receiverName = String(f.receiverName || '').trim()
    const receiverPhone = String(f.receiverPhone || '').trim()
    const addressLine = String(f.addressLine || '').trim()
    if (!receiverName) return wx.showToast({ title: '请填写收件人', icon: 'none' })
    if (!receiverPhone) return wx.showToast({ title: '请填写手机号', icon: 'none' })
    if (!addressLine) return wx.showToast({ title: '请填写详细地址', icon: 'none' })

    const body = {
      receiverName,
      receiverPhone,
      countryCode: f.countryCode || 'COUNTRY:CN',
      provinceCode: f.provinceCode || null,
      cityCode: f.cityCode || null,
      districtCode: null,
      addressLine,
      postalCode: f.postalCode || null,
      isDefault: !!f.isDefault
    }

    try {
      this.setData({ saving: true })
      if (this.data.id) {
        await api.put(`/api/v1/user/addresses/${this.data.id}`, body)
      } else {
        await api.post('/api/v1/user/addresses', body)
      }
      wx.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    } catch (e) {
      wx.showToast({ title: e?.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  }
})



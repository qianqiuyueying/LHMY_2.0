// pages/ai-chat/ai-chat.js
// AI对话页

const api = require('../../utils/api')
const app = getApp()

const DISCLAIMER_DISMISSED_KEY = 'mp:aiChat:disclaimerDismissed'
const DEFAULT_SCENE = 'knowledge_qa'

Page({
  data: {
    messages: [],
    inputValue: '',
    loading: false,
    canSend: false,
    aiDisabled: false,
    aiDisabledMessage: '',
    // 免责声明
    showDisclaimer: true
  },

  onLoad() {
    // 检查登录状态
    const token = app.globalData.token || wx.getStorageSync('token')
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '使用AI对话需要先登录',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/profile/profile' })
          } else {
            wx.navigateBack()
          }
        }
      })
      return
    }

    // 事实清单：首次显示免责声明（关闭后本地记忆）
    const dismissed = !!wx.getStorageSync(DISCLAIMER_DISMISSED_KEY)
    this.setData({ showDisclaimer: !dismissed })
  },

  // 关闭免责声明
  onCloseDisclaimer() {
    try {
      wx.setStorageSync(DISCLAIMER_DISMISSED_KEY, true)
    } catch (e) {}
    this.setData({ showDisclaimer: false })
  },

  // 输入内容
  onInput(e) {
    const v = String(e.detail.value || '')
    this.setData({ inputValue: v, canSend: v.trim().length > 0 })
  },

  // 发送消息
  async onSend() {
    const content = String(this.data.inputValue || '').trim()
    if (!content || this.data.loading || this.data.aiDisabled) return

    const userMessage = {
      role: 'user',
      content
    }

    const nextMessages = [...this.data.messages, userMessage]

    // 添加用户消息
    this.setData({
      messages: nextMessages,
      inputValue: '',
      canSend: false,
      loading: true
    })

    try {
      // 调用AI接口
      const response = await api.post('/api/v1/ai/chat', {
        scene: DEFAULT_SCENE,
        message: content
      }, true, { 'Idempotency-Key': api.genIdempotencyKey('mp-ai') })

      // 添加AI回复
      const aiMessage = {
        role: 'assistant',
        content: response.message?.content || '抱歉，我无法回答这个问题'
      }

      this.setData({
        messages: [...this.data.messages, aiMessage],
        loading: false
      })
    } catch (error) {
      console.error('AI对话失败:', error)
      // 后端可能返回：FORBIDDEN（AI 功能已停用/配置缺失）
      if (error?.code === 'FORBIDDEN') {
        this.setData({
          loading: false,
          aiDisabled: true,
          aiDisabledMessage: error?.message || 'AI 功能暂未开放',
        })
        return
      }

      wx.showToast({ title: error?.message || '对话失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },

  onGoSupport() {
    wx.navigateTo({ url: '/pages/support/support' })
  },
})

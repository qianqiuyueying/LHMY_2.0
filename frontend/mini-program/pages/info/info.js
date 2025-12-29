// pages/info/info.js
// 信息页（可配置）

const api = require('../../utils/api')
const { navigateByJump } = require('../../utils/navigate')
const _cfg = require('../../utils/config') || {}
const getApiBaseUrl = _cfg.getApiBaseUrl || (_cfg.default && _cfg.default.getApiBaseUrl)

function _rewriteHtmlAssetUrls(html) {
  const raw = String(html || '')
  if (!raw) return raw
  const base = String(getApiBaseUrl() || '').trim().replace(/\/$/, '')
  if (!base) return raw
  // 将 <img src="/static/..."> 转为绝对地址，保证小程序 rich-text 能加载
  let out = raw.replace(/(<img[^>]+src=["'])(\/static\/[^"']*)(["'][^>]*>)/gi, `$1${base}$2$3`)

  // 小程序 rich-text 对外层 wxss 的选择器支持不稳定：直接给 img 注入内联样式兜底
  // - 限制最大宽度，避免超大图片撑爆布局
  // - 高度自适应，保持比例
  // - display:block + margin 让排版更像文章
  out = out.replace(/<img\b([^>]*?)>/gi, (m, attrs) => {
    const a = String(attrs || '')
      // 移除 width/height 属性（避免固定尺寸）
      .replace(/\swidth\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\sheight\s*=\s*["'][^"']*["']/gi, '')

    const hasStyle = /\sstyle\s*=/.test(a)
    if (hasStyle) {
      return `<img${a.replace(/\sstyle\s*=\s*["']([^"']*)["']/i, (_mm, s) => {
        const merged = `${String(s || '').trim().replace(/;?$/, ';')}max-width:100%;height:auto;display:block;margin:10px 0;`
        return ` style="${merged}"`
      })}>`
    }
    return `<img${a} style="max-width:100%;height:auto;display:block;margin:10px 0;">`
  })

  return out
}

Page({
  data: {
    pageId: null,
    pageConfig: null, // INFO_PAGE 的 config（含 blocks）
    loading: true,
    errorMessage: ''
  },

  onLoad(options) {
    if (options.pageId) {
      this.setData({ pageId: options.pageId })
      this.loadPageConfig()
    }
  },

  // 加载页面配置
  async loadPageConfig() {
    try {
      this.setData({ loading: true, errorMessage: '' })
      const resp = await api.get(`/api/v1/mini-program/pages/${this.data.pageId}`, {}, false)
      // design.md：response = { id, type, config, version }
      const config = resp?.config || null
      if (!config) {
        this.setData({
          pageConfig: null,
          loading: false,
          errorMessage: '页面配置不存在或不可用',
        })
        return
      }
      const merged = await this.resolveCmsBlocks(config)
      this.setData({
        pageConfig: merged,
        loading: false
      })
    } catch (error) {
      console.error('加载页面配置失败:', error)
      this.setData({
        loading: false,
        errorMessage: '加载失败，请稍后重试',
      })
    }
  },

  // INFO_PAGE：支持 cmsContent block（事实更新：运行时按 contentId 拉取已发布内容）
  async resolveCmsBlocks(config) {
    try {
      const blocks = Array.isArray(config?.blocks) ? config.blocks : []
      const hasCms = blocks.some((b) => b && b.type === 'cmsContent' && b.contentId)
      if (!hasCms) return config

      const nextBlocks = await Promise.all(
        blocks.map(async (b) => {
          if (!b || b.type !== 'cmsContent' || !b.contentId) return b
          const id = String(b.contentId || '').trim()
          if (!id) return b
          try {
            const data = await api.get(`/api/v1/mini-program/cms/contents/${id}`, {}, false, true)
            const html = _rewriteHtmlAssetUrls(String(data?.contentHtml || ''))
            return { type: 'richText', contentHtml: html }
          } catch (e) {
            console.warn('加载 CMS 内容失败:', id, e)
            return { type: 'richText', contentHtml: `<p>内容暂不可用（contentId=${id}）</p>` }
          }
        })
      )
      return { ...config, blocks: nextBlocks }
    } catch (e) {
      console.warn('resolveCmsBlocks 失败:', e)
      return config
    }
  },

  onJumpTap(e) {
    const { jumpType, targetId, title } = e.currentTarget.dataset
    navigateByJump({ jumpType, targetId, title })
  },

  onRetryTap() {
    this.loadPageConfig()
  },

  onBackTap() {
    wx.navigateBack()
  }
})

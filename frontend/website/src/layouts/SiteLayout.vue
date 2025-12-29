<template>
  <n-layout class="site-root">
    <n-layout-header bordered class="site-header">
      <div class="container header-inner">
        <div class="brand" @click="go('/')">
          <div class="brand-logo">LHMY</div>
          <div class="brand-name">陆合铭云健康服务平台</div>
        </div>

        <div class="nav-desktop">
          <n-space :size="16" align="center">
            <n-button
              v-if="navEnabled.home"
              quaternary
              :type="isActive('/') ? 'primary' : 'default'"
              @click="go('/')"
              >首页</n-button
            >
            <n-button
              v-if="navEnabled.business"
              quaternary
              :type="isActive('/business') ? 'primary' : 'default'"
              @click="go('/business')"
            >
              业务线
            </n-button>
            <n-button
              v-if="navEnabled.venues"
              quaternary
              :type="isActive('/venues') ? 'primary' : 'default'"
              @click="go('/venues')"
            >
              场所/服务
            </n-button>
            <n-button
              v-if="navEnabled.content"
              quaternary
              :type="isActive('/content') ? 'primary' : 'default'"
              @click="go('/content')"
            >
              内容中心
            </n-button>
            <n-button
              v-if="navEnabled.about"
              quaternary
              :type="isActive('/about') ? 'primary' : 'default'"
              @click="go('/about')"
            >
              关于我们
            </n-button>
            <n-button
              v-if="navEnabled.contact"
              quaternary
              :type="isActive('/contact') ? 'primary' : 'default'"
              @click="go('/contact')"
            >
              联系我们
            </n-button>
          </n-space>
        </div>

        <div class="actions-desktop">
          <n-space :size="12" align="center">
            <n-button type="primary" ghost @click="openMiniProgram()">进入小程序</n-button>
          </n-space>
        </div>

        <div class="nav-mobile">
          <n-button quaternary class="mobile-menu-btn" @click="drawerOpen = true">
            <span class="mobile-menu-icon" aria-hidden="true">☰</span>
            <span class="mobile-menu-text">菜单</span>
          </n-button>
        </div>
      </div>
    </n-layout-header>

    <n-layout-content class="site-content">
      <maintenance-page
        v-if="maintenance.enabled && !maintenanceAllowPath"
        :title="maintenance.messageTitle"
        :body="maintenance.messageBody"
      />
      <not-open-page v-else-if="blockedByNav" />
      <router-view v-else />
    </n-layout-content>

    <n-layout-footer bordered class="site-footer">
      <div class="container footer-inner">
        <n-alert v-if="footerConfigError" type="warning" show-icon :title="footerConfigError" style="margin-bottom: 12px">
          <n-space style="margin-top: 8px">
            <n-button size="small" @click="loadFooterConfig()">重试</n-button>
          </n-space>
        </n-alert>
        <n-grid :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
          <n-grid-item>
            <div class="footer-col-title">公司信息</div>
            <div class="muted">{{ footerConfig?.companyName || '—' }}</div>
          </n-grid-item>
          <n-grid-item>
            <div class="footer-col-title">合作咨询</div>
            <div class="muted">邮箱：{{ footerConfig?.cooperationEmail || '—' }}</div>
            <div class="muted">电话：{{ footerConfig?.cooperationPhone || '—' }}</div>
          </n-grid-item>
          <n-grid-item>
            <div class="footer-col-title">备案信息</div>
            <div class="muted">
              <template v-if="footerConfig?.icpBeianNo">
                <a v-if="footerConfig?.icpBeianLink" :href="footerConfig.icpBeianLink" target="_blank" rel="noopener noreferrer">
                  {{ footerConfig.icpBeianNo }}
                </a>
                <template v-else>{{ footerConfig.icpBeianNo }}</template>
              </template>
              <template v-else>—</template>
            </div>
          </n-grid-item>
          <n-grid-item>
            <div class="footer-col-title">公众号 / 小程序码</div>
            <n-space :size="12" align="start">
              <div class="qr-box">
                <div class="qr-label muted">公众号</div>
                <n-image v-if="footerConfig?.publicAccountQrUrl" width="88" :src="footerConfig.publicAccountQrUrl" />
                <div v-else class="muted">—</div>
              </div>
              <div class="qr-box">
                <div class="qr-label muted">小程序</div>
                <n-image v-if="footerConfig?.miniProgramQrUrl" width="88" :src="footerConfig.miniProgramQrUrl" />
                <div v-else class="muted">—</div>
              </div>
            </n-space>
          </n-grid-item>
        </n-grid>

        <div class="footer-bottom muted">© {{ new Date().getFullYear() }} LHMY. All rights reserved.</div>
      </div>
    </n-layout-footer>

    <n-drawer v-model:show="drawerOpen" placement="right" :width="280">
      <n-drawer-content title="导航">
        <n-space vertical :size="8">
          <n-button v-if="navEnabled.home" block @click="goAndClose('/')">首页</n-button>
          <n-button v-if="navEnabled.business" block @click="goAndClose('/business')">业务线</n-button>
          <n-button v-if="navEnabled.venues" block @click="goAndClose('/venues')">场所/服务</n-button>
          <n-button v-if="navEnabled.content" block @click="goAndClose('/content')">内容中心</n-button>
          <n-button v-if="navEnabled.about" block @click="goAndClose('/about')">关于我们</n-button>
          <n-button v-if="navEnabled.contact" block @click="goAndClose('/contact')">联系我们</n-button>
          <n-divider />
          <n-button block type="primary" ghost @click="openMiniProgram()">进入小程序</n-button>
        </n-space>
      </n-drawer-content>
    </n-drawer>

    <n-modal v-model:show="miniProgramQrOpen" preset="card" title="微信扫码进入小程序" style="width: min(420px, 92vw)">
      <div style="display: flex; flex-direction: column; align-items: center; gap: 12px">
        <n-image v-if="miniProgramUrl" :src="miniProgramUrl" width="260" />
        <n-empty v-else description="小程序入口未配置" />
        <div class="muted" style="text-align: center; line-height: 1.6">
          请使用微信“扫一扫”扫描二维码进入小程序。
        </div>
      </div>
    </n-modal>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import {
  useMessage,
  NButton,
  NAlert,
  NDivider,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NGrid,
  NGridItem,
  NImage,
  NLayout,
  NLayoutContent,
  NLayoutFooter,
  NLayoutHeader,
  NModal,
  NSpace,
} from 'naive-ui'

import { useSeo } from '../lib/seo'
import { apiGet } from '../lib/api'
import { getWebsiteExternalLinks } from '../lib/websiteExternalLinks'
import { getWebsiteNavControl } from '../lib/websiteNavControl'
import { getWebsiteMaintenanceMode } from '../lib/websiteMaintenanceMode'
import MaintenancePage from '../components/MaintenancePage.vue'
import NotOpenPage from '../components/NotOpenPage.vue'

// 阶段13：SEO（title/description/canonical）
useSeo()

const router = useRouter()
const route = useRoute()
const message = useMessage()

const drawerOpen = ref(false)

type FooterConfig = {
  companyName?: string
  cooperationEmail?: string
  cooperationPhone?: string
  icpBeianNo?: string
  icpBeianLink?: string
  publicAccountQrUrl?: string
  miniProgramQrUrl?: string
}

const footerConfig = ref<FooterConfig | null>(null)
const footerConfigError = ref<string>('')

async function loadFooterConfig() {
  footerConfigError.value = ''
  try {
    footerConfig.value = await apiGet<FooterConfig>('/v1/website/footer/config')
  } catch (e) {
    footerConfig.value = null
    footerConfigError.value = e instanceof Error ? e.message : '页脚信息加载失败'
  }
}

const miniProgramUrl = ref<string>('')
const miniProgramQrOpen = ref(false)

async function loadExternalLinks() {
  try {
    const data = await getWebsiteExternalLinks()
    miniProgramUrl.value = String(data.miniProgramUrl || '').trim()
  } catch {
    miniProgramUrl.value = ''
  }
}

function openMiniProgram() {
  const u = String(miniProgramUrl.value || '').trim()
  if (!u) {
    message.warning('小程序入口未配置')
    return
  }
  miniProgramQrOpen.value = true
}

function go(path: string) {
  router.push(path)
}

function goAndClose(path: string) {
  drawerOpen.value = false
  router.push(path)
}

function isActive(prefix: string) {
  const p = route.path
  if (prefix === '/') return p === '/'
  return p === prefix || p.startsWith(prefix + '/')
}

const navEnabled = reactive({
  home: true,
  business: true,
  venues: true,
  content: true,
  about: true,
  contact: true,
})

async function loadNavControl() {
  try {
    const data = await getWebsiteNavControl()
    navEnabled.home = !!data.navItems.home.enabled
    navEnabled.business = !!data.navItems.business.enabled
    navEnabled.venues = !!data.navItems.venues.enabled
    navEnabled.content = !!data.navItems.content.enabled
    navEnabled.about = !!data.navItems.about.enabled
    navEnabled.contact = !!data.navItems.contact.enabled
  } catch {
    // ignore：默认全开
  }
}

const maintenance = reactive({
  enabled: false,
  messageTitle: '维护中',
  messageBody: '我们正在进行系统维护，请稍后再试。',
  allowPaths: [] as string[],
})

async function loadMaintenanceMode() {
  try {
    const data = await getWebsiteMaintenanceMode()
    maintenance.enabled = !!data.enabled
    maintenance.messageTitle = String(data.messageTitle || '维护中')
    maintenance.messageBody = String(data.messageBody || '我们正在进行系统维护，请稍后再试。')
    maintenance.allowPaths = Array.isArray(data.allowPaths) ? data.allowPaths.map((x) => String(x)) : []
  } catch {
    maintenance.enabled = false
    maintenance.allowPaths = []
  }
}

const maintenanceAllowPath = computed(() => {
  const p = String(route.path || '/')
  return maintenance.allowPaths.includes(p)
})

function isRouteBlockedByNav(path: string): boolean {
  const p = String(path || '/')
  if (p === '/' || p === '') return !navEnabled.home
  if (p === '/business' || p.startsWith('/business/')) return !navEnabled.business
  if (p === '/venues' || p.startsWith('/venues/')) return !navEnabled.venues
  if (p === '/content' || p.startsWith('/content/')) return !navEnabled.content
  if (p === '/about' || p.startsWith('/about/')) return !navEnabled.about
  if (p === '/contact' || p.startsWith('/contact/')) return !navEnabled.contact
  return false
}

const blockedByNav = computed(() => isRouteBlockedByNav(route.path))

onMounted(() => {
  loadFooterConfig()
  loadExternalLinks()
  loadNavControl()
  loadMaintenanceMode()
})
</script>

<style scoped>
.site-root {
  min-height: 100vh;
}

/* 避免窄屏时内容溢出被裁切：允许横向滚动（同时各页面尽量通过 min-width:0 + wrap 避免溢出） */
.site-root :deep(.n-layout-scroll-container) {
  overflow-x: auto;
}

.site-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
}

.header-inner {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: nowrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, #14b8a6, #2dd4bf);
}

.brand-name {
  font-weight: 700;
  white-space: nowrap;
}

.nav-mobile {
  display: none;
}

.mobile-menu-btn {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 12px;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.65);
}

.mobile-menu-icon {
  font-size: 18px;
  line-height: 1;
  margin-right: 6px;
}

.site-content {
  background: #ffffff;
}

.site-footer {
  background: #ffffff;
}

.footer-inner {
  padding: 24px 16px;
}

.footer-title {
  font-weight: 700;
}

.footer-col-title {
  font-weight: 700;
  margin-bottom: 8px;
}

.footer-bottom {
  margin-top: 18px;
  display: flex;
  justify-content: space-between;
}

.qr-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qr-label {
  font-size: 12px;
}

/* 窄屏策略：提前切换到移动端菜单，避免桌面导航/按钮导致 header 换行 */
@media (max-width: 1100px) {
  .nav-desktop,
  .actions-desktop {
    display: none;
  }
  .nav-mobile {
    display: block;
  }
  .mobile-menu-text {
    display: none;
  }
  .brand-name {
    display: none;
  }
}
</style>


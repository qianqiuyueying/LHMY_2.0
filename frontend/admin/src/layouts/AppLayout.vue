<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown,
  Bell,
  Document,
  Edit,
  Expand,
  Finished,
  Fold,
  HomeFilled,
  Link,
  List,
  Money,
  Moon,
  Notebook,
  Operation,
  Setting,
  Sunny,
  SwitchButton,
  Tickets,
  User,
} from '@element-plus/icons-vue'

import { apiRequest } from '../lib/api'
import { clearSession, getSession, isAdmin, isDealer, isProvider } from '../lib/auth'
import { getAdminNavGroups, getDealerNavGroups, getProviderNavGroups, type NavGroup } from '../lib/nav'
import { applyTheme, getStoredTheme, type ThemeMode } from '../lib/theme'
import { lsGet, lsSet } from '@shared/storage/localStorage'

const route = useRoute()
const router = useRouter()

const session = computed(() => getSession())
const actorType = computed(() => session.value?.actorType)
const actorUsername = computed(() => session.value?.actorUsername || session.value?.actorType || '-')

const activePath = computed(() => String(route.path || ''))

const sidebarCollapsed = ref<boolean>(lsGet('lh-admin.sidebarCollapsed') === '1')
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  lsSet('lh-admin.sidebarCollapsed', sidebarCollapsed.value ? '1' : '0')
}

const themeMode = ref<ThemeMode>(getStoredTheme())
applyTheme(themeMode.value)
function toggleTheme() {
  themeMode.value = themeMode.value === 'dark' ? 'light' : 'dark'
  applyTheme(themeMode.value)
}

const iconBag = {
  Bell,
  Document,
  Edit,
  Finished,
  HomeFilled,
  Link,
  List,
  Money,
  Notebook,
  Operation,
  Setting,
  Tickets,
  User,
} as const

const navTitle = computed(() => {
  if (isProvider(actorType.value)) return '服务提供方后台'
  if (isDealer(actorType.value)) return '经销商后台'
  return '运营后台'
})

type ProviderOnboarding = { infraAgreementAcceptedAt?: string | null; agreementAcceptedAt?: string | null }
const providerOnboarding = ref<ProviderOnboarding | null>(null)
const providerOnboardingLoading = ref(false)
const providerInfraAccepted = computed(() => !!providerOnboarding.value?.infraAgreementAcceptedAt)
const providerHealthAccepted = computed(() => !!providerOnboarding.value?.agreementAcceptedAt)

async function loadProviderOnboardingForNav() {
  if (!isProvider(actorType.value)) return
  providerOnboardingLoading.value = true
  try {
    providerOnboarding.value = await apiRequest<ProviderOnboarding>('/provider/onboarding')
  } catch {
    // 兜底：拿不到就按“未同意”处理（收口菜单，避免误导/误点）
    providerOnboarding.value = null
  } finally {
    providerOnboardingLoading.value = false
  }
}

const navGroups = computed<NavGroup[]>(() => {
  if (isProvider(actorType.value))
    return getProviderNavGroups(iconBag, { infraAccepted: providerInfraAccepted.value, healthAccepted: providerHealthAccepted.value })
  if (isDealer(actorType.value)) return getDealerNavGroups(iconBag)
  return getAdminNavGroups(iconBag)
})

onMounted(() => {
  void loadProviderOnboardingForNav()

  // Provider：工作台签署协议/提交申请后，需要立刻刷新侧边栏与门禁展示（无需整页刷新）
  const handler = () => void loadProviderOnboardingForNav()
  window.addEventListener('lh-provider-onboarding-updated', handler as any)
  onUnmounted(() => {
    window.removeEventListener('lh-provider-onboarding-updated', handler as any)
  })
})

type NotificationItem = {
  id: string
  title: string
  content: string
  category?: 'SYSTEM' | 'ACTIVITY' | 'OPS' | string
  status: 'UNREAD' | 'READ'
  createdAt: string
  readAt?: string | null
}

const notificationsOpen = ref(false)
const notificationsLoading = ref(false)
const notifications = ref<NotificationItem[]>([])
const notificationsTab = ref<'UNREAD' | 'READ'>('UNREAD')
const canUseNotifications = computed(() => isAdmin(actorType.value) || isDealer(actorType.value) || isProvider(actorType.value))
const notificationsBasePath = computed<string | null>(() => {
  if (isAdmin(actorType.value)) return '/admin/notifications'
  if (isDealer(actorType.value)) return '/dealer/notifications'
  if (isProvider(actorType.value)) return '/provider/notifications'
  return null
})
const unreadCount = ref<number>(0)

async function loadNotifications() {
  if (!notificationsBasePath.value) return
  notificationsLoading.value = true
  try {
    const data = await apiRequest<{ items: NotificationItem[]; page: number; pageSize: number; total: number }>(
      notificationsBasePath.value,
      {
        query: { status: notificationsTab.value, page: 1, pageSize: 20 },
      },
    )
    notifications.value = data.items || []
    if (notificationsTab.value === 'UNREAD') unreadCount.value = Number(data.total ?? notifications.value.length ?? 0)
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '通知加载失败')
    notifications.value = []
  } finally {
    notificationsLoading.value = false
  }
}

async function loadUnreadCount() {
  if (!notificationsBasePath.value) {
    unreadCount.value = 0
    return
  }
  try {
    const data = await apiRequest<{ items: NotificationItem[]; page: number; pageSize: number; total: number }>(
      notificationsBasePath.value,
      { query: { status: 'UNREAD', page: 1, pageSize: 1 } },
    )
    unreadCount.value = Number(data.total ?? 0)
  } catch {
    // ignore：不阻断主 UI
  }
}

async function markRead(id: string) {
  if (!notificationsBasePath.value) return
  try {
    await apiRequest(`${notificationsBasePath.value}/${id}/read`, { method: 'POST' })
    // 未读列表：直接移除；已读列表：刷新以回显 readAt
    if (notificationsTab.value === 'UNREAD') notifications.value = notifications.value.filter((x) => x.id !== id)
    else await loadNotifications()
    await loadUnreadCount()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function onClickNotifications() {
  if (!canUseNotifications.value) {
    ElMessage.info('当前身份不可用通知中心')
    return
  }
  notificationsOpen.value = true
  await loadNotifications()
  await loadUnreadCount()
}

async function onChangeNotificationsTab() {
  await loadNotifications()
  await loadUnreadCount()
}

async function seedDemoNotifications() {
  // 仅用于开发/测试：让“通知”功能可见、可操作
  if ((import.meta as any).env?.MODE === 'production') {
    ElMessage.warning('生产环境不提供演示数据初始化')
    return
  }
  if (!isAdmin(actorType.value)) {
    ElMessage.info('演示数据初始化仅对 Admin 开放')
    return
  }
  try {
    await ElMessageBox.confirm('将调用“演示数据初始化（seed）”，用于生成可见的通知示例。确认继续？', '生成示例通知', {
      type: 'warning',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest('/admin/dev/seed', { method: 'POST', body: { reset: false } })
    ElMessage.success('已生成示例通知')
    notificationsTab.value = 'UNREAD'
    await loadNotifications()
    await loadUnreadCount()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '生成失败')
  }
}

async function doLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '退出登录', { type: 'warning' })
  } catch {
    return
  }

  try {
    if (isAdmin(actorType.value)) {
      await apiRequest<{ success: boolean }>('/admin/auth/logout', { method: 'POST' })
    }
  } catch {
    // ignore
  } finally {
    clearSession()
    await router.replace('/login')
    ElMessage.success('已退出')
  }
}

async function goSecurity() {
  await router.push('/account/security')
}
</script>

<template>
  <el-container class="layout">
    <el-aside class="aside" :width="sidebarCollapsed ? '72px' : '220px'">
      <div class="brand" :class="{ 'brand--collapsed': sidebarCollapsed }">
        <div class="brand__row">
          <div class="brand__text">
            <div class="brand__name" v-if="!sidebarCollapsed">{{ navTitle }}</div>
            <div class="brand__sub" v-if="!sidebarCollapsed">陆合铭云 · LHMY 2.0</div>
            <div v-else class="brand__mini">LH</div>
          </div>

          <el-tooltip :content="sidebarCollapsed ? '展开菜单' : '折叠菜单'" placement="right">
            <el-button
              class="brand__collapseBtn"
              :icon="sidebarCollapsed ? Expand : Fold"
              circle
              size="small"
              @click="toggleSidebar"
            />
          </el-tooltip>
        </div>
      </div>
      <el-menu
        router
        :default-active="activePath"
        class="menu"
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
      >
        <template v-for="g in navGroups" :key="g.key">
          <el-sub-menu v-if="g.items.length > 1" :index="`group:${g.key}`">
            <template #title>
              <el-icon v-if="g.items[0]?.icon"><component :is="g.items[0].icon" /></el-icon>
              <span>{{ g.label }}</span>
            </template>
            <el-menu-item v-for="it in g.items" :key="it.path" :index="it.path">
              <el-icon v-if="it.icon"><component :is="it.icon" /></el-icon>
              <span>{{ it.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="g.items[0]?.path">
            <el-icon v-if="g.items[0]?.icon"><component :is="g.items[0].icon" /></el-icon>
            <span>{{ g.items[0]?.label }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header__left">
          <div class="header__logo">LH</div>
          <div class="header__title">
            <div class="header__titleMain">陆合铭云健康服务平台</div>
            <div class="header__titleSub">管理后台 · {{ navTitle }}</div>
          </div>
        </div>

        <div class="header__right">
          <el-tooltip :content="themeMode === 'dark' ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
            <el-button :icon="themeMode === 'dark' ? Sunny : Moon" circle size="small" @click="toggleTheme" />
          </el-tooltip>
          <el-tooltip v-if="!canUseNotifications" content="当前身份不可用通知中心" placement="bottom">
            <el-button :icon="Bell" size="small" disabled>通知</el-button>
          </el-tooltip>
          <el-badge v-else :value="unreadCount" :hidden="unreadCount <= 0" :max="99">
            <el-button :icon="Bell" size="small" @click="onClickNotifications">通知</el-button>
          </el-badge>

          <el-dropdown trigger="click">
            <el-button size="small">
              {{ actorUsername }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>角色：{{ actorType || '-' }}</el-dropdown-item>
                <el-dropdown-item @click="goSecurity">
                  <el-icon><Setting /></el-icon>
                  安全设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="doLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <el-drawer v-model="notificationsOpen" title="通知中心" size="420px">
    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>站内通知（v1）</template>
      <div style="line-height: 1.7">
        <div>这里展示发送给你的 <b>站内通知</b>（系统通知/运营通知）。</div>
        <div v-if="isAdmin(actorType)" style="color: var(--lh-muted); margin-top: 4px">
          Admin 可在菜单「通知管理」中手工发送通知；本抽屉用于查看/标记已读。
        </div>
      </div>
    </el-alert>

    <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap">
      <el-segmented v-model="notificationsTab" :options="['UNREAD', 'READ']" @change="onChangeNotificationsTab" />
      <el-button size="small" :loading="notificationsLoading" @click="loadNotifications">刷新</el-button>
      <el-button v-if="isAdmin(actorType)" size="small" type="primary" plain @click="seedDemoNotifications">生成示例通知</el-button>
    </div>

    <el-skeleton v-if="notificationsLoading" :rows="6" animated />
    <el-empty v-else-if="notifications.length === 0" :description="notificationsTab === 'UNREAD' ? '暂无未读通知' : '暂无已读通知'" />
    <el-timeline v-else>
      <el-timeline-item v-for="n in notifications" :key="n.id" :timestamp="n.createdAt" placement="top">
        <div style="display: flex; justify-content: space-between; align-items: start; gap: 12px">
          <div style="flex: 1">
            <div style="font-weight: 700; display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
              <span>{{ n.title }}</span>
              <el-tag v-if="n.category" size="small" type="info">{{ n.category }}</el-tag>
            </div>
            <div style="margin-top: 6px; color: var(--lh-muted)">{{ n.content }}</div>
            <div v-if="notificationsTab === 'READ' && n.readAt" style="margin-top: 6px; font-size: 12px; color: var(--lh-muted-2)">
              已读时间：{{ n.readAt }}
            </div>
          </div>
          <el-button v-if="notificationsTab === 'UNREAD'" size="small" @click="markRead(n.id)">标记已读</el-button>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-drawer>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.aside {
  border-right: 1px solid var(--lh-border);
  background: var(--lh-surface-glass);
  backdrop-filter: blur(10px);
}

.brand {
  padding: 14px 12px;
  border-bottom: 1px solid var(--lh-border);
}

.brand__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.brand--collapsed .brand__row {
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

.brand--collapsed .brand__text {
  display: flex;
  justify-content: center;
  width: 100%;
}

.brand--collapsed .brand__collapseBtn {
  margin-left: 0;
}

.brand__text {
  min-width: 0;
}

.brand__collapseBtn {
  flex: none;
}

.brand__name {
  font-weight: 700;
  font-size: 14px;
}

.brand__sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--lh-muted);
}

.brand__mini {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.95), rgba(13, 148, 136, 0.9));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 12px;
  box-shadow: var(--lh-shadow-1);
}

.menu {
  border-right: none;
}

.menu :deep(.el-menu--collapse .el-sub-menu__title),
.menu :deep(.el-menu--collapse .el-menu-item) {
  justify-content: center;
}

.menu :deep(.el-menu--collapse .el-sub-menu__title .el-sub-menu__icon-arrow) {
  display: none;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--lh-border);
  background: var(--lh-surface-glass);
  backdrop-filter: blur(10px);
}

.header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header__logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.95), rgba(13, 148, 136, 0.9));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  box-shadow: var(--lh-shadow-1);
}

.header__title {
  font-weight: 600;
}

.header__titleMain {
  font-weight: 700;
  line-height: 1.05;
}

.header__titleSub {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 500;
  color: var(--lh-muted);
}

.header__dealer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header__dealerLabel {
  font-size: 12px;
  color: var(--lh-muted);
}

.header__right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.main {
  background: transparent;
  padding: 18px;
}
</style>

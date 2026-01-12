import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getSession, isAdmin, isDealer, isProvider } from '../lib/auth'
import { applyStoredTheme, forceLightTheme } from '../lib/theme'
import { apiRequest } from '../lib/api'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/admin' },
  {
    path: '/login',
    name: 'login',
    component: () => import('../pages/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/admin-2fa',
    name: 'admin-2fa',
    component: () => import('../pages/Admin2faPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../layouts/AppLayout.vue'),
    children: [
      // Account (any authenticated actor)
      {
        path: '/account/security',
        name: 'account-security',
        component: () => import('../pages/AccountSecurityPage.vue'),
      },
      // Admin
      {
        path: '/admin',
        redirect: '/admin/dashboard',
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/legal/agreements',
        name: 'admin-legal-agreements',
        component: () => import('../pages/admin/AdminLegalAgreementsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/dashboard',
        name: 'admin-dashboard',
        component: () => import('../pages/admin/AdminDashboardPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/enterprise-bindings',
        name: 'admin-enterprise-bindings',
        component: () => import('../pages/admin/AdminEnterpriseBindingsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/enterprises',
        name: 'admin-enterprises',
        component: () => import('../pages/admin/AdminEnterprisesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/users',
        name: 'admin-users',
        component: () => import('../pages/admin/AdminUsersPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/accounts',
        name: 'admin-accounts',
        component: () => import('../pages/admin/AdminAccountsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/tags',
        name: 'admin-tags',
        component: () => import('../pages/admin/AdminTagsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/products',
        name: 'admin-products',
        component: () => import('../pages/admin/AdminProductsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/orders',
        name: 'admin-orders',
        // 避免混用：订单监管按业务线拆分（基建联防/健行天下）
        redirect: '/admin/orders/ecommerce-product',
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/orders/all',
        name: 'admin-orders-all',
        component: () => import('../pages/admin/AdminOrdersPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/orders/ecommerce-product',
        name: 'admin-orders-ecommerce-product',
        component: () => import('../pages/admin/AdminOrdersByTypePage.vue'),
        meta: { role: 'ADMIN', orderType: 'PRODUCT' },
      },
      {
        path: '/admin/orders/service-package',
        name: 'admin-orders-service-package',
        component: () => import('../pages/admin/AdminOrdersByTypePage.vue'),
        meta: { role: 'ADMIN', orderType: 'SERVICE_PACKAGE' },
      },
      {
        path: '/admin/after-sales',
        name: 'admin-after-sales',
        component: () => import('../pages/admin/AdminAfterSalesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/entitlements',
        name: 'admin-entitlements',
        component: () => import('../pages/admin/AdminEntitlementsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/service-packages',
        name: 'admin-service-packages',
        component: () => import('../pages/admin/AdminServicePackagesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/service-categories',
        name: 'admin-service-categories',
        component: () => import('../pages/admin/AdminServiceCategoriesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/sellable-cards',
        name: 'admin-sellable-cards',
        component: () => import('../pages/admin/AdminSellableCardsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/provider-onboarding/health-card',
        name: 'admin-provider-health-card-onboarding',
        component: () => import('../pages/admin/AdminProviderHealthCardOnboardingPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/venues',
        name: 'admin-venues',
        component: () => import('../pages/admin/AdminVenuesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/dealer-settlements',
        name: 'admin-dealer-settlements',
        component: () => import('../pages/admin/AdminDealerSettlementsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/service-package-pricing',
        name: 'admin-service-package-pricing',
        component: () => import('../pages/admin/AdminServicePackagePricingPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/bookings',
        name: 'admin-bookings',
        component: () => import('../pages/admin/AdminBookingsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/cms',
        redirect: '/admin/cms/content-center',
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/cms/content-center',
        name: 'admin-cms-content-center',
        component: () => import('../pages/admin/AdminCmsContentCenterPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/cms/website',
        name: 'admin-cms-website-delivery',
        component: () => import('../pages/admin/AdminCmsWebsiteDeliveryPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/cms/mini-program',
        name: 'admin-cms-mini-program-delivery',
        component: () => import('../pages/admin/AdminCmsMiniProgramDeliveryPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/mini-program',
        name: 'admin-mini-program',
        component: () => import('../pages/admin/AdminMiniProgramConfigPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/ai/providers',
        name: 'admin-ai-providers',
        component: () => import('../pages/admin/AdminAiProvidersPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/ai/strategies',
        name: 'admin-ai-strategies',
        component: () => import('../pages/admin/AdminAiStrategiesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/ai/bindings',
        name: 'admin-ai-bindings',
        component: () => import('../pages/admin/AdminAiBindingsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/regions/cities',
        name: 'admin-regions-cities',
        component: () => import('../pages/admin/AdminRegionCitiesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/external-links',
        name: 'admin-website-external-links',
        component: () => import('../pages/admin/AdminWebsiteExternalLinksPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/footer-config',
        name: 'admin-website-footer-config',
        component: () => import('../pages/admin/AdminWebsiteFooterConfigPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/home/recommended-venues',
        name: 'admin-website-home-recommended-venues',
        component: () => import('../pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/site-seo',
        name: 'admin-website-site-seo',
        component: () => import('../pages/admin/AdminWebsiteSiteSeoPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/nav-control',
        name: 'admin-website-nav-control',
        component: () => import('../pages/admin/AdminWebsiteNavControlPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/website/maintenance-mode',
        name: 'admin-website-maintenance-mode',
        component: () => import('../pages/admin/AdminWebsiteMaintenanceModePage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/audit-logs',
        name: 'admin-audit-logs',
        component: () => import('../pages/admin/AdminAuditLogsPage.vue'),
        meta: { role: 'ADMIN' },
      },
      {
        path: '/admin/notifications/send',
        name: 'admin-notifications-send',
        component: () => import('../pages/admin/AdminNotificationsSendPage.vue'),
        meta: { role: 'ADMIN' },
      },

      // Dealer
      {
        path: '/dealer',
        redirect: '/dealer/dashboard',
        meta: { role: 'DEALER' },
      },
      {
        path: '/dealer/dashboard',
        name: 'dealer-dashboard',
        component: () => import('../pages/dealer/DealerDashboardPage.vue'),
        meta: { role: 'DEALER' },
      },
      {
        path: '/dealer/links',
        name: 'dealer-links',
        component: () => import('../pages/dealer/DealerLinksPage.vue'),
        meta: { role: 'DEALER' },
      },
      {
        path: '/dealer/orders',
        name: 'dealer-orders',
        component: () => import('../pages/dealer/DealerOrdersPage.vue'),
        meta: { role: 'DEALER' },
      },
      {
        path: '/dealer/settlements',
        name: 'dealer-settlements',
        component: () => import('../pages/dealer/DealerSettlementsPage.vue'),
        meta: { role: 'DEALER' },
      },
      {
        path: '/dealer/notifications',
        name: 'dealer-notifications',
        component: () => import('../pages/dealer/DealerNotificationsPage.vue'),
        meta: { role: 'DEALER' },
      },

      // Provider
      {
        path: '/provider',
        redirect: '/provider/workbench',
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/workbench',
        name: 'provider-workbench',
        component: () => import('../pages/provider/ProviderWorkbenchPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/venues',
        name: 'provider-venues',
        component: () => import('../pages/provider/ProviderVenuesPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/notifications',
        name: 'provider-notifications',
        component: () => import('../pages/provider/ProviderNotificationsPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/services',
        name: 'provider-services',
        component: () => import('../pages/provider/ProviderServicesPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/products',
        name: 'provider-products',
        component: () => import('../pages/provider/ProviderProductsPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/schedules',
        name: 'provider-schedules',
        component: () => import('../pages/provider/ProviderSchedulesPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/bookings',
        name: 'provider-bookings',
        component: () => import('../pages/provider/ProviderBookingsPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/redeem',
        name: 'provider-redeem',
        component: () => import('../pages/provider/ProviderRedeemPage.vue'),
        meta: { role: 'PROVIDER' },
      },
      {
        path: '/provider/redemptions',
        name: 'provider-redemptions',
        component: () => import('../pages/provider/ProviderRedemptionsPage.vue'),
        meta: { role: 'PROVIDER' },
      },
    ],
  },
  { path: '/403', name: 'forbidden', component: () => import('../pages/ForbiddenPage.vue') },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../pages/NotFoundPage.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

type ProviderOnboarding = {
  infraAgreementAcceptedAt?: string | null
  agreementAcceptedAt?: string | null
}

let _providerOnboardingCache: { at: number; data: ProviderOnboarding | null } | null = null
async function _getProviderOnboardingCached(): Promise<ProviderOnboarding | null> {
  const now = Date.now()
  if (_providerOnboardingCache && now - _providerOnboardingCache.at < 10_000) return _providerOnboardingCache.data
  try {
    const data = await apiRequest<ProviderOnboarding>('/provider/onboarding')
    _providerOnboardingCache = { at: now, data }
    return data
  } catch {
    // 门禁读不到状态时：兜底为 null（由调用方决定 fail-closed 策略）
    _providerOnboardingCache = { at: now, data: null }
    return null
  }
}

router.beforeEach(async (to) => {
  // 主题策略：
  // - 登录/2FA 等公共页：固定浅色（不受全局 theme 影响）
  // - 业务页：按用户上次选择应用主题
  if (to.meta.public) forceLightTheme()
  else applyStoredTheme()

  if (to.meta.public) return true

  const session = getSession()
  if (!session) {
    return { path: '/login', query: { next: to.fullPath, reason: 'UNAUTHENTICATED' } }
  }

  // Provider 协议门禁（REQ-PROVIDER-P1-001，方案A）
  if (isProvider(session.actorType)) {
    const allowedBeforeInfra = new Set<string>(['/provider', '/provider/workbench', '/provider/venues'])
    const onboarding = await _getProviderOnboardingCached()
    const infraAccepted = !!(onboarding && onboarding.infraAgreementAcceptedAt)
    const healthAccepted = !!(onboarding && onboarding.agreementAcceptedAt)

    if (!infraAccepted) {
      // 仅允许：工作台（签协议）/场所信息/退出登录
      if (!allowedBeforeInfra.has(to.path)) {
        return { path: '/provider/workbench', query: { gate: 'INFRA', next: to.fullPath } }
      }
    } else {
      // infra 已同意：仅健行天下服务页受 health 协议门禁
      if (!healthAccepted && to.path === '/provider/services') {
        return { path: '/provider/workbench', query: { gate: 'HEALTH', next: to.fullPath } }
      }
    }
  }

  const requiredRole = to.meta.role as string | undefined
  if (!requiredRole) return true

  if (requiredRole === 'ADMIN' && !isAdmin(session.actorType)) {
    return { path: '/403' }
  }
  if (requiredRole === 'DEALER' && !isDealer(session.actorType)) {
    return { path: '/403' }
  }
  if (requiredRole === 'PROVIDER' && !isProvider(session.actorType)) {
    return { path: '/403' }
  }

  return true
})

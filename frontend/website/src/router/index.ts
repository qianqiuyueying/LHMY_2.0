import { createRouter, createWebHistory } from 'vue-router'

import SiteLayout from '../layouts/SiteLayout.vue'
import HomePage from '../pages/HomePage.vue'
import BusinessPage from '../pages/BusinessPage.vue'
import VenuesPage from '../pages/VenuesPage.vue'
import VenueDetailPage from '../pages/VenueDetailPage.vue'
import ContentCenterPage from '../pages/ContentCenterPage.vue'
import ContentDetailPage from '../pages/ContentDetailPage.vue'
import AboutPage from '../pages/AboutPage.vue'
import ContactPage from '../pages/ContactPage.vue'
import NotFoundPage from '../pages/NotFoundPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: SiteLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: HomePage,
          meta: {
            title: '陆合铭云健康服务平台',
            description: '统一入口 · 多业务线协同 · 可信赖服务',
          },
        },
        {
          path: 'business',
          name: 'business',
          component: BusinessPage,
          meta: {
            title: '业务线 - 陆合铭云健康服务平台',
            description: '基建联防、健行天下、职健行动三大业务线介绍与入口。',
          },
        },
        {
          path: 'venues',
          name: 'venues',
          component: VenuesPage,
          meta: {
            title: '场所/服务 - 陆合铭云健康服务平台',
            description: '对外展示可服务的健康场所与服务类别。',
          },
        },
        {
          path: 'venues/:id',
          name: 'venueDetail',
          component: VenueDetailPage,
          meta: {
            title: '场所详情 - 陆合铭云健康服务平台',
            description: '场所信息与可提供服务展示。',
          },
        },
        {
          path: 'content',
          name: 'content',
          component: ContentCenterPage,
          meta: {
            title: '内容中心 - 陆合铭云健康服务平台',
            description: '公告、资讯、科普、案例等内容。',
          },
        },
        {
          path: 'content/:id',
          name: 'contentDetail',
          component: ContentDetailPage,
          meta: {
            title: '内容详情 - 陆合铭云健康服务平台',
            description: '内容详情阅读。',
          },
        },
        {
          path: 'about',
          name: 'about',
          component: AboutPage,
          meta: {
            title: '关于我们 - 陆合铭云健康服务平台',
            description: '平台定位与品牌介绍。',
          },
        },
        {
          path: 'contact',
          name: 'contact',
          component: ContactPage,
          meta: {
            title: '联系我们 - 陆合铭云健康服务平台',
            description: '合作咨询与联系方式。',
          },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'notFound', component: NotFoundPage },
  ],
})


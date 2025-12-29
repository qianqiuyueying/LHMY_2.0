import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Vant from 'vant'
import 'vant/lib/index.css'
import 'amfe-flexible'
import './style.css'
import App from './App.vue'

import LandingPage from './pages/LandingPage.vue'
import BuyPage from './pages/BuyPage.vue'
import PayResultPage from './pages/PayResultPage.vue'
import NotFoundPage from './pages/NotFoundPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/h5' },
    { path: '/h5', component: LandingPage },
    { path: '/h5/buy', component: BuyPage },
    { path: '/h5/pay/result', component: PayResultPage },
    { path: '/:pathMatch(.*)*', component: NotFoundPage },
  ],
})

createApp(App).use(router).use(Vant).mount('#app')

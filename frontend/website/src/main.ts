import { createApp } from 'vue'
import { createHead } from '@vueuse/head'

import './style.css'
import App from './App.vue'
import { router } from './router'

const app = createApp(App)

// SEO：基础 meta 管理（路由切换时更新 title/description）
app.use(createHead())

// 路由
app.use(router)

app.mount('#app')

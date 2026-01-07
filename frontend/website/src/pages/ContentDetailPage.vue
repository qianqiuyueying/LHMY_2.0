<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <n-breadcrumb>
          <n-breadcrumb-item @click="go('/')">首页</n-breadcrumb-item>
          <n-breadcrumb-item @click="go('/content')">内容中心</n-breadcrumb-item>
          <n-breadcrumb-item>详情</n-breadcrumb-item>
        </n-breadcrumb>

        <n-alert v-if="errorText" type="error" show-icon :title="errorText">
          <n-space style="margin-top: 8px">
            <n-button size="small" @click="load()">重试</n-button>
          </n-space>
        </n-alert>
        <n-skeleton v-if="loading" :height="240" />
        <n-empty v-else-if="!detail" description="内容不存在或已下线">
          <template #icon>
            <empty-geo-icon />
          </template>
        </n-empty>

        <n-card v-else size="large">
          <div class="detail-header">
            <div class="title">{{ detail.title }}</div>
            <div class="meta muted">
              <span>{{ detail.publishedAt ? formatLocalDateTime(detail.publishedAt) : '' }}</span>
            </div>
          </div>
          <div v-if="detail.coverImageUrl" class="detail-cover">
            <img class="detail-cover-img" :src="detail.coverImageUrl" alt="cover" />
          </div>
          <n-divider />
          <!-- 注意：contentHtml 来自后台 CMS 富文本；阶段13先按“信任 CMS 输出”渲染 -->
          <div class="content article" v-html="detail.contentHtml" />
        </n-card>

        <div>
          <n-button type="primary" ghost @click="go('/content')">返回内容中心</n-button>
        </div>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHead } from '@vueuse/head'
import { NAlert, NBreadcrumb, NBreadcrumbItem, NButton, NCard, NDivider, NEmpty, NSkeleton, NSpace } from 'naive-ui'

import { apiGet } from '../lib/api'
import { formatLocalDateTime } from '../lib/time'
import type { CmsContentDetail } from '../types/cms'
import EmptyGeoIcon from '../components/EmptyGeoIcon.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const errorText = ref<string>('')
const detail = ref<CmsContentDetail | null>(null)

function go(path: string) {
  router.push(path)
}

const dynamicTitle = computed(() => {
  if (!detail.value?.title) return '内容详情 - 陆合铭云健康服务平台'
  return `${detail.value.title} - 陆合铭云健康服务平台`
})
const dynamicDesc = computed(() => detail.value?.summary || '内容详情阅读。')

useHead({
  title: dynamicTitle,
  meta: [{ name: 'description', content: dynamicDesc }],
})

async function load() {
  const id = String(route.params.id || '').trim()
  if (!id) return
  errorText.value = ''
  loading.value = true
  try {
    detail.value = await apiGet<CmsContentDetail>(`/v1/website/cms/contents/${encodeURIComponent(id)}`)
  } catch (e) {
    detail.value = null
    errorText.value = e instanceof Error ? e.message : '内容详情加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.detail-cover {
  margin-top: 12px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(15, 23, 42, 0.04);
  display: flex;
  justify-content: center;
}
.detail-cover-img {
  /* 兼容不同尺寸封面：尽量完整展示，同时限制最大高度避免撑爆页面 */
  max-width: 100%;
  max-height: 60vh;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}
.detail-header {
  padding-top: 6px;
}
.title {
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.02em;
}

.meta {
  margin-top: 8px;
  font-size: 14px;
}

.article {
  font-size: 15px;
  line-height: 1.78;
  color: rgba(15, 23, 42, 0.92);
}
.article :deep(p) {
  margin: 0 0 12px;
}
.article :deep(h1),
.article :deep(h2),
.article :deep(h3) {
  margin: 18px 0 10px;
  font-weight: 900;
  letter-spacing: -0.01em;
}
.article :deep(h2) {
  font-size: 18px;
}
.article :deep(h3) {
  font-size: 16px;
}
.article :deep(ul),
.article :deep(ol) {
  margin: 0 0 12px;
  padding-left: 20px;
}
.article :deep(li) {
  margin: 6px 0;
}
.article :deep(blockquote) {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-left: 3px solid rgba(20, 184, 166, 0.6);
  background: rgba(20, 184, 166, 0.08);
  border-radius: 12px;
}
.article :deep(a) {
  color: rgba(15, 118, 110, 0.95);
  text-decoration: underline;
  text-decoration-color: rgba(20, 184, 166, 0.5);
  text-underline-offset: 2px;
}
.article :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.92em;
  padding: 0 6px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.06);
}
.article :deep(pre) {
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.06);
  overflow: auto;
}
.article :deep(pre code) {
  background: transparent;
  padding: 0;
}

.content :deep(img) {
  max-width: 100%;
}
</style>


<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <n-breadcrumb>
          <n-breadcrumb-item @click="go('/')">首页</n-breadcrumb-item>
          <n-breadcrumb-item @click="go('/venues')">场所/服务</n-breadcrumb-item>
          <n-breadcrumb-item>详情</n-breadcrumb-item>
        </n-breadcrumb>

        <n-alert v-if="errorText" type="error" show-icon :title="errorText">
          <n-space style="margin-top: 8px">
            <n-button size="small" @click="load()">重试</n-button>
          </n-space>
        </n-alert>
        <n-skeleton v-if="loading" :height="240" />
        <n-empty v-else-if="!venue" description="场所不存在或暂不可访问">
          <template #icon>
            <empty-geo-icon />
          </template>
        </n-empty>

        <template v-else>
          <n-card size="large">
            <template #cover>
              <div class="cover" :style="{ backgroundImage: cover(venue.coverImageUrl) }" />
            </template>
            <div class="detail-header">
              <div class="title">{{ venue.name }}</div>
              <div class="lead muted">{{ venue.description || '—' }}</div>
            </div>

            <div class="tags" v-if="(venue.tags || []).length > 0">
              <n-tag v-for="t in venue.tags" :key="t" size="small" type="success">{{ t }}</n-tag>
            </div>

            <n-divider />

            <n-descriptions label-placement="left" :column="1" bordered>
              <n-descriptions-item label="地址">{{ venue.address || '—' }}</n-descriptions-item>
              <n-descriptions-item label="营业时间">{{ venue.businessHours || '—' }}</n-descriptions-item>
              <n-descriptions-item label="联系电话">
                <span style="margin-left: 8px">{{ venue.contactPhone || '—' }}</span>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <n-card v-if="(venue.services || []).length > 0" size="large" title="可提供服务" :segmented="{ content: true }">
            <n-list bordered>
              <n-list-item v-for="s in venue.services" :key="s.id">
                <n-thing :title="s.title" :description="`履约类型：${s.fulfillmentType}`" />
              </n-list-item>
            </n-list>
          </n-card>

          <div>
            <n-button type="primary" ghost @click="go('/venues')">返回列表</n-button>
          </div>
        </template>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAlert,
  NBreadcrumb,
  NBreadcrumbItem,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  NEmpty,
  NList,
  NListItem,
  NSkeleton,
  NSpace,
  NTag,
  NThing,
} from 'naive-ui'

import { apiGet } from '../lib/api'
import type { VenueDetail } from '../types/venues'
import EmptyGeoIcon from '../components/EmptyGeoIcon.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const errorText = ref<string>('')
const venue = ref<VenueDetail | null>(null)

function go(path: string) {
  router.push(path)
}

function cover(url?: string | null) {
  if (!url) return 'linear-gradient(135deg, rgba(20, 184, 166, 0.22), rgba(15, 118, 110, 0.14))'
  return `url(${url})`
}

async function load() {
  const id = String(route.params.id || '').trim()
  if (!id) return
  errorText.value = ''
  loading.value = true
  try {
    venue.value = await apiGet<VenueDetail>(`/v1/venues/${encodeURIComponent(id)}`)
  } catch (e) {
    venue.value = null
    errorText.value = e instanceof Error ? e.message : '场所详情加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.cover {
  height: 240px;
  background-size: cover;
  background-position: center;
  border-radius: 12px 12px 0 0;
}

.detail-header {
  padding-top: 10px;
}
.title {
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.02em;
}

.lead {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.7;
}

.tags {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>


<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <page-header title="内容中心" subtitle="公告 / 资讯 / 科普 / 案例（按 CMS 栏目展示）。" />

        <n-card size="large" :segmented="{ content: true }">
          <n-space vertical :size="12">
            <div class="filter-bar">
              <div class="filter-bar__left">
                <n-tabs
                  v-model:value="activeChannelId"
                  type="line"
                  animated
                  :tabs-padding="8"
                  @update:value="onTabChange"
                >
                  <n-tab name="" tab="全部" />
                  <n-tab v-for="c in orderedChannels" :key="c.id" :name="c.id" :tab="c.name" />
                </n-tabs>
              </div>

              <div class="filter-bar__right">
                <n-space :size="10" align="center" wrap>
                  <div class="search-box">
                    <n-input v-model:value="keyword" placeholder="搜索标题/摘要" clearable @keyup.enter="search(1)" />
                  </div>
                  <n-button type="primary" :loading="loading" @click="search(1)">搜索</n-button>
                  <n-button @click="reset()">重置</n-button>
                </n-space>
              </div>
            </div>
          </n-space>
        </n-card>

        <result-bar
          v-if="!loading && !errorText"
          :total="total"
          :page="page"
          :page-size="pageSize"
          :filters="activeFilters"
        />

        <n-alert v-if="errorText" type="error" show-icon :title="errorText">
          <n-space style="margin-top: 8px">
            <n-button size="small" @click="search(1)">重试</n-button>
          </n-space>
        </n-alert>
        <n-skeleton v-if="loading" :height="28" :repeat="8" />
        <n-empty v-else-if="items.length === 0" description="暂无内容">
          <template #icon>
            <empty-geo-icon />
          </template>
          <template #extra>
            <n-button size="small" @click="go('/contact')">合作咨询</n-button>
          </template>
        </n-empty>
        <n-list v-else bordered class="content-list">
          <n-list-item v-for="x in items" :key="x.id" class="content-item" @click="go(`/content/${x.id}`)">
            <n-space justify="space-between" align="start" :wrap-item="false" style="width: 100%">
              <n-space align="start" :size="14" :wrap-item="false" style="flex: 1; min-width: 0">
                <div v-if="x.coverImageUrl" class="thumb">
                  <img class="thumb-img" :src="x.coverImageUrl" alt="cover" />
                </div>
                <div class="content-main">
                  <div class="content-title">{{ x.title }}</div>
                  <div class="muted content-summary">{{ x.summary || '' }}</div>
                  <n-space align="center" :size="8" style="margin-top: 10px">
                    <n-tag v-if="channelNameById[x.channelId]" size="small" type="success">
                      {{ channelNameById[x.channelId] }}
                    </n-tag>
                    <span class="muted">{{ x.publishedAt ? formatLocalDateTime(x.publishedAt) : '' }}</span>
                  </n-space>
                </div>
              </n-space>
              <div class="content-arrow muted">→</div>
            </n-space>
          </n-list-item>
        </n-list>

        <pager-bar
          v-if="total > pageSize"
          :total="total"
          :page="page"
          :page-size="pageSize"
          @update:page="search"
        />
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NInput,
  NList,
  NListItem,
  NSkeleton,
  NSpace,
  NTab,
  NTabs,
  NTag,
} from 'naive-ui'

import { apiGet } from '../lib/api'
import { formatLocalDateTime } from '../lib/time'
import type { CmsChannel, CmsContentListItem } from '../types/cms'
import EmptyGeoIcon from '../components/EmptyGeoIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import PagerBar from '../components/PagerBar.vue'
import ResultBar from '../components/ResultBar.vue'

const router = useRouter()

function go(path: string) {
  router.push(path)
}

const channels = ref<CmsChannel[]>([])
const activeChannelId = ref<string>('') // '' 表示全部
const keyword = ref<string>('')

const errorText = ref<string>('')

const orderedChannels = computed(() => {
  const order = ['公告', '资讯', '科普', '案例']
  const byName = new Map(channels.value.map((c) => [c.name, c]))
  const picked: CmsChannel[] = []
  for (const name of order) {
    const c = byName.get(name)
    if (c) picked.push(c)
  }
  const pickedIds = new Set(picked.map((c) => c.id))
  const rest = channels.value.filter((c) => !pickedIds.has(c.id))
  return [...picked, ...rest]
})

const channelNameById = computed<Record<string, string>>(() => {
  const entries = channels.value.map((c) => [c.id, c.name] as const)
  return Object.fromEntries(entries)
})

const loading = ref(false)
const items = ref<CmsContentListItem[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const activeFilters = computed(() => {
  const chips: { key: string; label: string; value: string }[] = []
  if (activeChannelId.value) {
    chips.push({ key: 'channel', label: '栏目', value: channelNameById.value[activeChannelId.value] || activeChannelId.value })
  }
  if (keyword.value.trim()) {
    chips.push({ key: 'keyword', label: '关键词', value: keyword.value.trim() })
  }
  return chips
})

async function loadChannels() {
  errorText.value = ''
  try {
    const data = await apiGet<{ items: CmsChannel[] }>('/v1/website/cms/channels')
    channels.value = data.items || []
  } catch (e) {
    channels.value = []
    errorText.value = e instanceof Error ? e.message : '栏目加载失败'
  }
}

async function search(p = 1) {
  page.value = p
  loading.value = true
  errorText.value = ''
  try {
    const data = await apiGet<{ items: CmsContentListItem[]; page: number; pageSize: number; total: number }>(
      '/v1/website/cms/contents',
      {
        channelId: activeChannelId.value || null,
        keyword: keyword.value,
        page: page.value,
        pageSize: pageSize.value,
      },
    )
    items.value = data.items || []
    total.value = Number(data.total || 0)
  } catch (e) {
    items.value = []
    total.value = 0
    errorText.value = e instanceof Error ? e.message : '内容加载失败'
  } finally {
    loading.value = false
  }
}

function reset() {
  activeChannelId.value = ''
  keyword.value = ''
  search(1)
}

function onTabChange() {
  search(1)
}

onMounted(async () => {
  await loadChannels()
  await search(1)
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-bar__left {
  flex: 1;
  min-width: 0;
}
.filter-bar__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: min(520px, 100%);
  flex: 0 1 auto;
}
.search-box {
  width: min(360px, 62vw);
}
.thumb {
  width: 96px;
  height: 64px;
  flex: 0 0 auto;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(15, 23, 42, 0.04);
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.search-box {
  width: 280px;
}
.filter-actions {
  display: flex;
  justify-content: flex-end;
}

.content-list :deep(.n-list-item) {
  cursor: pointer;
}
.content-item:hover {
  background: rgba(15, 23, 42, 0.02);
}

.content-title {
  font-weight: 900;
  font-size: 16px;
}
.content-summary {
  margin-top: 6px;
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.content-main {
  min-width: 0;
}
.content-arrow {
  flex: 0 0 auto;
  font-size: 16px;
  padding-top: 2px;
}

@media (max-width: 640px) {
  .search-box {
    width: 100%;
  }
  .filter-actions {
    justify-content: flex-start;
  }
}
</style>


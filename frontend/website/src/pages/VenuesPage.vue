<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <page-header title="场所/服务" subtitle="对外展示：已发布的健康场所与可提供服务。" />

        <n-card size="large" :segmented="{ content: true }">
          <n-form label-placement="top" :show-feedback="false">
            <n-grid cols="1 s:2 m:4" :x-gap="12" :y-gap="12" responsive="screen">
              <n-grid-item>
                <n-form-item label="城市">
                  <n-select v-model:value="cityCode" :options="cityOptions" clearable placeholder="选择城市" />
                </n-form-item>
              </n-grid-item>
              <n-grid-item>
                <n-form-item label="区域">
                  <n-select :value="null" disabled placeholder="v1 暂不支持区/县" />
                </n-form-item>
              </n-grid-item>
              <n-grid-item>
                <n-form-item label="服务类别">
                  <n-select v-model:value="taxonomyId" :options="taxonomyOptions" clearable placeholder="选择服务类别" />
                </n-form-item>
              </n-grid-item>
              <n-grid-item>
                <n-form-item label="关键词">
                  <n-input v-model:value="keyword" placeholder="场所名称/地址" />
                </n-form-item>
              </n-grid-item>
            </n-grid>

            <div class="filter-actions">
              <n-space :size="10" wrap>
                <n-button type="primary" :loading="loading" @click="search(1)">搜索</n-button>
                <n-button @click="reset()">重置</n-button>
              </n-space>
            </div>
          </n-form>
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
        <n-skeleton v-if="loading" :height="140" :repeat="3" />
        <n-empty v-else-if="items.length === 0" description="暂无匹配的场所">
          <template #icon>
            <empty-geo-icon />
          </template>
        </n-empty>

        <n-grid v-else :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
          <n-grid-item v-for="v in items" :key="v.id">
            <n-card size="large" hoverable @click="go(`/venues/${v.id}`)">
              <template #cover>
                <div class="cover" :style="{ backgroundImage: cover(v.coverImageUrl) }" />
              </template>
              <div class="card-title">{{ v.name }}</div>
              <div class="muted clamp-2">{{ v.address || '—' }}</div>
              <div class="tags">
                <n-tag v-for="t in (v.tags || []).slice(0, 3)" :key="t" size="small" type="success">{{ t }}</n-tag>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

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
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NSkeleton,
  NSpace,
  NTag,
} from 'naive-ui'

import { apiGet } from '../lib/api'
import type { VenueListItem } from '../types/venues'
import EmptyGeoIcon from '../components/EmptyGeoIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import PagerBar from '../components/PagerBar.vue'
import ResultBar from '../components/ResultBar.vue'

const router = useRouter()

function go(path: string) {
  router.push(path)
}

function cover(url?: string | null) {
  if (!url) return 'linear-gradient(135deg, rgba(20, 184, 166, 0.16), rgba(15, 118, 110, 0.10))'
  return `url(${url})`
}

const keyword = ref<string>('')
const cityCode = ref<string | null>(null)
const taxonomyId = ref<string | null>(null)

type CityItem = { code: string; name: string; sort: number }
type CitiesResp = { items: CityItem[]; defaultCode?: string; version: string }

type TaxonomyNode = { id: string; name: string; type: 'VENUE' | 'PRODUCT' | 'CONTENT' }
type TaxonomyResp = { items: TaxonomyNode[] }

const cityOptions = ref<{ label: string; value: string }[]>([])
const taxonomyOptions = ref<{ label: string; value: string }[]>([])

const loading = ref(false)
const errorText = ref<string>('')
const items = ref<VenueListItem[]>([])
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)

const activeFilters = computed(() => {
  const chips: { key: string; label: string; value: string }[] = []
  if (cityCode.value) {
    const label = cityOptions.value.find((x) => x.value === cityCode.value)?.label || cityCode.value
    chips.push({ key: 'city', label: '城市', value: label })
  }
  if (taxonomyId.value) {
    const label = taxonomyOptions.value.find((x) => x.value === taxonomyId.value)?.label || taxonomyId.value
    chips.push({ key: 'taxonomy', label: '服务类别', value: label })
  }
  if (keyword.value.trim()) {
    chips.push({ key: 'keyword', label: '关键词', value: keyword.value.trim() })
  }
  return chips
})

async function search(p = 1) {
  page.value = p
  loading.value = true
  errorText.value = ''
  try {
    const data = await apiGet<{ items: VenueListItem[]; page: number; pageSize: number; total: number }>('/v1/venues', {
      keyword: keyword.value,
      regionLevel: cityCode.value ? 'CITY' : null,
      regionCode: cityCode.value || null,
      taxonomyId: taxonomyId.value,
      page: page.value,
      pageSize: pageSize.value,
    })
    items.value = data.items || []
    total.value = Number(data.total || 0)
  } catch (e) {
    items.value = []
    total.value = 0
    errorText.value = e instanceof Error ? e.message : '场所列表加载失败'
  } finally {
    loading.value = false
  }
}

function reset() {
  keyword.value = ''
  cityCode.value = null
  taxonomyId.value = null
  search(1)
}

async function loadCities() {
  try {
    const data = await apiGet<CitiesResp>('/v1/regions/cities')
    const opts = (data.items || [])
      .filter((x) => String(x?.code || '').startsWith('CITY:'))
      .slice()
      .sort((a, b) => Number(a.sort || 0) - Number(b.sort || 0))
      .map((x) => ({ label: x.name, value: x.code }))
    cityOptions.value = opts
  } catch {
    cityOptions.value = []
  }
}

async function loadTaxonomy() {
  try {
    const data = await apiGet<TaxonomyResp>('/v1/taxonomy-nodes', { type: 'VENUE' })
    taxonomyOptions.value = (data.items || []).map((x) => ({ label: x.name, value: x.id }))
  } catch {
    taxonomyOptions.value = []
  }
}

onMounted(async () => {
  await Promise.all([loadCities(), loadTaxonomy()])
  search(1)
})
</script>

<style scoped>
.cover {
  width: 100%;
  /* 列表封面：统一容器 + cover，兼容各种尺寸图片 */
  aspect-ratio: 16 / 9;
  height: auto;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  border-radius: 12px 12px 0 0;
}

.card-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tags {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}
</style>


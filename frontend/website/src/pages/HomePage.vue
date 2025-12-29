<template>
  <div>
    <section class="hero">
      <div class="container hero-inner">
        <div class="hero-left">
          <div class="hero-title">陆合铭云健康服务平台</div>
          <div class="hero-subtitle muted">统一入口 · 多业务线协同 · 可信赖服务</div>
          <div class="hero-points">
            <n-grid :cols="3" :x-gap="12" :y-gap="12" responsive="screen">
              <n-grid-item v-for="p in points" :key="p.title">
                <div class="hero-point">
                  <div class="hero-point-icon" />
                  <div>
                    <div class="hero-point-title">{{ p.title }}</div>
                    <div class="muted hero-point-desc">{{ p.desc }}</div>
                  </div>
                </div>
              </n-grid-item>
            </n-grid>
          </div>
          <div class="hero-actions">
            <n-space :size="12">
              <n-button type="primary" @click="go('/business')">了解基建联防</n-button>
              <n-button type="primary" ghost @click="openMiniProgram()">了解职健行动</n-button>
            </n-space>
          </div>
          <div class="hero-links muted">
            官网仅用于品牌与信息展示；交易与使用流程请前往小程序 / H5 完成。
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <n-space vertical :size="16">
          <div class="section-title">三大业务线</div>
          <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
            <n-grid-item v-for="item in businessLines" :key="item.key">
              <n-card size="large" :title="item.title" :segmented="{ content: true }" hoverable>
                <div class="muted">{{ item.desc }}</div>
                <template #footer>
                  <n-space justify="space-between" align="center">
                    <n-button type="primary" ghost @click="item.onClick">{{ item.cta }}</n-button>
                  </n-space>
                </template>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-space>
      </div>
    </section>

    <section class="section section-alt">
      <div class="container">
        <n-space vertical :size="16">
          <div class="section-title">推荐场所</div>
          <div class="muted">来自平台已发布的场所（由管理端配置推荐列表）。</div>

          <n-alert v-if="venuesError" type="error" show-icon :title="venuesError">
            <n-space style="margin-top: 8px">
              <n-button size="small" @click="loadVenues()">重试</n-button>
            </n-space>
          </n-alert>
          <n-skeleton v-if="loadingVenues" :height="140" :repeat="3" />
          <n-empty v-else-if="venues.length === 0" description="暂无推荐场所（请先在管理端配置推荐列表）">
            <template #icon>
              <empty-geo-icon />
            </template>
          </n-empty>
          <n-grid v-else :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
            <n-grid-item v-for="v in venues" :key="v.id">
              <n-card size="large" hoverable @click="go(`/venues/${v.id}`)">
                <template #cover>
                  <div class="cover" :style="{ backgroundImage: cover(v.coverImageUrl) }" />
                </template>
                <div class="card-title">{{ v.name }}</div>
                <div class="muted clamp-2">{{ v.address || '—' }}</div>
              </n-card>
            </n-grid-item>
          </n-grid>

          <div>
            <n-button type="primary" ghost @click="go('/venues')">查看更多场所</n-button>
          </div>
        </n-space>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <n-space vertical :size="16">
          <div class="section-title">内容中心入口</div>
          <div class="muted">资讯/公告/案例/科普（来自 CMS 发布内容）。</div>

          <n-alert v-if="contentsError" type="error" show-icon :title="contentsError">
            <n-space style="margin-top: 8px">
              <n-button size="small" @click="loadContents()">重试</n-button>
            </n-space>
          </n-alert>
          <n-skeleton v-if="loadingContents" :height="28" :repeat="5" />
          <n-empty v-else-if="contents.length === 0" description="暂无内容">
            <template #icon>
              <empty-geo-icon />
            </template>
          </n-empty>
          <n-list v-else bordered>
            <n-list-item v-for="c in contents" :key="c.id">
              <n-thing :title="c.title" :description="c.summary || ''" @click="go(`/content/${c.id}`)" />
            </n-list-item>
          </n-list>

          <div>
            <n-button type="primary" ghost @click="go('/content')">进入内容中心</n-button>
          </div>
        </n-space>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  useMessage,
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NGrid,
  NGridItem,
  NList,
  NListItem,
  NSkeleton,
  NSpace,
  NThing,
} from 'naive-ui'

import { apiGet } from '../lib/api'
import type { VenueListItem } from '../types/venues'
import type { CmsContentListItem } from '../types/cms'
import { getWebsiteExternalLinks } from '../lib/websiteExternalLinks'
import EmptyGeoIcon from '../components/EmptyGeoIcon.vue'

const router = useRouter()
const message = useMessage()

const points = [
  { title: '可信赖', desc: '信息结构清晰，入口明确' },
  { title: '可检索', desc: '场所/服务列表可筛选搜索' },
  { title: '可阅读', desc: '内容中心支持列表与详情' },
]

function go(path: string) {
  router.push(path)
}

function cover(url?: string | null) {
  if (!url) return 'linear-gradient(135deg, #bbf7d0, #86efac)'
  return `url(${url})`
}

function openMiniProgram() {
  getWebsiteExternalLinks()
    .then((x) => {
      const u = String(x.miniProgramUrl || '').trim()
      if (!u) throw new Error('EMPTY')
      window.open(u, '_blank')
    })
    .catch(() => message.warning('小程序入口未配置'))
}

function openH5Buy() {
  getWebsiteExternalLinks()
    .then((x) => {
      const u = String(x.h5BuyUrl || '').trim()
      if (!u) throw new Error('EMPTY')
      window.open(u, '_blank')
    })
    .catch(() => message.warning('H5购买入口未配置'))
}

const businessLines = [
  {
    key: 'jljf',
    title: '基建联防',
    desc: '电商平台核心：商品、订单、履约与服务协同。',
    cta: '查看详情',
    onClick: () => go('/business'),
  },
  {
    key: 'jxtx',
    title: '健行天下',
    desc: '高端服务卡：权益、预约与核销闭环。',
    cta: '去H5购买',
    onClick: () => openH5Buy(),
  },
  {
    key: 'zjxd',
    title: '职健行动',
    desc: '身份升级与折扣：企业绑定与员工价支持。',
    cta: '去小程序绑定',
    onClick: () => openMiniProgram(),
  },
]

const loadingVenues = ref(false)
const venues = ref<VenueListItem[]>([])
const venuesError = ref<string>('')

const loadingContents = ref(false)
const contents = ref<CmsContentListItem[]>([])
const contentsError = ref<string>('')

async function loadVenues() {
  venuesError.value = ''
  loadingVenues.value = true
  try {
    // v1 固化：官网首页推荐位由配置下发（SystemConfig WEBSITE_HOME_RECOMMENDED_VENUES）
    // 读侧接口：GET /api/v1/website/home/recommended-venues
    const data = await apiGet<{ items: VenueListItem[] }>('/v1/website/home/recommended-venues')
    venues.value = data.items || []
  } catch (e) {
    venues.value = []
    venuesError.value = e instanceof Error ? e.message : '推荐场所加载失败'
  } finally {
    loadingVenues.value = false
  }
}

async function loadContents() {
  contentsError.value = ''
  loadingContents.value = true
  try {
    const data = await apiGet<{ items: CmsContentListItem[] }>('/v1/website/cms/contents', { page: 1, pageSize: 5 })
    contents.value = data.items || []
  } catch (e) {
    contents.value = []
    contentsError.value = e instanceof Error ? e.message : '内容列表加载失败'
  } finally {
    loadingContents.value = false
  }
}

onMounted(async () => {
  await loadVenues()
  await loadContents()
})
</script>

<style scoped>
.hero {
  padding: 64px 0;
  background: radial-gradient(1200px 600px at 10% 10%, rgba(20, 184, 166, 0.22), transparent 60%),
    radial-gradient(1000px 500px at 80% 0%, rgba(15, 118, 110, 0.16), transparent 55%),
    linear-gradient(180deg, #ffffff, #f8fafc);
}

.hero-inner {
  display: flex;
  gap: 24px;
}

.hero-title {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  margin-top: 8px;
  font-size: 18px;
}

.hero-actions {
  margin-top: 20px;
}

.hero-points {
  margin-top: 16px;
  max-width: 720px;
}

.hero-point {
  display: flex;
  gap: 10px;
  padding: 12px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.05);
}

.hero-point-icon {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.95), rgba(45, 212, 191, 0.95));
}

.hero-point-title {
  font-weight: 800;
  font-size: 14px;
}

.hero-point-desc {
  font-size: 12px;
}

.hero-links {
  margin-top: 12px;
  font-size: 14px;
}

.section-title {
  font-size: 22px;
  font-weight: 800;
}

.section-alt {
  background: #f8fafc;
}

.cover {
  width: 100%;
  /* 列表/卡片封面：统一容器 + cover，兼容各种尺寸图片 */
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

@media (max-width: 640px) {
  .hero {
    padding: 40px 0;
  }
  .hero-title {
    font-size: 30px;
  }
}
</style>


<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <n-breadcrumb>
          <n-breadcrumb-item @click="go('/')">首页</n-breadcrumb-item>
          <n-breadcrumb-item>业务线</n-breadcrumb-item>
        </n-breadcrumb>

        <page-header title="业务线" subtitle="平台整合三大业务线：基建联防 / 健行天下 / 职健行动。" />

        <n-grid :cols="1" :y-gap="16">
          <n-grid-item>
            <n-card title="基建联防" size="large" :segmented="{ content: true }">
              <n-space vertical :size="8">
                <div class="muted">电商平台核心能力：商品、订单、支付、履约与服务协同。</div>
                <n-space>
                  <n-button type="primary" ghost @click="go('/venues')">查看场所/服务</n-button>
                  <n-button type="primary" ghost @click="openMiniProgram()">进入小程序</n-button>
                </n-space>
              </n-space>
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="健行天下" size="large" :segmented="{ content: true }">
              <n-space vertical :size="8">
                <div class="muted">高端服务卡介绍：购买后在小程序端完成权益查询、预约与核销使用。</div>
                <n-space>
                  <n-button type="warning" @click="openH5Buy()">去H5购买</n-button>
                  <n-button type="primary" ghost @click="openMiniProgram()">进入小程序</n-button>
                </n-space>
              </n-space>
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card title="职健行动" size="large" :segmented="{ content: true }">
              <n-space vertical :size="8">
                <div class="muted">企业绑定/员工价说明：完成企业绑定后可升级身份并享受对应价格权益。</div>
                <n-space>
                  <n-button type="primary" @click="openMiniProgram()">去小程序绑定</n-button>
                  <n-button type="primary" ghost @click="go('/contact')">合作咨询</n-button>
                </n-space>
              </n-space>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useMessage, NBreadcrumb, NBreadcrumbItem, NButton, NCard, NGrid, NGridItem, NSpace } from 'naive-ui'
import { getWebsiteExternalLinks } from '../lib/websiteExternalLinks'
import PageHeader from '../components/PageHeader.vue'

const router = useRouter()
const message = useMessage()

function go(path: string) {
  router.push(path)
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
</script>

<style scoped>
</style>


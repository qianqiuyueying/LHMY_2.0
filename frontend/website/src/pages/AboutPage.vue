<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <page-header
          title="关于我们"
          subtitle="陆合铭云健康服务平台致力于构建“统一入口、多业务线协同”的健康服务体系，为公众与合作伙伴提供可信赖的信息与服务连接。"
        />

        <n-card size="large" title="平台定位" :segmented="{ content: true }">
          <n-space vertical :size="8">
            <div>企业官网：品牌展示与对外信息入口。</div>
            <div>管理后台：内容与业务配置中心。</div>
            <div>小程序端：三业务线统一入口与使用端。</div>
            <div>H5 端：营销与健行天下高端服务卡购买入口。</div>
          </n-space>
        </n-card>

        <n-card size="large" title="我们关注" :segmented="{ content: true }">
          <n-space vertical :size="8">
            <div>信息透明：公开展示内容与服务入口。</div>
            <div>体验一致：多端协同与统一模型。</div>
            <div>合规可信：关键操作审计与风控规则。</div>
          </n-space>
        </n-card>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NCard, NSpace } from 'naive-ui'
import PageHeader from '../components/PageHeader.vue'
</script>

<style scoped>
</style>


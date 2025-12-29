<template>
  <div class="section">
    <div class="container">
      <n-card size="large">
        <n-space vertical :size="12">
          <div class="title">{{ title }}</div>
          <div class="muted">{{ desc }}</div>
          <n-space :size="10" wrap style="margin-top: 4px">
            <n-button type="primary" @click="go('/')">返回首页</n-button>
            <n-button ghost type="primary" @click="go('/contact')">合作咨询</n-button>
          </n-space>
        </n-space>
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NCard, NSpace } from 'naive-ui'

withDefaults(
  defineProps<{
    title?: string
    desc?: string
  }>(),
  {
    title: '页面暂未开放',
    desc: '该入口当前暂未对外开放，请稍后再试或前往“联系我们”。',
  },
)

const router = useRouter()
function go(path: string) {
  router.push(path)
}
</script>

<style scoped>
.title {
  font-size: 22px;
  font-weight: 900;
  letter-spacing: -0.02em;
}
</style>



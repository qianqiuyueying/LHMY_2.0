<template>
  <div class="section">
    <div class="container">
      <n-card size="large">
        <n-space vertical :size="12">
          <div class="title">{{ title }}</div>
          <div class="muted">{{ body }}</div>
          <n-space :size="10" wrap style="margin-top: 4px">
            <n-button type="primary" ghost @click="go('/contact')">合作咨询</n-button>
            <n-button @click="reload()">刷新页面</n-button>
          </n-space>
        </n-space>
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NCard, NSpace } from 'naive-ui'

defineProps<{
  title: string
  body: string
}>()

const router = useRouter()
function go(path: string) {
  router.push(path)
}
function reload() {
  window.location.reload()
}
</script>

<style scoped>
.title {
  font-size: 22px;
  font-weight: 900;
  letter-spacing: -0.02em;
}
</style>



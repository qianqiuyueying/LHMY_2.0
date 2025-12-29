<template>
  <div class="section">
    <div class="container">
      <n-result status="404" title="页面不存在" description="你访问的页面不存在或已迁移。">
        <template #footer>
          <n-space>
            <n-button type="primary" @click="go('/')">返回首页</n-button>
            <n-button @click="go('/content')">去内容中心</n-button>
          </n-space>
        </template>
      </n-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NResult, NSpace } from 'naive-ui'

const router = useRouter()
function go(path: string) {
  router.push(path)
}
</script>


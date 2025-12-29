<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="page">
    <el-result icon="warning" title="无权限访问" sub-title="当前账号角色无权访问该页面。">
      <template #extra>
        <el-button type="primary" @click="router.replace('/login')">返回登录</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>

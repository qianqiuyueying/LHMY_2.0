<template>
  <div class="page">
    <div class="card">
      <div class="title">页面不存在</div>
      <div class="desc">你访问的页面可能已下线或链接有误。</div>
      <van-button type="primary" block @click="$router.replace('/h5')">返回首页</van-button>
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.page {
  padding: 16px;
  min-height: 70vh;
  display: flex;
  align-items: center;
}
.card {
  width: 100%;
  padding: 20px 16px;
  border-radius: var(--lh-radius-card);
  background: var(--lh-card-bg);
  box-shadow: var(--lh-shadow-card);
  border: 1px solid var(--lh-border);
}
.title {
  margin: 0 0 10px;
  font-size: 18px;
  font-weight: 700;
  color: var(--lh-slate-900);
}
.desc {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--lh-slate-700);
}
</style>


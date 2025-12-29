<script setup lang="ts">
type Props = {
  title?: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  title: '暂无数据',
  description: '当前条件下没有匹配的数据。',
})
</script>

<template>
  <div class="box">
    <el-empty :description="description">
      <template #default>
        <div class="title">{{ title }}</div>
      </template>
      <template #bottom>
        <slot name="action" />
      </template>
    </el-empty>
  </div>
</template>

<style scoped>
.box {
  padding: 16px 8px;
}

.title {
  font-weight: 600;
  margin-bottom: 6px;
}
</style>


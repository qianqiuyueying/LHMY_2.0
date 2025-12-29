<template>
  <div class="bar">
    <div class="inner">
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        @update:page="onUpdate"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { NPagination } from 'naive-ui'

withDefaults(
  defineProps<{
    total: number
    page: number
    pageSize: number
  }>(),
  { total: 0, page: 1, pageSize: 10 },
)

const emit = defineEmits<{
  (e: 'update:page', value: number): void
}>()

function onUpdate(p: number) {
  emit('update:page', p)
}
</script>

<style scoped>
.bar {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

.inner {
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.78);
  backdrop-filter: saturate(120%) blur(6px);
}
</style>



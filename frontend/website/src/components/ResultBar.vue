<template>
  <div class="bar" role="status" aria-live="polite">
    <div class="left">
      <div class="count">
        <span class="count-num">{{ totalText }}</span>
        <span class="count-suffix">条</span>
      </div>
      <div v-if="pageInfoText" class="page muted">· {{ pageInfoText }}</div>
    </div>

    <div class="right">
      <n-space v-if="activeFilters.length > 0" :size="6" wrap>
        <n-tag v-for="f in activeFilters" :key="f.key" size="small" type="success">
          {{ f.label }}：{{ f.value }}
        </n-tag>
      </n-space>
      <span v-else class="muted">{{ emptyFilterText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NSpace, NTag } from 'naive-ui'

type FilterChip = {
  key: string
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    total: number
    page?: number
    pageSize?: number
    filters?: FilterChip[]
    emptyFilterText?: string
  }>(),
  {
    page: 1,
    pageSize: 10,
    filters: () => [],
    emptyFilterText: '当前：全部',
  },
)

const totalText = computed(() => String(Math.max(0, Number(props.total || 0))))

const pageInfoText = computed(() => {
  const total = Math.max(0, Number(props.total || 0))
  const pageSize = Math.max(1, Number(props.pageSize || 10))
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const page = Math.min(Math.max(1, Number(props.page || 1)), pages)
  if (total <= 0) return ''
  return `第 ${page}/${pages} 页`
})

const activeFilters = computed(() => {
  return (props.filters || [])
    .filter((x) => x && x.key && x.label && String(x.value || '').trim())
    .map((x) => ({ ...x, value: String(x.value).trim() }))
})
</script>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.78);
  backdrop-filter: saturate(120%) blur(6px);
}

.left {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.count {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  font-weight: 900;
}
.count-num {
  font-size: 16px;
}
.count-suffix {
  font-size: 12px;
  color: rgba(15, 23, 42, 0.56);
  font-weight: 700;
}
.page {
  font-size: 12px;
}

.right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
  text-align: right;
}

@media (max-width: 640px) {
  .bar {
    flex-direction: column;
    align-items: flex-start;
  }
  .right {
    width: 100%;
    justify-content: flex-start;
    text-align: left;
  }
}
</style>



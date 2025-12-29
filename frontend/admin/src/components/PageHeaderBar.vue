<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { findBreadcrumbByPath, getAdminNavGroups, getDealerNavGroups, getProviderNavGroups } from '../lib/nav'
import { getSession, isAdmin, isProvider } from '../lib/auth'

type Props = {
  title: string
}

const props = defineProps<Props>()

const route = useRoute()
const activePath = computed(() => String(route.path || ''))

const session = computed(() => getSession())
const actorType = computed(() => session.value?.actorType)

// 仅用于面包屑匹配：不依赖 icon，因此传空对象即可
const emptyIcons = {} as any

const navGroups = computed(() => {
  if (isProvider(actorType.value)) return getProviderNavGroups(emptyIcons)
  if (isAdmin(actorType.value) && activePath.value.startsWith('/dealer/')) return getDealerNavGroups(emptyIcons)
  return getAdminNavGroups(emptyIcons)
})

const breadcrumb = computed(() => findBreadcrumbByPath(navGroups.value, activePath.value))
</script>

<template>
  <div class="ph">
    <div class="ph__main">
      <el-breadcrumb v-if="breadcrumb" separator="/" class="ph__breadcrumb">
        <el-breadcrumb-item>{{ breadcrumb.groupLabel }}</el-breadcrumb-item>
        <el-breadcrumb-item>{{ breadcrumb.itemLabel }}</el-breadcrumb-item>
      </el-breadcrumb>
      <div class="ph__title">{{ props.title }}</div>
    </div>

    <div class="ph__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<style scoped>
.ph {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ph__main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ph__breadcrumb {
  font-size: 12px;
}

.ph__title {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
}

.ph__extra {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>


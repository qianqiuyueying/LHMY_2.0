<template>
  <div class="page-header">
    <div class="page-header-inner">
      <div class="titles">
        <div class="title">{{ title }}</div>
        <div v-if="subtitle" class="subtitle muted">{{ subtitle }}</div>
      </div>
      <div class="actions">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.page-header {
  padding: 18px 16px;
  border-radius: 16px;
  background: radial-gradient(800px 280px at 10% 0%, rgba(20, 184, 166, 0.14), transparent 60%),
    radial-gradient(700px 240px at 90% 0%, rgba(15, 118, 110, 0.12), transparent 55%),
    rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.page-header-inner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.title {
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.02em;
}

.subtitle {
  margin-top: 6px;
  font-size: 14px;
}

.actions {
  display: flex;
  align-items: center;
}

@media (max-width: 640px) {
  .page-header {
    padding: 14px 14px;
  }
  .title {
    font-size: 22px;
  }
}
</style>



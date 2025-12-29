<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <router-view />
    </n-message-provider>
  </n-config-provider>
</template>
<script setup lang="ts">
import type { GlobalThemeOverrides } from 'naive-ui'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import { RouterView } from 'vue-router'

// 官网视觉基线（v1）：品牌调性“可信赖、健康活力、现代简洁”
// 说明：更细的组件级视觉（卡片阴影/渐变氛围/空态几何）由页面与全局 CSS 负责。
const themeOverrides: GlobalThemeOverrides = {
  common: {
    // teal（健康活力）
    primaryColor: '#14b8a6',
    primaryColorHover: '#2dd4bf',
    primaryColorPressed: '#0f766e',
    // CTA（适中使用）
    warningColor: '#f59e0b',
    warningColorHover: '#fbbf24',
    warningColorPressed: '#d97706',
    borderRadius: '12px',
  },
}
</script>

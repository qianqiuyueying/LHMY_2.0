<template>
  <div class="section">
    <div class="container">
      <n-space vertical :size="16">
        <page-header title="联系我们" subtitle="合作咨询、业务对接与问题反馈。" />

        <n-card size="large" :segmented="{ content: true }">
          <n-space vertical :size="10">
            <n-alert v-if="errorText" type="warning" show-icon :title="errorText">
              <n-space style="margin-top: 8px">
                <n-button size="small" @click="load()">重试</n-button>
              </n-space>
            </n-alert>

            <div>
              <b>合作邮箱：</b>
              <a v-if="email" :href="`mailto:${email}`">{{ email }}</a>
              <span v-else>—</span>
            </div>
            <div><b>电话：</b>{{ phone || '—' }}</div>
            <div class="muted">（信息来自官网页脚配置；未配置时会提示并显示占位符。）</div>
          </n-space>
        </n-card>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NSpace } from 'naive-ui'

import { apiGet } from '../lib/api'
import PageHeader from '../components/PageHeader.vue'

type FooterConfig = {
  cooperationEmail?: string
  cooperationPhone?: string
}

const footer = ref<FooterConfig | null>(null)
const errorText = ref<string>('')

const email = computed(() => String(footer.value?.cooperationEmail || '').trim())
const phone = computed(() => String(footer.value?.cooperationPhone || '').trim())

async function load() {
  errorText.value = ''
  try {
    footer.value = await apiGet<FooterConfig>('/v1/website/footer/config')
  } catch (e) {
    footer.value = null
    errorText.value = e instanceof Error ? e.message : '联系方式加载失败'
  }
}

onMounted(load)
</script>

<style scoped>
</style>


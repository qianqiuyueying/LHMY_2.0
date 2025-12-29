<script setup lang="ts">
import { ElMessage } from 'element-plus'

type Props = {
  title?: string
  message?: string
  retryText?: string
  code?: string
  requestId?: string
}

withDefaults(defineProps<Props>(), {
  title: '加载失败',
  message: '请稍后重试。',
  retryText: '重试',
  code: '',
  requestId: '',
})

const emit = defineEmits<{ retry: [] }>()

function suggestion(code: string): string {
  const c = String(code || '').trim().toUpperCase()
  if (!c) return ''
  if (c === 'UNAUTHORIZED') return '建议：请重新登录后重试。'
  if (c === 'FORBIDDEN') return '建议：请确认账号权限（或联系管理员）后重试。'
  if (c === 'INVALID_ARGUMENT') return '建议：请检查输入内容/格式后重试。'
  if (c === 'NOT_FOUND') return '建议：资源可能已不存在，刷新列表后重试。'
  if (c === 'STATE_CONFLICT') return '建议：可能存在并发修改，刷新后重试。'
  if (c === 'RATE_LIMITED') return '建议：请求过于频繁，请稍后再试。'
  if (c === 'INTERNAL_ERROR') return '建议：请稍后重试，必要时联系技术支持。'
  return ''
}

async function copyRequestId(id: string) {
  const rid = String(id || '').trim()
  if (!rid) return
  try {
    await navigator.clipboard.writeText(rid)
    ElMessage.success('requestId 已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

async function copyCode(code: string) {
  const c = String(code || '').trim()
  if (!c) return
  try {
    await navigator.clipboard.writeText(c)
    ElMessage.success('错误码已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}
</script>

<template>
  <div class="box">
    <el-result icon="error" :title="title" :sub-title="message">
      <template #extra>
        <div class="extra">
          <div v-if="code" class="rid">
            <span class="rid__label">错误码：</span>
            <el-text class="rid__value">{{ code }}</el-text>
            <el-button size="small" @click="copyCode(code)">复制</el-button>
          </div>
          <div v-if="requestId" class="rid">
            <span class="rid__label">requestId：</span>
            <el-text class="rid__value">{{ requestId }}</el-text>
            <el-button size="small" @click="copyRequestId(requestId)">复制</el-button>
          </div>
          <el-text v-if="code" type="info" style="font-size: 12px">{{ suggestion(code) }}</el-text>
          <el-button type="primary" @click="emit('retry')">{{ retryText }}</el-button>
        </div>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.box {
  padding: 12px 8px;
}

.extra {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.rid {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 640px;
  flex-wrap: wrap;
}

.rid__label {
  color: rgba(0, 0, 0, 0.55);
  font-size: 12px;
}

.rid__value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}
</style>


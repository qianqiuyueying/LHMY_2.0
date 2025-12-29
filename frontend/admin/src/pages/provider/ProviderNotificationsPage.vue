<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'

type NotificationItem = {
  id: string
  title: string
  content: string
  category?: string | null
  status: 'UNREAD' | 'READ'
  createdAt: string
  readAt?: string | null
}

const loading = ref(false)
const tab = ref<'UNREAD' | 'READ'>('UNREAD')
const rows = ref<NotificationItem[]>([])

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: NotificationItem[]; total: number }>('/provider/notifications', {
      query: { status: tab.value, page: 1, pageSize: 50 },
    })
    rows.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载失败')
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function markRead(id: string) {
  try {
    await apiRequest(`/provider/notifications/${id}/read`, { method: 'POST' })
    rows.value = rows.value.filter((x) => x.id !== id)
    ElMessage.success('已标记已读')
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="通知" />

    <el-card class="lh-card">
      <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
        <el-segmented v-model="tab" :options="['UNREAD', 'READ']" @change="load" />
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>

      <PageEmptyState
        v-if="!loading && rows.length === 0"
        :title="tab === 'UNREAD' ? '暂无未读通知' : '暂无已读通知'"
        description="运营/系统通知会出现在这里。"
        style="margin-top: 12px"
      />

      <el-timeline v-else style="margin-top: 12px">
        <el-timeline-item v-for="n in rows" :key="n.id" :timestamp="n.createdAt" placement="top">
          <div style="display: flex; justify-content: space-between; align-items: start; gap: 12px">
            <div style="flex: 1">
              <div style="font-weight: 700; display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
                <span>{{ n.title }}</span>
                <el-tag v-if="n.category" size="small" type="info">{{ n.category }}</el-tag>
              </div>
              <div style="margin-top: 6px; color: var(--lh-muted)">{{ n.content }}</div>
              <div v-if="tab === 'READ' && n.readAt" style="margin-top: 6px; font-size: 12px; color: var(--lh-muted-2)">已读时间：{{ n.readAt }}</div>
            </div>
            <el-button v-if="tab === 'UNREAD'" size="small" type="primary" @click="markRead(n.id)">标记已读</el-button>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>


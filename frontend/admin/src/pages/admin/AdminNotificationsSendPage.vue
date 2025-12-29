<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'

type AudienceMode = 'ALL_ADMINS' | 'ALL_DEALERS' | 'ALL_PROVIDERS' | 'TARGETED'
type ReceiverType = 'ADMIN' | 'DEALER' | 'PROVIDER' | 'PROVIDER_STAFF'
type Category = 'SYSTEM' | 'ACTIVITY' | 'OPS'

type ReceiverOption = { id: string; receiverType: ReceiverType; label: string }

const submitting = ref(false)
const searching = ref(false)
const receiverKeyword = ref('')
const receiverOptions = ref<ReceiverOption[]>([])
const selectedIds = ref<string[]>([])
const selectedMap = ref<Record<string, ReceiverOption>>({})

const pasteIdsText = ref('')
const router = useRouter()

const form = reactive({
  title: '',
  content: '',
  category: 'SYSTEM' as Category,
  mode: 'ALL_DEALERS' as AudienceMode,
  targetedReceiverType: 'DEALER' as ReceiverType,
})

function clearTargeted() {
  receiverKeyword.value = ''
  receiverOptions.value = []
  selectedIds.value = []
  selectedMap.value = {}
  pasteIdsText.value = ''
}

async function searchReceivers(query: string) {
  if (form.mode !== 'TARGETED') return
  const q = String(query || '').trim()
  receiverKeyword.value = q
  if (q.length < 1) {
    receiverOptions.value = []
    return
  }
  searching.value = true
  try {
    const data = await apiRequest<{ items: ReceiverOption[]; page: number; pageSize: number; total: number }>(
      '/admin/notification-receivers',
      { query: { receiverType: form.targetedReceiverType, keyword: q, page: 1, pageSize: 20 } },
    )
    receiverOptions.value = (data.items || []).map((x) => ({ id: String(x.id), receiverType: x.receiverType as ReceiverType, label: String(x.label) }))
  } catch (e: any) {
    receiverOptions.value = []
    handleApiError(e, { router, fallbackMessage: '搜索失败' })
  } finally {
    searching.value = false
  }
}

function onChangeSelected(ids: string[]) {
  selectedIds.value = ids
  // 把当前 options 的 label 记下来，保证“已选列表”可显示
  const next: Record<string, ReceiverOption> = { ...selectedMap.value }
  for (const opt of receiverOptions.value) {
    if (ids.includes(opt.id)) next[opt.id] = opt
  }
  // 清理被移除项
  for (const k of Object.keys(next)) {
    if (!ids.includes(k)) delete next[k]
  }
  selectedMap.value = next
}

const parsedTargets = computed(() => {
  if (form.mode !== 'TARGETED') return []
  const fromSelect = selectedIds.value.map((id) => ({ receiverType: form.targetedReceiverType, receiverId: id }))
  const fromPaste = String(pasteIdsText.value || '')
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((id) => ({ receiverType: form.targetedReceiverType, receiverId: id }))
  const merged = [...fromSelect, ...fromPaste]
  const seen = new Set<string>()
  const uniq: { receiverType: ReceiverType; receiverId: string }[] = []
  for (const t of merged) {
    const key = `${t.receiverType}:${t.receiverId}`
    if (seen.has(key)) continue
    seen.add(key)
    uniq.push(t)
  }
  return uniq
})

function validate(): string | null {
  if (!String(form.title || '').trim()) return '标题不能为空'
  if (String(form.title).trim().length > 256) return '标题不能超过 256 字'
  if (!String(form.content || '').trim()) return '内容不能为空'
  if (String(form.content).length > 4000) return '内容不能超过 4000 字'
  if (form.mode === 'TARGETED' && parsedTargets.value.length < 1) return '定向发送：请先搜索并选择接收者（或粘贴ID快速添加）'
  return null
}

async function submit() {
  const err = validate()
  if (err) return ElMessage.error(err)

  const body = {
    title: String(form.title).trim(),
    content: String(form.content),
    category: form.category,
    audience: {
      mode: form.mode,
      targets: form.mode === 'TARGETED' ? parsedTargets.value : [],
    },
  }

  submitting.value = true
  try {
    const idem = newIdempotencyKey()
    const data = await apiRequest<{ success: boolean; createdCount: number; batchId: string }>(
      '/admin/notifications/send',
      { method: 'POST', body, idempotencyKey: idem },
    )
    ElMessage.success(`发送成功：已创建 ${data.createdCount} 条通知`)
    form.title = ''
    form.content = ''
    clearTargeted()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '发送失败' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div>
    <PageHeaderBar title="通知管理" description="手工发送站内通知（群发/定向）。" />

    <el-card class="lh-card">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>发送说明（v1.1）</template>
        <div style="line-height: 1.7">
          <div>通知采用 fan-out 投递：会为每个接收者创建一条通知记录。</div>
          <div style="color: var(--lh-muted); margin-top: 4px">
            定向模式已升级为“搜索选择”；如需批量快速添加，也可以粘贴账号ID（同一类型，按行分隔）。
          </div>
        </div>
      </el-alert>

      <el-form label-width="110px">
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="256" show-word-limit placeholder="例如：系统维护通知" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="6" maxlength="4000" show-word-limit placeholder="支持换行，建议包含：时间、影响范围、处理方式等" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.category">
            <el-radio-button label="SYSTEM">系统</el-radio-button>
            <el-radio-button label="ACTIVITY">活动</el-radio-button>
            <el-radio-button label="OPS">运营</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发送范围">
          <el-radio-group v-model="form.mode" @change="clearTargeted">
            <el-radio label="ALL_ADMINS">所有运营（Admin）</el-radio>
            <el-radio label="ALL_DEALERS">所有经销商（Dealer）</el-radio>
            <el-radio label="ALL_PROVIDERS">所有服务商（Provider）</el-radio>
            <el-radio label="TARGETED">定向（指定账号ID）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.mode === 'TARGETED'" label="定向接收者">
          <div style="width: 100%">
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px">
              <span style="color: var(--lh-muted)">接收者类型</span>
              <el-select v-model="form.targetedReceiverType" style="width: 220px" @change="clearTargeted">
                <el-option label="运营账号（ADMIN）" value="ADMIN" />
                <el-option label="经销商账号（DEALER）" value="DEALER" />
                <el-option label="服务商主账号（PROVIDER）" value="PROVIDER" />
                <el-option label="服务商员工账号（PROVIDER_STAFF）" value="PROVIDER_STAFF" />
              </el-select>
              <span style="color: var(--lh-muted)">已选 {{ parsedTargets.length }} 个（自动去重）</span>
            </div>

            <el-select
              v-model="selectedIds"
              multiple
              filterable
              remote
              reserve-keyword
              :remote-method="searchReceivers"
              :loading="searching"
              style="width: 100%"
              placeholder="输入关键词搜索（用户名/主体名），选择后会加入接收者列表"
              @change="onChangeSelected"
            >
              <el-option v-for="opt in receiverOptions" :key="opt.id" :label="opt.label" :value="opt.id" />
            </el-select>

            <div v-if="selectedIds.length > 0" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
              <el-tag v-for="id in selectedIds" :key="id" closable @close="onChangeSelected(selectedIds.filter((x) => x !== id))">
                {{ selectedMap[id]?.label ?? id }}
              </el-tag>
            </div>

            <el-collapse style="margin-top: 12px">
              <el-collapse-item title="批量快速添加（粘贴账号ID）" name="paste">
                <el-input v-model="pasteIdsText" type="textarea" :rows="5" placeholder="每行一个账号ID（同一类型），例如：\n8b6c...\n2a1f..." />
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">发送</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>


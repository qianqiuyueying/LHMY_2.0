<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type TagKind = 'PRODUCT' | 'SERVICE' | 'VENUE'
type NodeType = 'PRODUCT_TAG' | 'SERVICE_TAG' | 'VENUE_TAG'

type TaxNode = {
  id: string
  type: NodeType
  name: string
  sort: number
  status: 'ENABLED' | 'DISABLED' | string
  createdAt: string
  updatedAt: string
}

const active = ref<TagKind>('PRODUCT')
const nodeType = computed<NodeType>(() => (active.value === 'PRODUCT' ? 'PRODUCT_TAG' : active.value === 'SERVICE' ? 'SERVICE_TAG' : 'VENUE_TAG'))

const loading = ref(false)
const rows = ref<TaxNode[]>([])
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const createOpen = ref(false)
const createForm = reactive({
  name: '',
  sort: 0,
})

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: TaxNode[] }>('/admin/taxonomy-nodes', { query: { type: nodeType.value } })
    rows.value = data.items || []
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    rows.value = []
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.name = ''
  createForm.sort = 0
  createOpen.value = true
}

async function saveCreate() {
  const name = String(createForm.name || '').trim()
  if (!name) return ElMessage.error('名称不能为空')
  try {
    await apiRequest('/admin/taxonomy-nodes', { method: 'POST', body: { type: nodeType.value, name, sort: Number(createForm.sort || 0) } })
    ElMessage.success('已创建')
    createOpen.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '创建失败')
  }
}

async function toggleStatus(row: TaxNode) {
  const next = row.status === 'ENABLED' ? 'DISABLED' : 'ENABLED'
  try {
    await ElMessageBox.confirm(`确认将标签「${row.name}」设置为 ${next}？`, '确认操作', { type: 'warning' })
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/taxonomy-nodes/${row.id}`, { method: 'PUT', body: { status: next } })
    ElMessage.success('已更新')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '更新失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="标签库（全局）" />

    <el-card class="lh-card" style="margin-top: 12px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>说明</template>
        <div style="line-height: 1.7">
          <div>标签为全局库，由 Admin 统一维护；Provider 创建商品/服务时只能从此处选择。</div>
          <div style="color: var(--lh-muted); margin-top: 4px">类型区分：产品标签 / 服务标签 / 场所标签。</div>
        </div>
      </el-alert>

      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap">
        <el-segmented v-model="active" :options="[{ label: '产品标签', value: 'PRODUCT' }, { label: '服务标签', value: 'SERVICE' }, { label: '场所标签', value: 'VENUE' }]" @change="load" />
        <div style="display: flex; gap: 8px">
          <el-button type="primary" @click="openCreate">新增标签</el-button>
          <el-button :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无标签" description="点击右上角“新增标签”创建。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="name" label="名称" min-width="240" />
        <el-table-column prop="sort" label="排序" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.status === 'ENABLED' ? 'success' : 'info'">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="200" />
        <el-table-column label="操作" width="160">
          <template #default="scope">
            <el-button size="small" @click="toggleStatus(scope.row)">{{ scope.row.status === 'ENABLED' ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createOpen" title="新增标签" width="520px">
      <el-form label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="例如：上门体检 / 体检服务 / 物流商品" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="createForm.sort" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" @click="saveCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>



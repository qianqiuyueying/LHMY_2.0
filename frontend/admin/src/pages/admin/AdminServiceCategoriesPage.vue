<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type Status = 'ENABLED' | 'DISABLED'
type Item = {
  id: string
  code: string
  displayName: string
  status: Status
  sort: number
  createdAt?: string | null
  updatedAt?: string | null
}

const STATUS_LABEL: Record<Status, string> = {
  ENABLED: '启用',
  DISABLED: '停用',
}

const loading = ref(false)
const rows = ref<Item[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

const filters = reactive({
  keyword: '',
  status: '' as '' | Status,
})

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<Item>>('/admin/service-categories', {
      query: {
        keyword: filters.keyword || null,
        status: filters.status || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items || []
    total.value = data.total
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    errorText.value = e?.apiError?.message ?? '加载失败'
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: '加载失败' })
  } finally {
    loading.value = false
  }
}

const editorOpen = ref(false)
const editorMode = ref<'CREATE' | 'EDIT'>('CREATE')
const editorTitle = computed(() => (editorMode.value === 'CREATE' ? '新增服务大类' : '编辑服务大类'))
const editingId = ref<string | null>(null)

const form = reactive({
  code: '',
  displayName: '',
  sort: 0,
})

function openCreate() {
  editorMode.value = 'CREATE'
  editingId.value = null
  Object.assign(form, { code: '', displayName: '', sort: 0 })
  editorOpen.value = true
}

function openEdit(row: Item) {
  editorMode.value = 'EDIT'
  editingId.value = row.id
  Object.assign(form, { code: row.code, displayName: row.displayName, sort: Number(row.sort ?? 0) })
  editorOpen.value = true
}

async function save() {
  const code = String(form.code || '').trim().toUpperCase()
  const displayName = String(form.displayName || '').trim()
  const sort = Number(form.sort ?? 0)
  if (!displayName) return ElMessage.error('中文名称不能为空')

  try {
    if (editorMode.value === 'CREATE') {
      if (!code) return ElMessage.error('code 不能为空')
      await apiRequest<Item>('/admin/service-categories', { method: 'POST', body: { code, displayName, sort } })
      ElMessage.success('已新增')
    } else {
      if (!editingId.value) return
      await apiRequest<Item>(`/admin/service-categories/${editingId.value}`, { method: 'PUT', body: { displayName, sort } })
      ElMessage.success('已保存')
    }
    editorOpen.value = false
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  }
}

async function enable(row: Item) {
  try {
    await apiRequest<Item>(`/admin/service-categories/${row.id}/enable`, { method: 'POST' })
    ElMessage.success('已启用')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function disable(row: Item) {
  try {
    await ElMessageBox.confirm('确认停用该服务大类？停用后将无法用于新建服务包模板/健行天下服务（历史数据不受影响）。', '停用', {
      type: 'warning',
      confirmButtonText: '停用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest<Item>(`/admin/service-categories/${row.id}/disable`, { method: 'POST' })
    ElMessage.success('已停用')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="服务大类管理（serviceType）" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
      <template #title>说明（v1）</template>
      <div style="line-height: 1.7">
        <div>本页维护“健行天下/供给侧”统一的服务大类字典。</div>
        <div style="color: var(--lh-muted); margin-top: 4px">
          停用不会影响历史订单/权益查询，但会禁止在新建服务包模板与 Provider 健行天下服务中选择该类目。
        </div>
      </div>
    </el-alert>

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="code / 中文名" style="width: 240px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="启用（ENABLED）" value="ENABLED" />
            <el-option label="停用（DISABLED）" value="DISABLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            @click="
              page = 1;
              load()
            "
          >
            查询
          </el-button>
          <el-button
            @click="
              filters.keyword = '';
              filters.status = '';
              page = 1;
              load()
            "
          >
            重置
          </el-button>
          <el-button type="success" @click="openCreate">新增</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState v-if="!loading && errorText" :message="errorText" :code="errorCode" :requestId="errorRequestId" style="margin-top: 12px" @retry="load" />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无服务大类" description="建议先新增：例如 GYM（健身）、DENTAL（口腔）等。" style="margin-top: 12px" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="code" label="code（serviceType）" width="220" />
        <el-table-column prop="displayName" label="中文名称" min-width="220" />
        <el-table-column prop="sort" label="排序" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small" :type="scope.row.status === 'ENABLED' ? 'success' : 'info'">
                {{ STATUS_LABEL[scope.row.status as keyof typeof STATUS_LABEL] ?? scope.row.status }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="200" />
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <el-button size="small" type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button v-if="scope.row.status === 'ENABLED'" size="small" type="warning" @click="disable(scope.row)">停用</el-button>
            <el-button v-else size="small" type="success" @click="enable(scope.row)">启用</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="editorOpen" :title="editorTitle" width="720px">
      <el-form label-width="120px">
        <el-form-item label="code（必填）">
          <div class="lh-form-item-stack">
            <el-input
              v-model="form.code"
              :disabled="editorMode !== 'CREATE'"
              placeholder="例如：GYM / DENTAL_CLEANING"
              style="width: 420px"
            />
            <div class="lh-form-hint">
              约束：仅大写字母/数字/下划线，长度 2~64；一旦产生业务数据后不建议变更（v1 禁止修改）。
            </div>
          </div>
        </el-form-item>
        <el-form-item label="中文名称（必填）">
          <el-input v-model="form.displayName" placeholder="例如：健身" style="width: 360px" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="9999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lh-form-item-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.lh-form-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lh-muted);
  line-height: 1.6;
  max-width: 520px;
}
</style>

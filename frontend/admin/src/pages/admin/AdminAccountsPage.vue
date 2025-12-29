<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { handleApiError } from '../../lib/error-handling'

type ProviderUserItem = {
  id: string
  username: string
  providerId: string
  providerName: string
  status: 'ACTIVE' | 'SUSPENDED' | string
  createdAt: string
  updatedAt?: string | null
}

type ProviderStaffItem = {
  id: string
  username: string
  providerId: string
  providerName: string
  status: 'ACTIVE' | 'SUSPENDED' | string
  createdAt: string
  updatedAt?: string | null
}

type DealerUserItem = {
  id: string
  username: string
  dealerId: string
  dealerName: string
  status: 'ACTIVE' | 'SUSPENDED' | string
  createdAt: string
  updatedAt?: string | null
}

type AdminUserItem = {
  id: string
  username: string
  status: 'ACTIVE' | 'SUSPENDED' | string
  phone?: string | null
  createdAt: string
  updatedAt?: string | null
}

const activeTab = ref<'ADMIN' | 'PROVIDER' | 'PROVIDER_STAFF' | 'DEALER'>('PROVIDER')
const keyword = ref('')

const loading = ref(false)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const providerRows = ref<ProviderUserItem[]>([])
const providerStaffRows = ref<ProviderStaffItem[]>([])
const dealerRows = ref<DealerUserItem[]>([])
const adminRows = ref<AdminUserItem[]>([])

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const router = useRouter()

const rows = computed(() => {
  if (activeTab.value === 'ADMIN') return adminRows.value
  if (activeTab.value === 'PROVIDER') return providerRows.value
  if (activeTab.value === 'PROVIDER_STAFF') return providerStaffRows.value
  return dealerRows.value
})

const createDialogOpen = ref(false)
const createForm = reactive({
  username: '',
  providerName: '',
  providerId: '',
  dealerName: '',
})

const passwordDialogOpen = ref(false)
const passwordDialogTitle = ref('')
const generatedPassword = ref('')
const manualCopyOpen = ref(false)
const manualCopyText = ref('')

const providerOptionsLoading = ref(false)
const providerOptions = ref<Array<{ providerId: string; providerName: string }>>([])

function resetListState() {
  page.value = 1
  total.value = 0
  errorText.value = ''
  errorCode.value = ''
  errorRequestId.value = ''
}

function openCreate() {
  createForm.username = ''
  createForm.providerName = ''
  createForm.providerId = ''
  createForm.dealerName = ''
  createDialogOpen.value = true
}

function statusLabel(status: string): string {
  const s = String(status || '').toUpperCase()
  if (s === 'ACTIVE') return '启用'
  if (s === 'SUSPENDED') return '冻结'
  if (s === 'PENDING_REVIEW') return '待审核'
  return s || '-'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status || '').toUpperCase()
  if (s === 'ACTIVE') return 'success'
  if (s === 'PENDING_REVIEW') return 'warning'
  if (s === 'SUSPENDED') return 'danger'
  return 'info'
}

async function copy(text: string) {
  const v = String(text || '').trim()
  if (!v) return
  try {
    await navigator.clipboard.writeText(v)
    ElMessage.success('已复制')
  } catch {
    // 安卓 WebView / 非 https / 权限限制：兜底到“可手动复制”弹窗
    try {
      const ta = document.createElement('textarea')
      ta.value = v
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.top = '0'
      ta.style.left = '0'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (ok) {
        ElMessage.success('已复制')
        return
      }
    } catch {
      // ignore
    }

    manualCopyText.value = v
    manualCopyOpen.value = true
    // 提示一次即可，避免反复 toast 干扰
    ElMessage.warning('系统限制导致无法自动复制：请在弹窗中长按选择后复制')
  }
}

async function load() {
  loading.value = true
  try {
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''

    if (activeTab.value === 'ADMIN') {
      const data = await apiRequest<PageResp<AdminUserItem>>('/admin/admin-users', {
        query: { keyword: keyword.value || null, page: page.value, pageSize: pageSize.value },
      })
      adminRows.value = data.items || []
      total.value = data.total
      return
    }

    if (activeTab.value === 'PROVIDER') {
      const data = await apiRequest<PageResp<ProviderUserItem>>('/admin/provider-users', {
        query: { keyword: keyword.value || null, page: page.value, pageSize: pageSize.value },
      })
      providerRows.value = data.items || []
      total.value = data.total
      return
    }

    if (activeTab.value === 'PROVIDER_STAFF') {
      const data = await apiRequest<PageResp<ProviderStaffItem>>('/admin/provider-staff', {
        query: { keyword: keyword.value || null, page: page.value, pageSize: pageSize.value },
      })
      providerStaffRows.value = data.items || []
      total.value = data.total
      return
    }

    const data = await apiRequest<PageResp<DealerUserItem>>('/admin/dealer-users', {
      query: { keyword: keyword.value || null, page: page.value, pageSize: pageSize.value },
    })
    dealerRows.value = data.items || []
    total.value = data.total
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

async function loadProviderOptions() {
  // v1 最小：从 provider-users 列表中抽取 providerId/providerName 作为 staff 绑定下拉
  providerOptionsLoading.value = true
  try {
    const data = await apiRequest<PageResp<ProviderUserItem>>('/admin/provider-users', {
      query: { page: 1, pageSize: 200 },
    })
    const map = new Map<string, string>()
    for (const x of data.items || []) {
      if (!x?.providerId) continue
      map.set(x.providerId, x.providerName || x.providerId)
    }
    providerOptions.value = Array.from(map.entries()).map(([providerId, providerName]) => ({ providerId, providerName }))
    if (!createForm.providerId && providerOptions.value[0]?.providerId) createForm.providerId = providerOptions.value[0].providerId
  } catch {
    providerOptions.value = []
  } finally {
    providerOptionsLoading.value = false
  }
}

async function saveCreate() {
  try {
    const username = createForm.username.trim()
    if (!username) {
      ElMessage.error('username 不能为空')
      return
    }

    if (activeTab.value === 'ADMIN') {
      const res = await apiRequest<{ adminUser: AdminUserItem; password: string }>('/admin/admin-users', {
        method: 'POST',
        body: { username },
      })
      createDialogOpen.value = false
      passwordDialogTitle.value = `Admin 账号创建成功（${res.adminUser.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    if (activeTab.value === 'PROVIDER') {
      const providerName = createForm.providerName.trim()
      if (!providerName) {
        ElMessage.error('主体名称不能为空')
        return
      }
      const res = await apiRequest<{ providerUser: ProviderUserItem; password: string }>('/admin/provider-users', {
        method: 'POST',
        body: { username, providerName },
      })
      createDialogOpen.value = false
      passwordDialogTitle.value = `Provider 账号创建成功（${res.providerUser.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    if (activeTab.value === 'PROVIDER_STAFF') {
      const providerId = String(createForm.providerId || '').trim()
      if (!providerId) {
        ElMessage.error('请选择 providerId')
        return
      }
      const res = await apiRequest<{ providerStaff: ProviderStaffItem; password: string }>('/admin/provider-staff', {
        method: 'POST',
        body: { username, providerId },
      })
      createDialogOpen.value = false
      passwordDialogTitle.value = `ProviderStaff 账号创建成功（${res.providerStaff.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    const dealerName = createForm.dealerName.trim()
    if (!dealerName) {
      ElMessage.error('主体名称不能为空')
      return
    }
    const res = await apiRequest<{ dealerUser: DealerUserItem; password: string }>('/admin/dealer-users', {
      method: 'POST',
      body: { username, dealerName },
    })
    createDialogOpen.value = false
    passwordDialogTitle.value = `Dealer 账号创建成功（${res.dealerUser.username}）`
    generatedPassword.value = res.password
    passwordDialogOpen.value = true
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '创建失败' })
  }
}

async function resetPassword(row: ProviderUserItem | ProviderStaffItem | DealerUserItem | AdminUserItem) {
  try {
    await ElMessageBox.confirm(`确认重置账号 ${row.username} 的密码？新密码仅显示一次。`, '重置密码', {
      type: 'warning',
      confirmButtonText: '确认重置',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    if (activeTab.value === 'ADMIN') {
      const res = await apiRequest<{ adminUser: AdminUserItem; password: string }>(`/admin/admin-users/${row.id}/reset-password`, {
        method: 'POST',
      })
      passwordDialogTitle.value = `Admin 密码已重置（${res.adminUser.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    if (activeTab.value === 'PROVIDER') {
      const res = await apiRequest<{ providerUser: ProviderUserItem; password: string }>(
        `/admin/provider-users/${row.id}/reset-password`,
        { method: 'POST' },
      )
      passwordDialogTitle.value = `Provider 密码已重置（${res.providerUser.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    if (activeTab.value === 'PROVIDER_STAFF') {
      const res = await apiRequest<{ providerStaff: ProviderStaffItem; password: string }>(
        `/admin/provider-staff/${row.id}/reset-password`,
        { method: 'POST' },
      )
      passwordDialogTitle.value = `ProviderStaff 密码已重置（${res.providerStaff.username}）`
      generatedPassword.value = res.password
      passwordDialogOpen.value = true
      await load()
      return
    }

    const res = await apiRequest<{ dealerUser: DealerUserItem; password: string }>(`/admin/dealer-users/${row.id}/reset-password`, {
      method: 'POST',
    })
    passwordDialogTitle.value = `Dealer 密码已重置（${res.dealerUser.username}）`
    generatedPassword.value = res.password
    passwordDialogOpen.value = true
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function toggleProviderStaffStatus(row: ProviderStaffItem) {
  const isActive = String(row.status || '').toUpperCase() === 'ACTIVE'
  try {
    await ElMessageBox.confirm(
      isActive ? `确认禁用员工账号 ${row.username}？` : `确认启用员工账号 ${row.username}？`,
      isActive ? '禁用账号' : '启用账号',
      {
        type: 'warning',
        confirmButtonText: '确认',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }

  try {
    if (isActive) {
      await apiRequest(`/admin/provider-staff/${row.id}/suspend`, { method: 'POST' })
      ElMessage.success('已禁用')
    } else {
      await apiRequest(`/admin/provider-staff/${row.id}/activate`, { method: 'POST' })
      ElMessage.success('已启用')
    }
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function toggleProviderUserStatus(row: ProviderUserItem) {
  const st = String(row.status || '').toUpperCase()
  const isActive = st === 'ACTIVE'
  const isPending = st === 'PENDING_REVIEW'
  try {
    await ElMessageBox.confirm(
      isActive
        ? `确认冻结账号 ${row.username}？冻结后将禁止登录与发起新业务，但不影响历史数据。`
        : isPending
          ? `确认通过注册并启用账号 ${row.username}？启用后即可登录。`
          : `确认启用账号 ${row.username}？`,
      isActive ? '冻结账号' : isPending ? '通过注册' : '启用账号',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    if (isActive) {
      await apiRequest(`/admin/provider-users/${row.id}/suspend`, { method: 'POST' })
      ElMessage.success('已冻结')
    } else {
      await apiRequest(`/admin/provider-users/${row.id}/activate`, { method: 'POST' })
      ElMessage.success('已启用')
    }
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

async function toggleDealerUserStatus(row: DealerUserItem) {
  const st = String(row.status || '').toUpperCase()
  const isActive = st === 'ACTIVE'
  const isPending = st === 'PENDING_REVIEW'
  try {
    await ElMessageBox.confirm(
      isActive
        ? `确认冻结账号 ${row.username}？冻结后将禁止登录与发起新业务，但不影响历史数据。`
        : isPending
          ? `确认通过注册并启用账号 ${row.username}？启用后即可登录。`
          : `确认启用账号 ${row.username}？`,
      isActive ? '冻结账号' : isPending ? '通过注册' : '启用账号',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    if (isActive) {
      await apiRequest(`/admin/dealer-users/${row.id}/suspend`, { method: 'POST' })
      ElMessage.success('已冻结')
    } else {
      await apiRequest(`/admin/dealer-users/${row.id}/activate`, { method: 'POST' })
      ElMessage.success('已启用')
    }
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function toggleAdminUserStatus(row: AdminUserItem) {
  const isActive = String(row.status || '').toUpperCase() === 'ACTIVE'
  try {
    await ElMessageBox.confirm(
      isActive ? `确认冻结账号 ${row.username}？` : `确认启用账号 ${row.username}？`,
      isActive ? '冻结账号' : '启用账号',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    if (isActive) {
      await apiRequest(`/admin/admin-users/${row.id}/suspend`, { method: 'POST' })
      ElMessage.success('已冻结')
    } else {
      await apiRequest(`/admin/admin-users/${row.id}/activate`, { method: 'POST' })
      ElMessage.success('已启用')
    }
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '操作失败' })
  }
}

function onTabChange() {
  resetListState()
  providerRows.value = []
  providerStaffRows.value = []
  dealerRows.value = []
  adminRows.value = []
  if (activeTab.value === 'PROVIDER_STAFF') loadProviderOptions()
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="账号管理">
      <template #extra>
        <el-input v-model="keyword" placeholder="按 username/主体名称搜索" style="width: 260px" clearable />
        <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
        <el-button @click="keyword=''; page=1; load()">重置</el-button>
        <el-button type="success" @click="openCreate">创建账号</el-button>
      </template>
    </PageHeaderBar>

    <el-card>
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="Admin 账号" name="ADMIN" />
        <el-tab-pane label="Provider 账号" name="PROVIDER" />
        <el-tab-pane label="Provider 员工账号" name="PROVIDER_STAFF" />
        <el-tab-pane label="Dealer 账号" name="DEALER" />
      </el-tabs>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState v-else-if="!loading && rows.length === 0" title="暂无账号" />

      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="username" label="登录名" width="200" />

        <el-table-column v-if="activeTab === 'ADMIN'" prop="phone" label="手机号" width="160" />

        <el-table-column v-if="activeTab === 'PROVIDER'" prop="providerName" label="主体名称" min-width="220" />
        <el-table-column v-if="activeTab === 'PROVIDER'" prop="providerId" label="服务方ID" width="260" />

        <el-table-column v-if="activeTab === 'PROVIDER_STAFF'" prop="providerName" label="主体名称" min-width="220" />
        <el-table-column v-if="activeTab === 'PROVIDER_STAFF'" prop="providerId" label="服务方ID" width="260" />

        <el-table-column v-if="activeTab === 'DEALER'" prop="dealerName" label="主体名称" min-width="220" />
        <el-table-column v-if="activeTab === 'DEALER'" prop="dealerId" label="经销商ID" width="260" />

        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag size="small" :type="statusTagType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="操作" width="260">
          <template #default="scope">
            <el-button type="warning" size="small" @click="resetPassword(scope.row)">重置密码</el-button>
            <el-button
              v-if="activeTab === 'ADMIN'"
              :type="String(scope.row.status).toUpperCase() === 'ACTIVE' ? 'danger' : 'success'"
              size="small"
              @click="toggleAdminUserStatus(scope.row)"
            >
              {{ String(scope.row.status).toUpperCase() === 'ACTIVE' ? '冻结' : '启用' }}
            </el-button>
            <el-button
              v-if="activeTab === 'PROVIDER'"
              :type="String(scope.row.status).toUpperCase() === 'ACTIVE' ? 'danger' : 'success'"
              size="small"
              @click="toggleProviderUserStatus(scope.row)"
            >
              {{
                String(scope.row.status).toUpperCase() === 'ACTIVE'
                  ? '冻结'
                  : String(scope.row.status).toUpperCase() === 'PENDING_REVIEW'
                    ? '通过注册'
                    : '启用'
              }}
            </el-button>
            <el-button
              v-if="activeTab === 'PROVIDER_STAFF'"
              :type="String(scope.row.status).toUpperCase() === 'ACTIVE' ? 'danger' : 'success'"
              size="small"
              @click="toggleProviderStaffStatus(scope.row)"
            >
              {{ String(scope.row.status).toUpperCase() === 'ACTIVE' ? '禁用' : '启用' }}
            </el-button>
            <el-button
              v-if="activeTab === 'DEALER'"
              :type="String(scope.row.status).toUpperCase() === 'ACTIVE' ? 'danger' : 'success'"
              size="small"
              @click="toggleDealerUserStatus(scope.row)"
            >
              {{
                String(scope.row.status).toUpperCase() === 'ACTIVE'
                  ? '冻结'
                  : String(scope.row.status).toUpperCase() === 'PENDING_REVIEW'
                    ? '通过注册'
                    : '启用'
              }}
            </el-button>
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

    <el-dialog
      v-model="createDialogOpen"
      :title="
        activeTab === 'ADMIN'
          ? '创建 Admin 账号'
          : activeTab === 'PROVIDER'
            ? '创建 Provider 账号'
            : activeTab === 'PROVIDER_STAFF'
              ? '创建 Provider 员工账号'
              : '创建 Dealer 账号'
      "
      width="560px"
    >
      <el-form label-width="110px">
        <el-form-item label="登录名">
          <el-input v-model="createForm.username" placeholder="唯一登录名" />
        </el-form-item>
        <el-form-item v-if="activeTab === 'ADMIN'" label="说明">
          <el-text type="info">新 Admin 默认未绑定手机号；如需 2FA，请登录后在“安全设置”绑定。</el-text>
        </el-form-item>
        <el-form-item v-else-if="activeTab === 'PROVIDER'" label="主体名称">
          <el-input v-model="createForm.providerName" placeholder="例如：北京 XX 健康中心" />
        </el-form-item>
        <el-form-item v-else-if="activeTab === 'PROVIDER_STAFF'" label="绑定 Provider">
          <el-select
            v-model="createForm.providerId"
            filterable
            placeholder="请选择 providerId"
            style="width: 360px"
            :loading="providerOptionsLoading"
          >
            <el-option
              v-for="p in providerOptions"
              :key="p.providerId"
              :label="`${p.providerName} (${p.providerId})`"
              :value="p.providerId"
            />
          </el-select>
          <el-button style="margin-left: 8px" :loading="providerOptionsLoading" @click="loadProviderOptions">刷新</el-button>
        </el-form-item>
        <el-form-item v-else label="主体名称">
          <el-input v-model="createForm.dealerName" placeholder="例如：XX 经销商" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="saveCreate">创建并生成密码</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogOpen" :title="passwordDialogTitle" width="600px">
      <el-alert title="该密码只会显示一次，请立即复制保存；关闭后无法再次查看明文。" type="warning" show-icon :closable="false" />
      <div style="margin-top: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap">
        <el-text style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace">
          {{ generatedPassword }}
        </el-text>
        <el-button size="small" @click="copy(generatedPassword)">复制密码</el-button>
      </div>
      <template #footer>
        <el-button type="primary" @click="passwordDialogOpen = false">我已保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="manualCopyOpen" title="请手动复制" width="560px">
      <el-alert title="自动复制在部分安卓平板/内置浏览器会被系统限制。请长按或全选后复制。" type="warning" show-icon :closable="false" />
      <div style="margin-top: 12px">
        <el-input v-model="manualCopyText" type="textarea" :rows="3" readonly />
      </div>
      <template #footer>
        <el-button type="primary" @click="manualCopyOpen = false">我已复制</el-button>
      </template>
    </el-dialog>
  </div>
</template>


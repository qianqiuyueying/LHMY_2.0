<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type VenueLite = { id: string; name: string; publishStatus: string }

type Schedule = {
  id: string
  venueId: string
  serviceType: string
  bookingDate: string
  timeSlot: string
  capacity: number
  remainingCapacity: number
  status: 'ENABLED' | 'DISABLED'
}

const venues = ref<VenueLite[]>([])
const venueId = ref('')
const venueName = ref('')

type VenueServiceLite = { id: string; serviceType: string; title: string; productId?: string | null; status: string }
const servicesLoading = ref(false)
const services = ref<VenueServiceLite[]>([])

const serviceGroups = computed(() => {
  const items = (services.value || []).filter((x) => x.status === 'ENABLED')
  const health = items.filter((x) => !x.productId).map((x) => ({ label: `${x.title}（${x.serviceType}）`, value: x.serviceType }))
  const infra = items.filter((x) => !!x.productId).map((x) => ({ label: `${x.title}（${x.serviceType}）`, value: x.serviceType }))
  return [
    { label: '健行天下服务（权益）', options: health },
    { label: '基建联防服务型商品（订单）', options: infra },
  ].filter((g) => g.options.length > 0)
})

const filters = reactive({
  serviceType: '',
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<Schedule[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

const addDialogOpen = ref(false)
const addForm = reactive({ serviceType: '', bookingDate: '', timeSlot: '', capacity: 10 })

async function loadVenues() {
  const data = await apiRequest<{ items: VenueLite[]; total: number }>('/provider/venues')
  venues.value = data.items
  if (venues.value.length > 1) {
    ElMessage.warning('检测到多个场所（异常数据），已默认选择第一条作为当前场所')
  }
  if (venues.value[0]?.id) {
    venueId.value = venues.value[0].id
    venueName.value = venues.value[0].name
  }
}

async function loadServices() {
  if (!venueId.value) return
  servicesLoading.value = true
  try {
    const data = await apiRequest<{ items: VenueServiceLite[]; total: number }>(`/provider/venues/${venueId.value}/services`)
    services.value = data.items || []
    // 新增对话框默认选第一项（若存在）
    if (!addForm.serviceType && services.value[0]?.serviceType) addForm.serviceType = services.value[0].serviceType
  } catch {
    services.value = []
  } finally {
    servicesLoading.value = false
  }
}

async function loadSchedules() {
  if (!venueId.value) return
  loading.value = true
  try {
    const data = await apiRequest<PageResp<Schedule>>(`/provider/venues/${venueId.value}/schedules`, {
      query: {
        serviceType: filters.serviceType || null,
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        page: page.value,
        pageSize: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
    errorText.value = ''
    errorCode.value = ''
    errorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    errorText.value = msg
    errorCode.value = e?.apiError?.code ?? ''
    errorRequestId.value = e?.apiError?.requestId ?? ''
    ElMessage.error(
      `${msg}${errorCode.value ? `（code=${errorCode.value}）` : ''}${errorRequestId.value ? `（requestId=${errorRequestId.value}）` : ''}`,
    )
  } finally {
    loading.value = false
  }
}

async function addOne() {
  if (!venueId.value) return
  try {
    if (!String(addForm.serviceType || '').trim()) return ElMessage.error('服务编码（serviceType）不能为空')
    if (!String(addForm.bookingDate || '').trim()) return ElMessage.error('日期（bookingDate）不能为空')
    if (!String(addForm.timeSlot || '').trim()) return ElMessage.error('时段（timeSlot）不能为空')
    await apiRequest(`/provider/venues/${venueId.value}/schedules/batch`, {
      method: 'PUT',
      body: {
        items: [
          {
            serviceType: addForm.serviceType,
            bookingDate: addForm.bookingDate,
            timeSlot: addForm.timeSlot,
            capacity: addForm.capacity,
          },
        ],
      },
    })
    ElMessage.success('已更新')
    addDialogOpen.value = false
    await loadSchedules()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '更新失败')
  }
}

onMounted(async () => {
  await loadVenues()
  await loadServices()
  await loadSchedules()
})
</script>

<template>
  <div>
    <PageHeaderBar title="排期/容量" />

    <el-alert
      title="排期用于控制可预约容量：先选择场所，再按服务/日期筛选；新增/调整只影响单条时段。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="场所">
          <el-tag type="info">{{ venueName || '—' }}</el-tag>
        </el-form-item>
        <el-form-item label="服务">
          <el-select v-model="filters.serviceType" filterable clearable placeholder="全部服务" style="width: 320px" :loading="servicesLoading">
            <el-option label="全部" value="" />
            <el-option-group v-for="g in serviceGroups" :key="g.label" :label="g.label">
              <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; loadSchedules()">查询</el-button>
          <el-button @click="filters.serviceType='';filters.dateFrom='';filters.dateTo='';page=1;loadSchedules()">重置</el-button>
          <el-button type="success" @click="addDialogOpen = true">新增/调整(单条)</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        style="margin-top: 12px"
        @retry="loadSchedules"
      />
      <PageEmptyState
        v-else-if="!loading && rows.length === 0"
        title="暂无排期"
        description="可尝试：选择场所；缩小日期范围；或先在“服务管理”创建服务后再配置排期。"
        style="margin-top: 12px"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="bookingDate" label="日期" width="140" />
        <el-table-column prop="timeSlot" label="时段" width="160" />
        <el-table-column prop="serviceType" label="服务编码" width="180" />
        <el-table-column prop="capacity" label="总容量" width="120" />
        <el-table-column prop="remainingCapacity" label="剩余" width="120" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.status === 'ENABLED' ? 'success' : 'info'">{{ scope.row.status }}</el-tag>
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
          @change="loadSchedules"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogOpen" title="新增/调整排期（单条）" width="520px">
      <el-form label-width="100px">
        <el-form-item label="服务">
          <el-select v-model="addForm.serviceType" filterable placeholder="请选择服务" style="width: 360px" :loading="servicesLoading">
            <el-option-group v-for="g in serviceGroups" :key="g.label" :label="g.label">
              <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="日期（bookingDate）"><el-input v-model="addForm.bookingDate" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="时段（timeSlot）"><el-input v-model="addForm.timeSlot" placeholder="HH:mm-HH:mm" /></el-form-item>
        <el-form-item label="容量（capacity）"><el-input-number v-model="addForm.capacity" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="addOne">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

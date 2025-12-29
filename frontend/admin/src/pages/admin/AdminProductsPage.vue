<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type ProductItem = {
  id: string
  title: string
  fulfillmentType: 'SERVICE' | 'PHYSICAL_GOODS'
  providerId: string
  providerName: string
  categoryId?: string | null
  price: { original: number; employee?: number | null; member?: number | null; activity?: number | null }
  stock?: number | null
  reservedStock?: number | null
  weight?: number | null
  shippingFee?: number | null
  status: 'PENDING_REVIEW' | 'ON_SALE' | 'OFF_SHELF' | 'REJECTED'
  rejectReason?: string | null
  rejectedAt?: string | null
  createdAt: string
}

const PRODUCT_STATUS_LABEL: Record<ProductItem['status'], string> = {
  PENDING_REVIEW: '待审核',
  ON_SALE: '已上架',
  OFF_SHELF: '已下架',
  REJECTED: '已驳回',
}

const PRODUCT_FULFILLMENT_LABEL: Record<ProductItem['fulfillmentType'], string> = {
  SERVICE: '到店服务',
  PHYSICAL_GOODS: '物流商品',
}

const filters = reactive({
  keyword: '',
  providerId: '',
  categoryId: '',
  status: '' as '' | ProductItem['status'],
  fulfillmentType: '' as '' | ProductItem['fulfillmentType'],
})

const loading = ref(false)
const rows = ref<ProductItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<ProductItem>>('/admin/products', {
      query: {
        keyword: filters.keyword || null,
        providerId: filters.providerId || null,
        categoryId: filters.categoryId || null,
        status: filters.status || null,
        fulfillmentType: filters.fulfillmentType || null,
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

async function approve(id: string) {
  try {
    await ElMessageBox.confirm('确认通过该商品审核？通过后商品将进入可售状态（若业务流程允许）。', '确认通过', {
      type: 'warning',
      confirmButtonText: '通过',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/products/${id}/approve`, { method: 'PUT' })
    ElMessage.success('已通过')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function reject(id: string) {
  let reason = ''
  try {
    const r = await ElMessageBox.prompt('请输入驳回原因（将展示给 Provider，可覆盖更新）', '确认驳回', {
      type: 'warning',
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：封面不清晰/价格不合理/信息不完整…',
      inputValidator: (v: string) => {
        if (!String(v || '').trim()) return '驳回原因不能为空'
        if (String(v || '').trim().length > 200) return '驳回原因最多 200 字'
        return true
      },
    })
    reason = String(r?.value || '').trim()
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/products/${id}/reject`, { method: 'PUT', body: { reason } })
    ElMessage.success('已驳回')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

async function offShelf(id: string) {
  try {
    await ElMessageBox.confirm('确认下架该商品？下架后用户将无法继续购买。', '确认下架', {
      type: 'warning',
      confirmButtonText: '下架',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await apiRequest(`/admin/products/${id}/off-shelf`, { method: 'PUT' })
    ElMessage.success('已下架')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="商品审核/监管" />

    <el-card style="margin-top: 12px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>说明（v2）</template>
        <div style="line-height: 1.7">
          <div>当前电商侧商品履约类型包含：<b>到店服务</b>（SERVICE）与 <b>物流商品</b>（PHYSICAL_GOODS）。</div>
          <div style="color: var(--lh-muted); margin-top: 4px">物流商品关键字段：库存/运费/重量（可选）。</div>
        </div>
      </el-alert>
      <el-form :inline="true" label-width="90px">
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="商品名" style="width: 220px" />
        </el-form-item>
        <el-form-item label="服务方ID">
          <el-input v-model="filters.providerId" placeholder="可选（精确）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="类目ID">
          <el-input v-model="filters.categoryId" placeholder="类目ID（categoryId）" style="width: 180px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="待审核（PENDING_REVIEW）" value="PENDING_REVIEW" />
            <el-option label="已上架（ON_SALE）" value="ON_SALE" />
            <el-option label="已下架（OFF_SHELF）" value="OFF_SHELF" />
            <el-option label="已驳回（REJECTED）" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item label="履约类型">
          <el-select v-model="filters.fulfillmentType" placeholder="全部" style="width: 160px">
            <el-option label="全部" value="" />
            <el-option label="到店服务（SERVICE）" value="SERVICE" />
            <el-option label="物流商品（PHYSICAL_GOODS）" value="PHYSICAL_GOODS" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button @click="filters.keyword='';filters.providerId='';filters.categoryId='';filters.status='';filters.fulfillmentType='';page=1;load()">重置</el-button>
        </el-form-item>
      </el-form>

      <PageErrorState
        v-if="!loading && errorText"
        :message="errorText"
        :code="errorCode"
        :requestId="errorRequestId"
        @retry="load"
      />
      <PageEmptyState
        v-else-if="!loading && rows.length === 0"
        title="暂无商品"
        description="可尝试：调整筛选条件；本地/测试环境可执行“演示数据初始化（seed）”生成可操作数据。"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="id" label="商品ID" width="220" />
        <el-table-column prop="title" label="名称" min-width="220" />
        <el-table-column prop="providerName" label="商家" width="180" />
        <el-table-column label="履约类型" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.fulfillmentType" placement="top">
              <el-tag size="small">{{ PRODUCT_FULFILLMENT_LABEL[scope.row.fulfillmentType as keyof typeof PRODUCT_FULFILLMENT_LABEL] ?? scope.row.fulfillmentType }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="price.original" label="原价" width="100" />
        <el-table-column prop="price.activity" label="活动价" width="100" />
        <el-table-column prop="price.member" label="会员价" width="100" />
        <el-table-column prop="price.employee" label="员工价" width="100" />
        <el-table-column label="库存" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">{{ scope.row.stock ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="占用" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">{{ scope.row.reservedStock ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="运费" width="110">
          <template #default="scope">
            <span v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">¥{{ scope.row.shippingFee ?? 0 }}</span>
            <span v-else style="color: var(--lh-muted)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.status" placement="top">
              <el-tag size="small">{{ PRODUCT_STATUS_LABEL[scope.row.status as keyof typeof PRODUCT_STATUS_LABEL] ?? scope.row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260">
          <template #default="scope">
            <el-button v-if="scope.row.status === 'PENDING_REVIEW'" type="success" size="small" @click="approve(scope.row.id)">通过</el-button>
            <el-button v-if="scope.row.status === 'PENDING_REVIEW'" type="danger" size="small" @click="reject(scope.row.id)">驳回</el-button>
            <el-button v-if="scope.row.status === 'ON_SALE'" type="warning" size="small" @click="offShelf(scope.row.id)">下架</el-button>
            <el-tag v-if="scope.row.status !== 'PENDING_REVIEW' && scope.row.status !== 'ON_SALE'" size="small" type="info">只读</el-tag>
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
  </div>
</template>

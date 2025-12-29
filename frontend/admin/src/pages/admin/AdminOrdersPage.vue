<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiException, apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import { handleApiError as handleApiErrorGlobal } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { useRouter } from 'vue-router'

type OrderItem = {
  id: string
  orderNo: string
  userId: string
  buyerPhoneMasked?: string | null
  orderType: 'PRODUCT' | 'SERVICE_PACKAGE'
  paymentStatus: 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED'
  fulfillmentType?: 'SERVICE' | 'PHYSICAL_GOODS' | null
  fulfillmentStatus?: 'NOT_SHIPPED' | 'SHIPPED' | 'DELIVERED' | 'RECEIVED' | null
  totalAmount: number
  goodsAmount?: number
  shippingAmount?: number
  shippingCarrier?: string | null
  trackingNoLast4?: string | null
  shippedAt?: string | null
  dealerId?: string | null
  providerId?: string | null
  createdAt: string
  paidAt?: string | null
}

const ORDER_TYPE_LABEL: Record<OrderItem['orderType'], string> = {
  PRODUCT: '电商商品',
  SERVICE_PACKAGE: '服务包（健行天下）',
}

const PAYMENT_STATUS_LABEL: Record<OrderItem['paymentStatus'], string> = {
  PENDING: '待支付',
  PAID: '已支付',
  FAILED: '失败',
  REFUNDED: '已退款',
}

const FULFILLMENT_TYPE_LABEL: Record<'SERVICE' | 'PHYSICAL_GOODS', string> = {
  SERVICE: '到店服务',
  PHYSICAL_GOODS: '物流商品',
}

const FULFILLMENT_STATUS_LABEL: Record<
  NonNullable<OrderItem['fulfillmentStatus']>,
  string
> = {
  NOT_SHIPPED: '待发货',
  SHIPPED: '已发货',
  DELIVERED: '已妥投',
  RECEIVED: '已签收',
}

const filters = reactive({
  orderNo: '',
  userId: '',
  phone: '',
  orderType: '' as '' | OrderItem['orderType'],
  paymentStatus: '' as '' | OrderItem['paymentStatus'],
  fulfillmentType: '' as '' | 'SERVICE' | 'PHYSICAL_GOODS',
  dealerId: '',
  providerId: '',
  dateFrom: '',
  dateTo: '',
})

const loading = ref(false)
const rows = ref<OrderItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')
const router = useRouter()

const shipDialogOpen = ref(false)
const shipTarget = ref<OrderItem | null>(null)
const shipForm = reactive({
  carrier: '',
  trackingNo: '',
})

function openShipDialog(row: OrderItem) {
  shipTarget.value = row
  shipForm.carrier = row.shippingCarrier || ''
  // 规格（TASK-P0-006）：列表不返回运单号明文，避免回显；需要发货时由运营重新输入
  shipForm.trackingNo = ''
  shipDialogOpen.value = true
}

function handleApiError(e: unknown, fallbackMessage: string): void {
  // 优先走全局统一口径（本页面保留旧逻辑作为兜底，便于渐进式收敛）
  try {
    handleApiErrorGlobal(e, { router, fallbackMessage, preferRefreshHintOn409: true })
    return
  } catch {
    // ignore
  }

  if (e instanceof ApiException) {
    const code = e.apiError.code
    // 401：apiRequest 已统一跳转登录；这里不重复弹窗避免噪声
    if (e.status === 401) return
    if (e.status === 403 || code === 'FORBIDDEN') {
      try {
        router.push('/403')
      } catch {
        // ignore
      }
      return
    }
    if (e.status === 409 && (code === 'STATE_CONFLICT' || code === 'INVALID_STATE_TRANSITION')) {
      ElMessage.warning('状态已变化，请刷新后重试')
      return
    }
    if (e.status === 400 || e.status === 404) {
      ElMessage.error(
        `${e.apiError.message}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
      )
      return
    }
    ElMessage.error(
      `${e.apiError.message || fallbackMessage}${code ? `（code=${code}）` : ''}${e.apiError.requestId ? `（requestId=${e.apiError.requestId}）` : ''}`,
    )
    return
  }
  ElMessage.error(fallbackMessage)
}

async function submitShip() {
  if (!shipTarget.value) return
  const id = shipTarget.value.id
  try {
    await apiRequest(`/admin/orders/${id}/ship`, {
      method: 'POST',
      body: { carrier: shipForm.carrier, trackingNo: shipForm.trackingNo },
    })
    ElMessage.success('已发货')
    shipDialogOpen.value = false
    await load()
  } catch (e: any) {
    handleApiError(e, '发货失败')
  }
}

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<OrderItem>>('/admin/orders', {
      query: {
        orderNo: filters.orderNo || null,
        userId: filters.userId || null,
        phone: filters.phone || null,
        orderType: filters.orderType || null,
        paymentStatus: filters.paymentStatus || null,
        fulfillmentType: filters.fulfillmentType || null,
        dealerId: filters.dealerId || null,
        providerId: filters.providerId || null,
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
    handleApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="订单监管" />

    <el-card style="margin-top: 12px">
      <el-form :inline="true" label-width="90px">
        <el-form-item label="订单号">
          <el-input v-model="filters.orderNo" placeholder="订单号/订单ID" style="width: 220px" />
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input v-model="filters.userId" placeholder="精确匹配" style="width: 220px" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="filters.phone" placeholder="模糊" style="width: 180px" />
        </el-form-item>
        <el-form-item label="订单类型">
          <el-select v-model="filters.orderType" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="电商商品（PRODUCT）" value="PRODUCT" />
            <el-option label="服务包（健行天下｜SERVICE_PACKAGE）" value="SERVICE_PACKAGE" />
          </el-select>
        </el-form-item>
        <el-form-item label="支付状态">
          <el-select v-model="filters.paymentStatus" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="待支付（PENDING）" value="PENDING" />
            <el-option label="已支付（PAID）" value="PAID" />
            <el-option label="失败（FAILED）" value="FAILED" />
            <el-option label="已退款（REFUNDED）" value="REFUNDED" />
          </el-select>
        </el-form-item>
        <el-form-item label="履约类型">
          <el-select v-model="filters.fulfillmentType" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="到店服务（SERVICE）" value="SERVICE" />
            <el-option label="物流商品（PHYSICAL_GOODS）" value="PHYSICAL_GOODS" />
          </el-select>
        </el-form-item>
        <el-form-item label="经销商ID">
          <el-input v-model="filters.dealerId" placeholder="可选（精确）" style="width: 180px" />
        </el-form-item>
        <el-form-item label="服务方ID">
          <el-input v-model="filters.providerId" placeholder="可选（精确）" style="width: 180px" />
        </el-form-item>
        <el-form-item label="起">
          <el-date-picker v-model="filters.dateFrom" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item label="止">
          <el-date-picker v-model="filters.dateTo" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="page = 1; load()">查询</el-button>
          <el-button
            @click="
              Object.assign(filters,{
                orderNo:'',userId:'',phone:'',orderType:'',paymentStatus:'',fulfillmentType:'',
                dealerId:'',providerId:'',dateFrom:'',dateTo:''
              });page=1;load()
            "
          >重置</el-button>
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
        title="暂无订单"
        description="可尝试：缩小日期范围或清空部分筛选条件；本地/测试环境可先执行“演示数据初始化（seed）”。"
      />
      <el-table v-else :data="rows" :loading="loading" style="width: 100%">
        <el-table-column prop="orderNo" label="订单号" width="220" />
        <el-table-column prop="buyerPhoneMasked" label="手机号" width="140" />
        <el-table-column label="订单类型" width="160">
          <template #default="scope">
            <el-tooltip :content="scope.row.orderType" placement="top">
              <el-tag size="small">{{ ORDER_TYPE_LABEL[scope.row.orderType as keyof typeof ORDER_TYPE_LABEL] ?? scope.row.orderType }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="支付状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.paymentStatus" placement="top">
              <el-tag size="small">{{ PAYMENT_STATUS_LABEL[scope.row.paymentStatus as keyof typeof PAYMENT_STATUS_LABEL] ?? scope.row.paymentStatus }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="履约类型" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.fulfillmentType" size="small">
              {{ FULFILLMENT_TYPE_LABEL[scope.row.fulfillmentType as keyof typeof FULFILLMENT_TYPE_LABEL] ?? scope.row.fulfillmentType }}
            </el-tag>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="物流状态" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.fulfillmentStatus" size="small">
              {{ FULFILLMENT_STATUS_LABEL[scope.row.fulfillmentStatus as keyof typeof FULFILLMENT_STATUS_LABEL] ?? scope.row.fulfillmentStatus }}
            </el-tag>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="totalAmount" label="金额" width="120" />
        <el-table-column label="物流信息" width="240">
          <template #default="scope">
            <div v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">
              <div style="font-size: 12px">
                {{ scope.row.shippingCarrier || '-' }}
              </div>
              <div style="font-size: 12px; color: rgba(0,0,0,.65)">
                {{ scope.row.trackingNoLast4 ? `****${scope.row.trackingNoLast4}` : '-' }}
              </div>
            </div>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="shippedAt" label="发货时间" width="200" />
        <el-table-column prop="dealerId" label="经销商ID" width="180" />
        <el-table-column prop="providerId" label="服务方ID" width="180" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column prop="paidAt" label="支付时间" width="200" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="scope">
            <el-button
              v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS' && scope.row.paymentStatus === 'PAID' && (scope.row.fulfillmentStatus === 'NOT_SHIPPED' || !scope.row.fulfillmentStatus)"
              type="primary"
              size="small"
              @click="openShipDialog(scope.row)"
            >
              发货
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

    <el-dialog v-model="shipDialogOpen" title="录入发货信息" width="520px">
      <el-form label-width="90px">
        <el-form-item label="快递公司">
          <el-input v-model="shipForm.carrier" placeholder="如：顺丰/中通" />
        </el-form-item>
        <el-form-item label="运单号">
          <el-input v-model="shipForm.trackingNo" placeholder="请输入运单号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialogOpen = false">取消</el-button>
        <el-button type="primary" @click="submitShip">确认发货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

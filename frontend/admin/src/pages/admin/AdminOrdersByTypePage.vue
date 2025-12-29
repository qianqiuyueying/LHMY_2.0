<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type OrderType = 'PRODUCT' | 'SERVICE_PACKAGE'
type PaymentStatus = 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED'

type OrderItem = {
  id: string
  orderNo: string
  userId: string
  buyerPhoneMasked?: string | null
  orderType: OrderType
  paymentStatus: PaymentStatus
  fulfillmentType?: 'SERVICE' | 'PHYSICAL_GOODS' | null
  fulfillmentStatus?: 'NOT_SHIPPED' | 'SHIPPED' | 'DELIVERED' | 'RECEIVED' | null
  totalAmount: number
  dealerId?: string | null
  providerId?: string | null
  shippingCarrier?: string | null
  trackingNoLast4?: string | null
  shippedAt?: string | null
  createdAt: string
  paidAt?: string | null
}

const ORDER_TYPE_LABEL: Record<OrderType, string> = {
  PRODUCT: '电商商品/服务（基建联防）',
  SERVICE_PACKAGE: '服务包（健行天下）',
}

const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
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

const route = useRoute()
const fixedOrderType = computed(() => String(route.meta?.orderType || '') as OrderType)
const pageTitle = computed(() => `订单监管 · ${ORDER_TYPE_LABEL[fixedOrderType.value] ?? fixedOrderType.value}`)

const filters = reactive({
  orderNo: '',
  userId: '',
  phone: '',
  paymentStatus: '' as '' | PaymentStatus,
  fulfillmentType: '' as '' | 'SERVICE' | 'PHYSICAL_GOODS',
  dealerId: '',
  providerId: '',
  dateFrom: '',
  dateTo: '',
})

const showDealer = computed(() => fixedOrderType.value === 'SERVICE_PACKAGE')

const loading = ref(false)
const rows = ref<OrderItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const errorText = ref('')
const errorCode = ref('')
const errorRequestId = ref('')

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<PageResp<OrderItem>>('/admin/orders', {
      query: {
        orderNo: filters.orderNo || null,
        userId: filters.userId || null,
        phone: filters.phone || null,
        orderType: fixedOrderType.value,
        paymentStatus: filters.paymentStatus || null,
        fulfillmentType: fixedOrderType.value === 'PRODUCT' ? filters.fulfillmentType || null : null,
        dealerId: showDealer.value ? filters.dealerId || null : null,
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
    ElMessage.error(
      `${msg}${errorCode.value ? `（code=${errorCode.value}）` : ''}${errorRequestId.value ? `（requestId=${errorRequestId.value}）` : ''}`,
    )
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar :title="pageTitle" />

    <el-card style="margin-top: 12px">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>说明</template>
        <div style="line-height: 1.7">
          <div>本页为“按业务线拆分后的订单监管视图”，避免把不同业务的订单类型混在同一语境里。</div>
          <div style="margin-top: 6px; color: rgba(0, 0, 0, 0.6)">
            当前视图固定订单类型：{{ fixedOrderType }}（{{ fixedOrderType === 'PRODUCT' ? '基建联防商品/服务订单' : '健行天下服务包订单' }}）
          </div>
        </div>
      </el-alert>

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
        <el-form-item label="支付状态">
          <el-select v-model="filters.paymentStatus" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="待支付（PENDING）" value="PENDING" />
            <el-option label="已支付（PAID）" value="PAID" />
            <el-option label="失败（FAILED）" value="FAILED" />
            <el-option label="已退款（REFUNDED）" value="REFUNDED" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="fixedOrderType === 'PRODUCT'" label="履约类型">
          <el-select v-model="filters.fulfillmentType" placeholder="全部" style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="到店服务（SERVICE）" value="SERVICE" />
            <el-option label="物流商品（PHYSICAL_GOODS）" value="PHYSICAL_GOODS" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="showDealer" label="经销商ID">
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
              Object.assign(filters, { orderNo: '', userId: '', phone: '', paymentStatus: '', fulfillmentType: '', dealerId: '', providerId: '', dateFrom: '', dateTo: '' });
              page = 1;
              load()
            "
          >
            重置
          </el-button>
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
        <el-table-column label="订单类型" width="180">
          <template #default="scope">
            <el-tooltip :content="scope.row.orderType" placement="top">
              <el-tag size="small">
                {{ ORDER_TYPE_LABEL[scope.row.orderType as keyof typeof ORDER_TYPE_LABEL] ?? scope.row.orderType }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="支付状态" width="140">
          <template #default="scope">
            <el-tooltip :content="scope.row.paymentStatus" placement="top">
              <el-tag size="small">
                {{ PAYMENT_STATUS_LABEL[scope.row.paymentStatus as keyof typeof PAYMENT_STATUS_LABEL] ?? scope.row.paymentStatus }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" label="履约类型" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.fulfillmentType" size="small">
              {{ FULFILLMENT_TYPE_LABEL[scope.row.fulfillmentType as keyof typeof FULFILLMENT_TYPE_LABEL] ?? scope.row.fulfillmentType }}
            </el-tag>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" label="物流状态" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.fulfillmentStatus" size="small">
              {{ FULFILLMENT_STATUS_LABEL[scope.row.fulfillmentStatus as keyof typeof FULFILLMENT_STATUS_LABEL] ?? scope.row.fulfillmentStatus }}
            </el-tag>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="totalAmount" label="金额" width="120" />
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" label="物流信息" width="240">
          <template #default="scope">
            <div v-if="scope.row.fulfillmentType === 'PHYSICAL_GOODS'">
              <div style="font-size: 12px">{{ scope.row.shippingCarrier || '-' }}</div>
              <div style="font-size: 12px; color: rgba(0,0,0,.65)">{{ scope.row.trackingNoLast4 ? `****${scope.row.trackingNoLast4}` : '-' }}</div>
            </div>
            <span v-else style="color: rgba(0,0,0,.45)">-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" prop="shippedAt" label="发货时间" width="200" />
        <el-table-column v-if="showDealer" prop="dealerId" label="经销商ID" width="220" />
        <el-table-column prop="providerId" label="服务方ID" width="220" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column prop="paidAt" label="支付时间" width="200" />
      </el-table>

      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          @current-change="load"
          @size-change="
            () => {
              page = 1
              load()
            }
          "
        />
      </div>
    </el-card>
  </div>
</template>


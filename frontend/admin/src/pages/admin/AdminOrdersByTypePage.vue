<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiRequest } from '../../lib/api'
import type { PageResp } from '../../lib/pagination'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageEmptyState from '../../components/PageEmptyState.vue'
import PageErrorState from '../../components/PageErrorState.vue'
import { fmtBeijingDateTime } from '../../lib/time'

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
  goodsAmount?: number
  shippingAmount?: number
  dealerId?: string | null
  dealerLinkId?: string | null
  providerId?: string | null
  shippingCarrier?: string | null
  trackingNoLast4?: string | null
  shippedAt?: string | null
  deliveredAt?: string | null
  receivedAt?: string | null
  itemsCount?: number
  firstItemTitle?: string | null
  createdAt: string
  paidAt?: string | null
}

type OrderDetail = {
  id: string
  orderType: OrderType
  paymentStatus: PaymentStatus
  paymentMethod?: string | null
  totalAmount: number
  goodsAmount?: number
  shippingAmount?: number
  fulfillmentType?: 'SERVICE' | 'PHYSICAL_GOODS' | null
  fulfillmentStatus?: 'NOT_SHIPPED' | 'SHIPPED' | 'DELIVERED' | 'RECEIVED' | null
  shippingCarrier?: string | null
  trackingNoLast4?: string | null
  shippedAt?: string | null
  deliveredAt?: string | null
  receivedAt?: string | null
  shippingAddress?: { provinceCode?: string | null; cityCode?: string | null; districtCode?: string | null; phoneMasked?: string | null } | null
  buyerPhoneMasked?: string | null
  dealerId?: string | null
  dealerLinkId?: string | null
  createdAt?: string | null
  paidAt?: string | null
  items: Array<{
    id: string
    title: string
    quantity: number
    unitPrice: number
    unitPriceType?: string
    totalPrice: number
    itemType?: string
    itemId?: string
    regionScope?: string | null
    tier?: string | null
  }>
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

const shipDialogOpen = ref(false)
const shipTarget = ref<OrderItem | null>(null)
const shipForm = reactive({
  carrier: '',
  trackingNo: '',
})

const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<OrderDetail | null>(null)
const detailError = ref('')

function openShipDialog(row: OrderItem) {
  shipTarget.value = row
  shipForm.carrier = row.shippingCarrier || ''
  // 列表不回显运单号明文（规格）：发货时由运营重新输入
  shipForm.trackingNo = ''
  shipDialogOpen.value = true
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
    // 若当前详情正在看同一单，刷新详情
    if (detailOpen.value && detail.value?.id === id) {
      await loadDetail(id)
    }
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '发货失败'
    ElMessage.error(msg)
  }
}

async function submitDeliver(id: string) {
  try {
    await apiRequest(`/admin/orders/${id}/deliver`, { method: 'POST' })
    ElMessage.success('已标记妥投')
    await load()
    if (detailOpen.value && detail.value?.id === id) {
      await loadDetail(id)
    }
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '标记妥投失败'
    ElMessage.error(msg)
  }
}

async function openDetail(row: OrderItem) {
  detailOpen.value = true
  await loadDetail(row.id)
}

async function loadDetail(id: string) {
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await apiRequest<OrderDetail>(`/orders/${id}`)
    detail.value = data
  } catch (e: any) {
    detail.value = null
    detailError.value = e?.apiError?.message ?? '加载详情失败'
  } finally {
    detailLoading.value = false
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
        <el-table-column label="订单摘要" min-width="220">
          <template #default="scope">
            <div style="line-height: 1.4">
              <div style="font-weight: 600">
                {{ scope.row.firstItemTitle || '-' }}
              </div>
              <div style="font-size: 12px; color: rgba(0,0,0,.65)">
                共 {{ Number(scope.row.itemsCount || 0) }} 项
              </div>
            </div>
          </template>
        </el-table-column>
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
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" prop="shippedAt" label="发货时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" prop="deliveredAt" label="妥投时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column v-if="fixedOrderType === 'PRODUCT'" prop="receivedAt" label="签收时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column v-if="showDealer" prop="dealerId" label="经销商ID" width="220" />
        <el-table-column v-if="showDealer" prop="dealerLinkId" label="投放链接ID" width="220" />
        <el-table-column prop="providerId" label="服务方ID" width="220" />
        <el-table-column prop="createdAt" label="创建时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column prop="paidAt" label="支付时间" width="200" :formatter="fmtBeijingDateTime" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openDetail(scope.row)">详情</el-button>
            <el-button
              v-if="fixedOrderType === 'PRODUCT' && scope.row.fulfillmentType === 'PHYSICAL_GOODS' && scope.row.paymentStatus === 'PAID' && (scope.row.fulfillmentStatus === 'NOT_SHIPPED' || !scope.row.fulfillmentStatus)"
              type="primary"
              size="small"
              @click="openShipDialog(scope.row)"
            >
              发货
            </el-button>
            <el-button
              v-if="fixedOrderType === 'PRODUCT' && scope.row.fulfillmentType === 'PHYSICAL_GOODS' && scope.row.paymentStatus === 'PAID' && scope.row.fulfillmentStatus === 'SHIPPED'"
              type="success"
              size="small"
              @click="submitDeliver(scope.row.id)"
            >
              标记妥投
            </el-button>
          </template>
        </el-table-column>
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

    <el-drawer v-model="detailOpen" title="订单详情" size="55%" destroy-on-close>
      <div v-if="detailLoading" style="padding: 12px">加载中...</div>
      <el-alert v-else-if="detailError" type="error" :closable="false" :title="detailError" />
      <div v-else-if="detail" style="padding: 8px 4px">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.buyerPhoneMasked || '-' }}</el-descriptions-item>
          <el-descriptions-item label="订单类型">
            {{ ORDER_TYPE_LABEL[detail.orderType] ?? detail.orderType }}
          </el-descriptions-item>
          <el-descriptions-item label="支付状态">
            {{ PAYMENT_STATUS_LABEL[detail.paymentStatus] ?? detail.paymentStatus }}
          </el-descriptions-item>
          <el-descriptions-item label="总金额">¥{{ Number(detail.totalAmount || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.orderType === 'PRODUCT'" label="金额拆分">
            商品 ¥{{ Number(detail.goodsAmount || 0).toFixed(2) }} + 运费 ¥{{ Number(detail.shippingAmount || 0).toFixed(2) }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ fmtBeijingDateTime(null as any, null as any, detail.createdAt || '') }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ detail.paidAt ? fmtBeijingDateTime(null as any, null as any, detail.paidAt) : '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.orderType === 'PRODUCT'" label="履约类型">
            {{ detail.fulfillmentType ? (FULFILLMENT_TYPE_LABEL[detail.fulfillmentType] ?? detail.fulfillmentType) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.orderType === 'PRODUCT'" label="物流状态">
            {{ detail.fulfillmentStatus ? (FULFILLMENT_STATUS_LABEL[detail.fulfillmentStatus] ?? detail.fulfillmentStatus) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.orderType === 'SERVICE_PACKAGE'" label="经销商ID">{{ detail.dealerId || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.orderType === 'SERVICE_PACKAGE'" label="投放链接ID">{{ detail.dealerLinkId || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detail.orderType === 'PRODUCT' && detail.fulfillmentType === 'PHYSICAL_GOODS'" style="margin-top: 12px">
          <el-descriptions :column="2" border title="物流信息">
            <el-descriptions-item label="快递公司">{{ detail.shippingCarrier || '-' }}</el-descriptions-item>
            <el-descriptions-item label="运单后4位">{{ detail.trackingNoLast4 ? `****${detail.trackingNoLast4}` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="发货时间">{{ detail.shippedAt ? fmtBeijingDateTime(null as any, null as any, detail.shippedAt) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="妥投时间">{{ detail.deliveredAt ? fmtBeijingDateTime(null as any, null as any, detail.deliveredAt) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="签收时间">{{ detail.receivedAt ? fmtBeijingDateTime(null as any, null as any, detail.receivedAt) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="收货地区（脱敏）">
              <span v-if="detail.shippingAddress">
                {{ detail.shippingAddress.provinceCode || '-' }} / {{ detail.shippingAddress.cityCode || '-' }} / {{ detail.shippingAddress.districtCode || '-' }}
                {{ detail.shippingAddress.phoneMasked ? `（${detail.shippingAddress.phoneMasked}）` : '' }}
              </span>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>

          <div style="margin-top: 10px">
            <el-button
              v-if="detail.paymentStatus === 'PAID' && (detail.fulfillmentStatus === 'NOT_SHIPPED' || !detail.fulfillmentStatus)"
              type="primary"
              @click="openShipDialog({ id: detail.id, orderNo: detail.id, userId: '', orderType: detail.orderType, paymentStatus: detail.paymentStatus, fulfillmentType: detail.fulfillmentType, fulfillmentStatus: detail.fulfillmentStatus, totalAmount: detail.totalAmount, dealerId: detail.dealerId, dealerLinkId: detail.dealerLinkId, providerId: null, shippingCarrier: detail.shippingCarrier, trackingNoLast4: detail.trackingNoLast4, shippedAt: detail.shippedAt || null, deliveredAt: detail.deliveredAt || null, receivedAt: detail.receivedAt || null, createdAt: detail.createdAt || '', paidAt: detail.paidAt || null } as any)"
            >
              发货
            </el-button>
            <el-button
              v-if="detail.paymentStatus === 'PAID' && detail.fulfillmentStatus === 'SHIPPED'"
              type="success"
              @click="submitDeliver(detail.id)"
            >
              标记妥投
            </el-button>
          </div>
        </div>

        <div style="margin-top: 12px">
          <div style="font-weight: 600; margin: 8px 0">订单明细</div>
          <el-table :data="detail.items" size="small" style="width: 100%">
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="unitPrice" label="单价" width="120" />
            <el-table-column prop="totalPrice" label="小计" width="120" />
            <el-table-column prop="regionScope" label="区域范围" width="160" />
            <el-table-column prop="tier" label="等级" width="120" />
          </el-table>
        </div>
      </div>
      <div v-else style="padding: 12px">-</div>
    </el-drawer>
  </div>
</template>


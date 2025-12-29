<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiRequest, newIdempotencyKey } from '../../lib/api'
import PageHeaderBar from '../../components/PageHeaderBar.vue'

type VenueLite = { id: string; name: string; publishStatus: string }

const form = reactive({
  entitlementId: '',
  venueId: '',
  redemptionMethod: 'QR_CODE' as 'QR_CODE' | 'VOUCHER_CODE',
  payloadOrCode: '',
})

const verifying = ref(false)
const venuesLoading = ref(false)
const venues = ref<VenueLite[]>([])

function _safeDecode(s: string): string {
  try {
    return decodeURIComponent(s)
  } catch {
    return s
  }
}

function _parseFromUrlQuery(text: string): { entitlementId?: string; venueId?: string } | null {
  const raw = String(text || '').trim()
  if (!raw) return null

  // 允许用户粘贴整段 URL 或仅 query 部分
  const queryPart = raw.includes('?') ? raw.slice(raw.indexOf('?') + 1) : raw
  if (!queryPart.includes('=') && !queryPart.includes('&')) return null

  try {
    const sp = new URLSearchParams(queryPart)
    const entitlementId = sp.get('entitlementId') || sp.get('entitlement_id') || undefined
    const venueId = sp.get('venueId') || sp.get('venue_id') || undefined
    if (!entitlementId && !venueId) return null
    return {
      entitlementId: entitlementId ? _safeDecode(entitlementId) : undefined,
      venueId: venueId ? _safeDecode(venueId) : undefined,
    }
  } catch {
    return null
  }
}

function _parseFromJson(text: string): { entitlementId?: string; venueId?: string } | null {
  const raw = String(text || '').trim()
  if (!raw) return null
  if (!(raw.startsWith('{') || raw.startsWith('['))) return null
  try {
    const obj = JSON.parse(raw)
    if (!obj || typeof obj !== 'object') return null
    const entitlementId = (obj as any).entitlementId ?? (obj as any).entitlement_id
    const venueId = (obj as any).venueId ?? (obj as any).venue_id
    if (!entitlementId && !venueId) return null
    return {
      entitlementId: entitlementId ? String(entitlementId) : undefined,
      venueId: venueId ? String(venueId) : undefined,
    }
  } catch {
    return null
  }
}

function _parseFromRegex(text: string): { entitlementId?: string; venueId?: string } | null {
  const raw = String(text || '').trim()
  if (!raw) return null

  // 常见：entitlementId=... 或 entitlementId: ... 或 JSON 片段
  const m1 = raw.match(/entitlementId\s*=\s*([^&\s]+)/i)
  const m2 = raw.match(/"entitlementId"\s*:\s*"([^"]+)"/i)
  const m3 = raw.match(/entitlementId\s*:\s*([0-9a-zA-Z_-]+)/i)

  const v1 = raw.match(/venueId\s*=\s*([^&\s]+)/i)
  const v2 = raw.match(/"venueId"\s*:\s*"([^"]+)"/i)
  const v3 = raw.match(/venueId\s*:\s*([0-9a-zA-Z_-]+)/i)

  const entitlementId = m1?.[1] || m2?.[1] || m3?.[1] || ''
  const venueId = v1?.[1] || v2?.[1] || v3?.[1] || ''

  if (!entitlementId && !venueId) return null
  return {
    entitlementId: entitlementId ? _safeDecode(entitlementId) : undefined,
    venueId: venueId ? _safeDecode(venueId) : undefined,
  }
}

function tryParseFromPayload() {
  const text = form.payloadOrCode
  const parsed = _parseFromJson(text) || _parseFromUrlQuery(text) || _parseFromRegex(text)
  if (!parsed) {
    ElMessage.warning('未解析到 entitlementId/venueId（支持：URL query、JSON、entitlementId=...）')
    return
  }

  if (parsed.entitlementId) form.entitlementId = parsed.entitlementId
  // venueId 仅在当前未选择时才回填（避免覆盖用户已选场所）
  if (parsed.venueId && !String(form.venueId || '').trim()) form.venueId = parsed.venueId

  ElMessage.success(
    `已解析：${parsed.entitlementId ? 'entitlementId' : ''}${parsed.entitlementId && parsed.venueId ? ' + ' : ''}${parsed.venueId ? 'venueId' : ''}`,
  )
}

async function loadVenues() {
  venuesLoading.value = true
  try {
    const data = await apiRequest<{ items: VenueLite[]; total: number }>('/provider/venues')
    venues.value = data.items || []
    if (venues.value.length > 1) {
      ElMessage.warning('检测到多个场所（异常数据），已默认选择第一条作为当前场所')
    }
    if (venues.value[0]?.id) form.venueId = venues.value[0].id
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载场所失败')
    venues.value = []
  } finally {
    venuesLoading.value = false
  }
}

async function redeem() {
  verifying.value = true
  try {
    if (!String(form.venueId || '').trim()) {
      ElMessage.error('请先选择场所（venue）')
      return
    }
    if (!String(form.entitlementId || '').trim()) {
      ElMessage.error('entitlementId 不能为空')
      return
    }
    if (!String(form.payloadOrCode || '').trim()) {
      ElMessage.error(form.redemptionMethod === 'QR_CODE' ? '二维码 payload 不能为空' : '券码不能为空')
      return
    }

    try {
      await ElMessageBox.confirm(
        '确认发起核销？核销成功才会扣减次数；若该服务需要预约，必须存在已确认预约。',
        '确认核销',
        { type: 'warning', confirmButtonText: '确认核销', cancelButtonText: '取消' },
      )
    } catch {
      return
    }

    const idem = newIdempotencyKey()
    const data = await apiRequest<{
      redemptionRecordId: string
      entitlementId: string
      status: string
      remainingCount?: number
      entitlementStatus?: string
    }>(
      `/entitlements/${form.entitlementId}/redeem`,
      {
        method: 'POST',
        idempotencyKey: idem,
        body: {
          venueId: form.venueId,
          redemptionMethod: form.redemptionMethod,
          voucherCode: form.payloadOrCode,
        },
      },
    )
    ElMessage.success(
      `核销成功：${data.redemptionRecordId}${typeof data.remainingCount === 'number' ? `（剩余次数=${data.remainingCount}）` : ''}`,
    )
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '核销失败')
  } finally {
    verifying.value = false
  }
}

onMounted(loadVenues)
</script>

<template>
  <div>
    <PageHeaderBar title="核销" />

    <el-alert
      title="操作步骤：选择场所 → 填写 entitlementId（可从 payload 解析）→ 粘贴扫码 payload 或输入券码 → 确认核销。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-card class="lh-card">
      <el-form label-width="140px">
        <el-form-item label="核销方式">
          <el-radio-group v-model="form.redemptionMethod">
            <el-radio label="QR_CODE">扫码（二维码payload）</el-radio>
            <el-radio label="VOUCHER_CODE">输入券码</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="核销场所">
          <el-input :model-value="venues[0]?.name ? `${venues[0]?.name}（固定）` : '未找到可用场所'" disabled style="width: 360px" />
          <el-button style="margin-left: 8px" :loading="venuesLoading" @click="loadVenues">刷新</el-button>
          <div style="margin-top: 6px; font-size: 12px; color: rgba(0, 0, 0, 0.6)">
            说明：当前业务规则为“单 Provider=单场所”，核销场所固定为该场所。
          </div>
        </el-form-item>

        <el-form-item label="权益ID（entitlementId）">
          <el-input v-model="form.entitlementId" placeholder="必填（可从 payload 解析）" />
          <el-button style="margin-left: 8px" @click="tryParseFromPayload">从payload解析</el-button>
        </el-form-item>

        <el-form-item :label="form.redemptionMethod === 'QR_CODE' ? '二维码payload' : '券码'">
          <el-input
            v-model="form.payloadOrCode"
            type="textarea"
            :rows="4"
            :placeholder="form.redemptionMethod === 'QR_CODE' ? '粘贴扫码得到的 payload 文本（后端验签）' : '输入券码本身'"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="verifying" @click="redeem">确认核销</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        title="规则提示：需要预约的服务必须存在已确认预约；核销成功才扣次数。"
        type="info"
        show-icon
        :closable="false"
      />
    </el-card>
  </div>
</template>

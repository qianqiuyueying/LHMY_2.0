<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { apiRequest } from '../../lib/api'
import { uploadImage } from '../../lib/uploads'

type ReviewStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
type VenueLite = {
  id: string
  name: string
  publishStatus: string
  reviewStatus?: ReviewStatus | null
  rejectReason?: string | null
  rejectedAt?: string | null
  offlineReason?: string | null
  offlinedAt?: string | null
}

type VenueDetail = {
  id: string
  providerId: string
  name: string
  address?: string | null
  contactPhone?: string | null
  businessHours?: string | null
  countryCode?: string | null
  provinceCode?: string | null
  cityCode?: string | null
  description?: string | null
  logoUrl?: string | null
  coverImageUrl?: string | null
  imageUrls?: string[] | null
  tags?: string[] | null
  publishStatus?: string | null
  reviewStatus?: ReviewStatus | null
  rejectReason?: string | null
  rejectedAt?: string | null
  offlineReason?: string | null
  offlinedAt?: string | null
}

const loading = ref(false)
const venues = ref<VenueLite[]>([])

const currentId = ref('')
const formRef = ref<FormInstance>()
const form = reactive<VenueDetail>({
  id: '',
  providerId: '',
  name: '',
  address: '',
  contactPhone: '',
  businessHours: '',
  countryCode: '',
  provinceCode: '',
  cityCode: '',
  description: '',
  logoUrl: '',
  coverImageUrl: '',
  imageUrls: [],
  tags: [],
})

type CityItem = { code: string; name: string }
const cities = ref<CityItem[]>([])
const citiesLoading = ref(false)

const tagsLoading = ref(false)
const tagOptions = ref<string[]>([])

// el-upload 的 on-change 可能在同一文件的状态变化中触发多次，导致重复上传
const _uploadingUids = new Set<string>()

async function loadCities() {
  citiesLoading.value = true
  try {
    const data = await apiRequest<{ items: CityItem[]; defaultCode?: string | null }>('/regions/cities')
    // REGION_CITIES 读侧可能同时包含 PROVINCE/CITY；本页仅需要 CITY
    cities.value = (data.items || []).filter((x) => String(x?.code || '').startsWith('CITY:'))
  } catch {
    cities.value = []
  } finally {
    citiesLoading.value = false
  }
}

async function loadVenueTagOptions() {
  tagsLoading.value = true
  try {
    const data = await apiRequest<{ items: Array<{ id: string; name: string }> }>('/tags', { query: { type: 'VENUE' } })
    const names = (data.items || []).map((x) => String(x.name || '').trim()).filter((x) => !!x)
    const picked = asArray(form.tags)
    tagOptions.value = Array.from(new Set([...names, ...picked]))
  } catch {
    const picked = asArray(form.tags)
    tagOptions.value = Array.from(new Set(picked))
  } finally {
    tagsLoading.value = false
  }
}

function asArray(v: string[] | null | undefined): string[] {
  return Array.isArray(v) ? v.filter((x) => !!String(x || '').trim()).map((x) => String(x).trim()) : []
}

// 前端实时校验：与 showcaseChecks 口径保持一致（提交展示前强校验；保存允许草稿）
const rules: FormRules = {
  name: [{ required: true, message: '请输入场所名称', trigger: 'blur' }],
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  contactPhone: [
    { required: true, message: '请输入联系电话', trigger: 'blur' },
    {
      validator: (_rule: any, value: any, cb: any) => {
        const phone = String(value || '').trim()
        if (!phone) return cb(new Error('请输入联系电话'))
        if (!/^[0-9 \-]{6,20}$/.test(phone)) return cb(new Error('电话格式不正确（仅数字/空格/短横线，长度 6~20）'))
        return cb()
      },
      trigger: 'blur',
    },
  ],
  cityCode: [
    { required: true, message: '请选择所在城市', trigger: 'change' },
    {
      validator: (_rule: any, value: any, cb: any) => {
        const city = String(value || '').trim()
        if (!city) return cb(new Error('请选择所在城市'))
        if (!city.startsWith('CITY:')) return cb(new Error('城市编码不合法（需为 CITY:xxx）'))
        return cb()
      },
      trigger: 'change',
    },
  ],
  description: [
    { required: true, message: '请输入简介', trigger: 'blur' },
    {
      validator: (_rule: any, value: any, cb: any) => {
        const desc = String(value || '').trim()
        if (desc.length < 20) return cb(new Error('简介至少 20 个字'))
        return cb()
      },
      trigger: 'blur',
    },
  ],
  coverImageUrl: [{ required: true, message: '请上传封面图', trigger: 'blur' }],
}

const showcaseChecks = computed(() => {
  const nameOk = !!String(form.name || '').trim()
  const addrOk = !!String(form.address || '').trim()
  const phone = String(form.contactPhone || '').trim()
  const phoneOk = !!phone && /^[0-9 \-]{6,20}$/.test(phone)
  const coverOk = !!String(form.coverImageUrl || '').trim()
  const desc = String(form.description || '').trim()
  const descOk = desc.length >= 20
  const city = String(form.cityCode || '').trim()
  const cityOk = !!city && city.startsWith('CITY:')
  const total = 6
  const passed = [nameOk, addrOk, phoneOk, coverOk, descOk, cityOk].filter(Boolean).length
  return { nameOk, addrOk, phoneOk, coverOk, descOk, cityOk, passed, total }
})

const showcaseReady = computed(() => showcaseChecks.value.passed === showcaseChecks.value.total)
const currentVenue = computed(() => venues.value?.[0] || null)

const REVIEW_LABEL: Record<ReviewStatus, string> = {
  DRAFT: '草稿',
  SUBMITTED: '待审核',
  APPROVED: '已通过',
  REJECTED: '已驳回',
}

function reviewLabel(v: unknown): string {
  const raw = String(v || '').trim() as ReviewStatus | ''
  const key: ReviewStatus = (raw && raw in REVIEW_LABEL ? (raw as ReviewStatus) : 'DRAFT')
  return REVIEW_LABEL[key] ?? (raw || '-')
}

function reviewTagType(status: ReviewStatus | null | undefined): 'info' | 'warning' | 'success' | 'danger' {
  const s = (status || 'DRAFT') as ReviewStatus
  if (s === 'SUBMITTED') return 'warning'
  if (s === 'APPROVED') return 'success'
  if (s === 'REJECTED') return 'danger'
  return 'info'
}

function publishTagType(status: string | null | undefined): 'info' | 'warning' | 'success' {
  const s = String(status || '').toUpperCase()
  if (s === 'PUBLISHED') return 'success'
  if (s === 'OFFLINE') return 'warning'
  return 'info'
}

async function doUploadSingle(setter: (url: string) => void, raw: any) {
  const uid = String(raw?.uid || '')
  if (uid) {
    if (_uploadingUids.has(uid)) return
    _uploadingUids.add(uid)
  }
  const f = raw?.raw as File | undefined
  if (!f) return
  try {
    const url = await uploadImage(f)
    setter(url)
    ElMessage.success('已上传')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? e ?? '上传失败'))
  } finally {
    if (uid) _uploadingUids.delete(uid)
  }
}

function onLogoUploadChange(f: any) {
  void doUploadSingle((url) => (form.logoUrl = url), f)
}

function onCoverUploadChange(f: any) {
  void doUploadSingle((url) => (form.coverImageUrl = url), f)
}

async function doUploadMultiple(raw: any) {
  const uid = String(raw?.uid || '')
  if (uid) {
    if (_uploadingUids.has(uid)) return
    _uploadingUids.add(uid)
  }
  const f = raw?.raw as File | undefined
  if (!f) return
  try {
    const url = await uploadImage(f)
    const list = asArray(form.imageUrls)
    if (list.length >= 9) return ElMessage.warning('最多上传 9 张环境/服务图')
    list.push(url)
    form.imageUrls = list
    ElMessage.success('已上传')
  } catch (e: any) {
    ElMessage.error(String(e?.message ?? e ?? '上传失败'))
  } finally {
    if (uid) _uploadingUids.delete(uid)
  }
}

function removeGallery(url: string) {
  form.imageUrls = asArray(form.imageUrls).filter((x) => x !== url)
}

async function loadVenues() {
  loading.value = true
  try {
    const data = await apiRequest<{ items: VenueLite[]; total: number }>('/provider/venues')
    venues.value = data.items
    if (venues.value.length > 1) {
      ElMessage.warning('检测到多个场所（异常数据），已默认选择第一条作为当前场所')
    }
    if (venues.value[0]?.id) {
      currentId.value = venues.value[0].id
      await loadDetail()
    }
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadDetail() {
  if (!currentId.value) return
  loading.value = true
  try {
    const data = await apiRequest<VenueDetail>(`/provider/venues/${currentId.value}`)
    Object.assign(form, data)
    await loadVenueTagOptions()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? '加载详情失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!currentId.value) return
  try {
    // 保存允许草稿态：不强制拦截；但会尽量提前给出校验提示
    try {
      await formRef.value?.validate?.()
    } catch {
      // ignore
    }
    const updated = await apiRequest<VenueDetail>(`/provider/venues/${currentId.value}`, {
      method: 'PUT',
      body: {
        name: form.name,
        address: form.address,
        contactPhone: form.contactPhone,
        businessHours: form.businessHours,
        countryCode: form.countryCode,
        provinceCode: form.provinceCode,
        cityCode: form.cityCode,
        description: form.description,
        logoUrl: form.logoUrl,
        coverImageUrl: form.coverImageUrl,
        imageUrls: asArray(form.imageUrls),
        tags: asArray(form.tags),
      },
    })
    ElMessage.success('已保存')
    // 回显一致：使用后端返回的最新数据回填（确保落库结果与 UI 一致）
    Object.assign(form, updated)
    await loadVenues()
  } catch (e: any) {
    ElMessage.error(e?.message ?? e?.apiError?.message ?? '保存失败')
  }
}

async function submitShowcase() {
  if (!currentId.value) return
  try {
    await formRef.value?.validate?.()
  } catch {
    ElMessage.error('请先修正表单校验错误后再提交')
    return
  }
  if (!showcaseReady.value) {
    return ElMessage.warning(`资料未完成：已完成 ${showcaseChecks.value.passed}/${showcaseChecks.value.total} 项，请补齐必填项后再提交`)
  }
  try {
    // 关键：提交展示前先保存，避免“未保存改动被直接提交”的困惑
    await apiRequest<VenueDetail>(`/provider/venues/${currentId.value}`, {
      method: 'PUT',
      body: {
        name: form.name,
        address: form.address,
        contactPhone: form.contactPhone,
        businessHours: form.businessHours,
        countryCode: form.countryCode,
        provinceCode: form.provinceCode,
        cityCode: form.cityCode,
        description: form.description,
        logoUrl: form.logoUrl,
        coverImageUrl: form.coverImageUrl,
        imageUrls: asArray(form.imageUrls),
        tags: asArray(form.tags),
      },
    })
    await apiRequest(`/provider/venues/${currentId.value}/submit-showcase`, { method: 'POST' })
    ElMessage.success('已提交展示资料，等待平台审核')
    await loadDetail()
    await loadVenues()
  } catch (e: any) {
    ElMessage.error(e?.apiError?.message ?? e?.message ?? '提交失败')
  }
}

onMounted(async () => {
  await loadCities()
  await loadVenues()
})
</script>

<template>
  <div>
    <el-page-header content="场所信息" />

    <el-card style="margin-top: 12px" :loading="loading">
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <template #title>提交展示资料（v1 最小校验）</template>
        <div style="line-height: 1.7">
          <div>
            资料完成度：<b>{{ showcaseChecks.passed }}/{{ showcaseChecks.total }}</b>
            <span style="color: var(--lh-muted)">(提交展示前会校验：名称/地址/电话/封面/介绍≥20字/城市)</span>
          </div>
        </div>
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="场所">
          <el-tag type="info">{{ venues[0]?.name || '—' }}</el-tag>
          <el-tag v-if="currentVenue?.reviewStatus" style="margin-left: 8px" :type="reviewTagType(currentVenue?.reviewStatus)">
            审核：{{ reviewLabel(currentVenue.reviewStatus) }}
          </el-tag>
          <el-tag v-if="currentVenue?.publishStatus" style="margin-left: 8px" :type="publishTagType(currentVenue?.publishStatus)">
            发布：{{ currentVenue.publishStatus }}
          </el-tag>
          <el-button style="margin-left: 8px" @click="loadVenues">刷新</el-button>
          <el-button type="primary" style="margin-left: 8px" @click="save">保存</el-button>
          <el-button type="success" style="margin-left: 8px" :disabled="!showcaseReady" @click="submitShowcase">提交展示</el-button>
        </el-form-item>

        <el-form-item v-if="currentVenue?.reviewStatus === 'REJECTED'" label="驳回原因">
          <el-alert type="error" show-icon :closable="false" style="width: 720px">
            <div style="line-height: 1.7">
              <div>{{ currentVenue?.rejectReason || '—' }}</div>
              <div style="color: var(--lh-muted); margin-top: 4px">修改后请点击“提交展示”重新进入待审核。</div>
            </div>
          </el-alert>
        </el-form-item>

        <el-form-item v-if="currentVenue?.publishStatus === 'OFFLINE'" label="下线原因">
          <el-alert type="warning" show-icon :closable="false" style="width: 720px">
            <div style="line-height: 1.7">
              <div>{{ currentVenue?.offlineReason || '—' }}</div>
              <div style="color: var(--lh-muted); margin-top: 4px">修改资料后可重新“提交展示”进入待审核。</div>
            </div>
          </el-alert>
        </el-form-item>

        <el-form-item label="场所名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input v-model="form.address" placeholder="详细地址（门牌号等）" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contactPhone">
          <el-input v-model="form.contactPhone" placeholder="手机号或座机（仅数字/空格/短横线，长度 6~20）" />
        </el-form-item>
        <el-form-item label="营业时间">
          <el-input v-model="form.businessHours" placeholder="例如 09:00-18:00" />
        </el-form-item>

        <el-form-item label="所在城市" prop="cityCode">
          <el-select
            v-model="form.cityCode"
            filterable
            clearable
            :loading="citiesLoading"
            style="width: 360px"
            placeholder="选择城市（会保存为 CITY:<code>）"
          >
            <el-option v-for="c in cities" :key="c.code" :label="`${c.name}（${c.code}）`" :value="c.code" />
          </el-select>
          <span style="color: var(--lh-muted); margin-left: 8px">当前：{{ form.cityCode || '-' }}</span>
        </el-form-item>

        <el-form-item label="简介" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="至少 20 个字，建议包含：特色、环境、可提供的服务等" />
        </el-form-item>
        <el-form-item label="Logo（可选）">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
            <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="onLogoUploadChange">
              <el-button>上传 Logo</el-button>
            </el-upload>
            <el-input v-model="form.logoUrl" style="width: 520px" placeholder="或粘贴图片 URL" />
            <el-image v-if="form.logoUrl" :src="form.logoUrl" style="width: 44px; height: 44px; border-radius: 10px" fit="cover" />
          </div>
        </el-form-item>

        <el-form-item label="封面图（必填）" prop="coverImageUrl">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="image/*"
              :on-change="onCoverUploadChange"
            >
              <el-button type="primary">上传封面图</el-button>
            </el-upload>
            <el-input v-model="form.coverImageUrl" style="width: 520px" placeholder="或粘贴图片 URL" />
          </div>
          <div v-if="form.coverImageUrl" style="margin-top: 8px">
            <el-image :src="form.coverImageUrl" style="width: 220px; height: 120px; border-radius: 12px" fit="cover" />
          </div>
        </el-form-item>

        <el-form-item label="环境/服务图（最多9张）">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
            <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" multiple :on-change="doUploadMultiple">
              <el-button>上传图片</el-button>
            </el-upload>
            <span style="color: var(--lh-muted)">已上传 {{ (form.imageUrls?.length ?? 0) || 0 }} 张</span>
          </div>
          <div v-if="(form.imageUrls?.length ?? 0) > 0" style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap">
            <div v-for="u in form.imageUrls" :key="u" style="position: relative">
              <el-image :src="u" style="width: 120px; height: 80px; border-radius: 10px" fit="cover" />
              <el-button size="small" type="danger" style="position: absolute; right: 6px; top: 6px" @click="removeGallery(u)">删</el-button>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="标签（可选）">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            :loading="tagsLoading"
            style="width: 520px"
            placeholder="选择标签（由 Admin 维护）"
            @visible-change="(v: boolean) => v && loadVenueTagOptions()"
          >
            <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
          </el-select>
          <span style="color: var(--lh-muted); margin-left: 8px">建议不超过 10 个</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="save">保存</el-button>
          <el-button type="success" :disabled="!showcaseReady" @click="submitShowcase">提交展示</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

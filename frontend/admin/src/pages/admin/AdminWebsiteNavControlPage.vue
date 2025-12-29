<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiRequest } from '../../lib/api'
import { handleApiError } from '../../lib/error-handling'
import PageHeaderBar from '../../components/PageHeaderBar.vue'
import PageErrorState from '../../components/PageErrorState.vue'

type NavControl = {
  navItems: Record<
    'home' | 'business' | 'venues' | 'content' | 'about' | 'contact',
    {
      enabled: boolean
    }
  >
  version: string
}

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const loadErrorCode = ref('')
const loadErrorRequestId = ref('')
const router = useRouter()

const cfg = reactive({
  version: '0',
  navItems: {
    home: { enabled: true },
    business: { enabled: true },
    venues: { enabled: true },
    content: { enabled: true },
    about: { enabled: true },
    contact: { enabled: true },
  } as NavControl['navItems'],
})

const allEnabled = computed(() => Object.values(cfg.navItems).every((x) => !!x.enabled))

async function load() {
  loading.value = true
  try {
    const data = await apiRequest<NavControl>('/admin/website/nav-control')
    cfg.version = data.version || '0'
    cfg.navItems = data.navItems
    loadError.value = ''
    loadErrorCode.value = ''
    loadErrorRequestId.value = ''
  } catch (e: any) {
    const msg = e?.apiError?.message ?? '加载失败'
    loadError.value = msg
    loadErrorCode.value = e?.apiError?.code ?? ''
    loadErrorRequestId.value = e?.apiError?.requestId ?? ''
    handleApiError(e, { router, fallbackMessage: msg })
  } finally {
    loading.value = false
  }
}

function setAll(v: boolean) {
  for (const k of Object.keys(cfg.navItems) as (keyof NavControl['navItems'])[]) {
    cfg.navItems[k].enabled = v
  }
}

async function save() {
  saving.value = true
  try {
    await apiRequest<NavControl>('/admin/website/nav-control', {
      method: 'PUT',
      body: { navItems: cfg.navItems },
    })
    ElMessage.success('已保存')
    await load()
  } catch (e: any) {
    handleApiError(e, { router, fallbackMessage: '保存失败' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeaderBar title="官网管理：导航与入口控制" />

    <el-card style="margin-top: 12px" :loading="loading">
      <PageErrorState
        v-if="!loading && loadError"
        :message="loadError"
        :code="loadErrorCode"
        :requestId="loadErrorRequestId"
        @retry="load"
      />

      <div v-else>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px">
          <div style="display: flex; align-items: center; gap: 10px">
            <span style="font-size: 12px; color: rgba(0, 0, 0, 0.55)">version={{ cfg.version }}</span>
            <el-button size="small" @click="setAll(true)" :disabled="allEnabled">全部开启</el-button>
            <el-button size="small" @click="setAll(false)" :disabled="!allEnabled">全部关闭</el-button>
          </div>
          <div style="display: flex; gap: 8px">
            <el-button :disabled="loading" @click="load">刷新</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </div>
        </div>

        <el-form label-width="160px">
          <el-form-item label="首页（/）">
            <el-switch v-model="cfg.navItems.home.enabled" />
          </el-form-item>
          <el-form-item label="业务线（/business）">
            <el-switch v-model="cfg.navItems.business.enabled" />
          </el-form-item>
          <el-form-item label="场所/服务（/venues）">
            <el-switch v-model="cfg.navItems.venues.enabled" />
          </el-form-item>
          <el-form-item label="内容中心（/content）">
            <el-switch v-model="cfg.navItems.content.enabled" />
          </el-form-item>
          <el-form-item label="关于（/about）">
            <el-switch v-model="cfg.navItems.about.enabled" />
          </el-form-item>
          <el-form-item label="联系（/contact）">
            <el-switch v-model="cfg.navItems.contact.enabled" />
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>



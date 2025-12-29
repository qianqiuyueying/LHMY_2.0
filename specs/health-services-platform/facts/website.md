## 完成事实清单：企业官网（frontend/website）

> 口径：只写“事实”（已经存在的行为/代码结构），每条都给出**证据入口**（文件路径/接口路径/关键函数）。

### A) 工程与入口

- [x] 技术栈：Vue3 + TypeScript + Vite + Naive UI + `@vueuse/head`（SEO meta 管理）  
  - 证据：`frontend/website/package.json`、`frontend/website/src/main.ts`
- [x] 应用入口：注册 `createHead()` 与 router 后挂载  
  - 证据：`frontend/website/src/main.ts`

### B) 路由与 SEO（信息结构约束）

- [x] 路由结构（SiteLayout + 子路由）：首页/业务线/场所列表/场所详情/内容中心/内容详情/关于/联系/404  
  - 证据：`frontend/website/src/router/index.ts`
- [x] 路由 meta 自带 `title/description`（用于 SEO）  
  - 证据：`frontend/website/src/router/index.ts` 各路由 `meta`
- [x] SEO：根据路由 meta 更新 `title/description/canonical/robots`（失败兜底默认值）  
  - 证据：`frontend/website/src/lib/seo.ts` `useSeo()`

### C) API 客户端（官网读侧）

- [x] 官网 API 前缀读取 `VITE_API_BASE`，默认 `/api`；仅做 GET + JSON 解析  
  - 证据：`frontend/website/src/lib/api.ts` `apiBase()/apiGet()`
- [x] 统一响应体（官网侧假定）：`{success,data,error,requestId}`；失败时抛 `ApiError(code, requestId)`  
  - 证据：`frontend/website/src/lib/api.ts` `ApiResp`、`ApiError`

### D) SiteLayout（导航/导流/维护模式/页脚）

- [x] 顶部导航可动态开关（nav-control），未开放路由显示 NotOpenPage  
  - 证据：`frontend/website/src/layouts/SiteLayout.vue` `loadNavControl()/blockedByNav`
- [x] 维护模式（maintenance-mode）：开启后除 allowPaths 外全部显示 MaintenancePage  
  - 证据：`frontend/website/src/layouts/SiteLayout.vue` `loadMaintenanceMode()/maintenanceAllowPath`
- [x] 页脚配置读取：`GET /api/v1/website/footer/config`（官网侧路径为 `/v1/website/footer/config`）  
  - 证据：`frontend/website/src/layouts/SiteLayout.vue` `loadFooterConfig()`
- [x] 外部导流链接（进入小程序 / H5 购买）：`GET /api/v1/website/external-links`  
  - 证据：`frontend/website/src/lib/websiteExternalLinks.ts` + `SiteLayout.vue` `loadExternalLinks()/openMiniProgram/openH5Buy`
- [x] 窄屏 header：在更宽的阈值提前切换到移动端菜单，避免 header 换行  
  - 证据：`frontend/website/src/layouts/SiteLayout.vue`（`@media (max-width: 1100px)`）

### E) 页面与接口依赖（官网侧调用点）

#### E1) 首页 `HomePage.vue`

- [x] 首页推荐场所：`GET /api/v1/website/home/recommended-venues`  
  - 证据：`frontend/website/src/pages/HomePage.vue` `loadVenues()`
- [x] 内容中心入口（列表）：`GET /api/v1/mini-program/cms/contents`（用于官网展示 CMS 已发布内容）  
  - 证据：`frontend/website/src/pages/HomePage.vue` `loadContents()`

#### E2) 场所列表 `VenuesPage.vue`

- [x] 地区城市：`GET /api/v1/regions/cities`（官网侧路径为 `/v1/regions/cities`）  
  - 证据：`frontend/website/src/pages/VenuesPage.vue` `loadCities()`
- [x] 服务类别：`GET /api/v1/taxonomy-nodes?type=VENUE`（官网侧路径为 `/v1/taxonomy-nodes`）  
  - 证据：`frontend/website/src/pages/VenuesPage.vue` `loadTaxonomy()`
- [x] 场所列表查询：`GET /api/v1/venues`（官网侧路径为 `/v1/venues`）  
  - 证据：`frontend/website/src/pages/VenuesPage.vue` `search()`

#### E3) 场所详情 `VenueDetailPage.vue`

- [x] 场所详情读取：`GET /api/v1/venues/{id}`（官网侧路径为 `/v1/venues/{id}`）  
  - 证据：`frontend/website/src/pages/VenueDetailPage.vue` `load()`

#### E4) 联系我们 `ContactPage.vue`

- [x] 联系方式复用页脚配置：`GET /api/v1/website/footer/config`  
  - 证据：`frontend/website/src/pages/ContactPage.vue` `load()`

### F) 网站配置缓存（事实）

- [x] external-links/nav-control/maintenance-mode 均有“内存缓存 + inflight 复用”逻辑  
  - 证据：`frontend/website/src/lib/websiteExternalLinks.ts`、`websiteNavControl.ts`、`websiteMaintenanceMode.ts`



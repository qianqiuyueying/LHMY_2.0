# CMS v2：小程序内容源（INFO_PAGE/AGG_PAGE 绑定入口）与多端发布控制（WEB/MINI_PROGRAM）

> 状态：**已确认（v2-P0：内容源与投放体验）**
>
> 规格来源（现状复用）：
> - `backend/app/api/v1/cms.py`：已存在 CMS 后端（admin 写侧 + website/mini-program 读侧），并支持 **按端发布**（`WEB` 与 `MINI_PROGRAM` 状态分离）
> - `specs/health-services-platform/facts/website.md`：官网已接入内容中心/详情
> - `frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`：信息页支持 `cmsContent` block（从 CMS 选择已发布内容）
> - `frontend/mini-program/pages/info/info.js`：信息页运行时按 `contentId` 拉取 CMS 已发布内容并渲染（rich-text）
> - `frontend/mini-program/pages/aggregate/aggregate.js`：聚合页支持 NAV 模式（TABS_LIST / SIDEBAR_GRID），条目跳转到 INFO_PAGE/AGG_PAGE/ROUTE/WEBVIEW 等

## 1. 背景与问题

- CMS 最初用于官网内容中心，但小程序也需要“内容中心/文章阅读”能力（公告/资讯/科普/案例等）。
- 当前仓库：
  - 后端已具备小程序读侧 CMS 接口（按 `mp_status=PUBLISHED` 返回）
  - 官网已有内容中心/详情页
  - 小程序缺少“内容中心列表/内容详情”的原生页面与入口（只能通过信息页间接引用）

## 2. 目标（P0）

- 小程序将 CMS 作为“内容源”，通过运营配置的 **Banner/快捷入口/聚合页条目** 进入内容阅读页（INFO_PAGE），形成可用闭环。
- 支持 **多端发布但可单独控制**：
  - 同一条内容允许：
    - 只发布到官网（WEB）
    - 只发布到小程序（MINI_PROGRAM）
    - 同时发布到两端
  - 不强制“必须都发/都不发”。
- 资源（图片）暂时使用 **本地落盘静态 URL**（`/static/uploads/...`），后续可升级外部图床/OSS，但不作为本期前置条件。

## 3. 非目标（本期不做）

- 不引入复杂的内容审核流/多级权限（除现有 admin 写侧门禁外）。
- 不做富媒体资源库/附件管理（PDF/视频等）。
- 不做阅读量/点赞/评论等互动能力（除非另行立项）。

## 4. 数据与发布口径（复用现有后端）

### 4.1 内容实体（现有字段，概念口径）

- `CmsChannel`：栏目（name/sort/status）
- `CmsContent`：
  - `channelId`
  - `title`
  - `coverImageUrl`（可选）
  - `summary`（可选）
  - `contentMd`（可选，写侧）
  - `contentHtml`（读侧渲染用；当传入 `contentMd` 时由后端转换并安全清洗）
  - `effectiveFrom/effectiveUntil`（可选：有效期控制）
  - 发布状态按端分离：
    - 官网：`status + publishedAt`
    - 小程序：`mpStatus + mpPublishedAt`

### 4.2 小程序读侧过滤规则（现有实现口径）

- 列表与详情仅返回：
  - `mpStatus = PUBLISHED`
  - 且当前时间在有效期内（`effectiveFrom/effectiveUntil`）

## 5. API 契约（复用现有接口）

### 5.1 小程序读侧（PUBLIC）

- `GET /api/v1/mini-program/cms/channels`
  - 返回：仅 `status=ENABLED` 的栏目，按 `sort asc, createdAt asc`
- `GET /api/v1/mini-program/cms/contents`
  - Query：`channelId?`、`keyword?`、`page`、`pageSize`
  - 返回：`{ items[{id, channelId, title, coverImageUrl, summary, publishedAt}], page, pageSize, total }`
- `GET /api/v1/mini-program/cms/contents/{id}`
  - 返回：`{ id, channelId, title, coverImageUrl, summary, contentHtml, publishedAt }`

### 5.2 Admin 写侧（需要 ADMIN）

复用现有 `Admin CMS 内容管理`：
- 栏目：`/api/v1/admin/cms/channels`
- 内容：`/api/v1/admin/cms/contents`
- 发布/下线：
  - `POST /api/v1/admin/cms/contents/{id}/publish?scope=WEB|MINI_PROGRAM`
  - `POST /api/v1/admin/cms/contents/{id}/offline?scope=WEB|MINI_PROGRAM`

## 6. 小程序功能范围（本期交付）

### 6.1 不新增“内容中心”独立页面（约束）

- 小程序端**不新增**独立的“内容中心列表/详情”页面入口。
- 内容入口通过运营配置体系完成：
  - Banner / 快捷入口 / 聚合页条目（`jumpType=INFO_PAGE`）
  - 进入 INFO_PAGE 后，通过 block 渲染内容（Markdown 或引用 CMS 内容）。

### 6.2 小程序内容阅读闭环（工作流口径）

- Step 1：在 Admin CMS 创建内容，并发布到 `scope=MINI_PROGRAM`（`mpStatus=PUBLISHED`）
- Step 2：在 Admin 小程序配置中心创建/编辑 **信息页（INFO_PAGE）**：
  - 选择 block 类型 `cmsContent`，从“已发布到小程序”的 CMS 内容中选择 `contentId`
- Step 3：在 Banner/快捷入口/聚合页条目中配置跳转：
  - `jumpType=INFO_PAGE`
  - `targetId=<pageId>`

### 6.3 聚合页（AGG_PAGE）能力边界

- 本期默认使用聚合页的 NAV 模式（TABS_LIST / SIDEBAR_GRID）作为“入口导航/目录页”，每个条目跳转到 INFO_PAGE（运营手工维护）。
- **不强制**本期实现“自动从 CMS 栏目拉取列表并生成条目”（见 9. 未决问题）。

### 6.4 Admin 写侧/投放体验（本期交付，P0）

> 说明：小程序内容中心不新增独立页面，因此“投放体验”本期优先级更高：
> 运营需要能够快速把“文章/内容”发布到小程序，并绑定到 INFO_PAGE，再由入口（Banner/快捷入口/聚合页）跳转。

#### 6.4.1 Admin CMS：正文支持“上传图片并插入 Markdown”

- **目标**：在 `Admin - 官网内容（CMS） - 内容编辑` 中提供“上传图片→自动插入 Markdown 图片语法”的快捷能力，避免运营手工用工具上传再复制 URL。
- **约束（必须）**
  - 不新增后端接口：复用 `POST /api/v1/uploads/images`（返回 `/static/uploads/...`）
  - 插入语法：`![alt](url)`（默认 alt 可为“图片”或文件名）
  - 仅作用于 `contentMd`（Markdown 模式）；若当前内容处于“历史 HTML 模式”，需提示运营先切换到 Markdown。

#### 6.4.1.1 Admin CMS：Markdown 预览面板（本地预览）

- **目标**：在内容编辑弹窗中提供“预览”面板，运营可在保存前直观看到 Markdown 渲染效果（含图片、标题、列表等）。
- **约束（必须）**
  - 预览为**本地渲染**（不新增后端接口）；仅作为编辑辅助。
  - 安全：预览不得执行任意 HTML/脚本；链接/图片 URL 必须过滤不安全协议（如 `javascript:`）。
  - 预览差异提示：需提示“后台会在保存时将 Markdown 转为安全 HTML，最终渲染以保存结果为准”。

#### 6.4.2 Admin 小程序配置中心：CMS 内容选择器增强

- **目标**：在 INFO_PAGE 的 `cmsContent` block 选择器中，支持：
  - 按栏目筛选（`channelId`）
  - 关键字搜索（标题/摘要，`keyword`）
- **约束（必须）**
  - 只展示“已发布到小程序”的 CMS 内容（等价于：scope=MINI_PROGRAM + status=PUBLISHED 的口径）
  - 不改现有 `cmsContent` block 结构（仍为 `{ type:'cmsContent', contentId, title? }`）

#### 6.4.3 Admin CMS：内容列表支持“投放端视图”分离（WEB / MINI_PROGRAM）

- **目标**：在 CMS 内容列表页提供“投放端”筛选：
  - 全部（同时显示官网发布状态 + 小程序发布状态）
  - 官网（只看/只操作 WEB 发布状态）
  - 小程序（只看/只操作 MINI_PROGRAM 发布状态）
- **约束（必须）**
  - 不新增后端接口：复用 `GET /api/v1/admin/cms/contents?scope=...&status=...`
  - 当 scope=MINI_PROGRAM 时，列表的 status 筛选作用于 `mpStatus`（后端已支持该语义）

#### 6.4.4 Admin CMS：内容中心 / 官网投放 / 小程序投放（三入口、强分工）

- **目标**：把“内容生产（编辑/存储）”与“投放（发布/下线/配置）”彻底拆开，降低运营误操作与认知负担（平台未上线，可大胆调整）。
- **入口与职责（必须）**
  - **内容中心（CMS）**：只做“编辑/生产/存储到数据库”
    - 允许：新增内容、编辑正文（Markdown + 图片上传 + 预览）、保存草稿
    - 禁止：发布/下线（WEB/MINI_PROGRAM）
    - 栏目：不在内容中心管理/选择（栏目仅用于官网投放）
  - **官网投放（CMS）**：相当于“投放控制台”
    - 包含：栏目管理（新增/编辑/启停/排序）
    - 内容列表：仅 WEB 口径（scope=WEB），支持分配栏目、发布到官网、官网下线
    - 禁止：正文编辑（提供“去内容中心编辑”跳转）
  - **小程序投放（CMS）**：仅小程序口径
    - 内容列表：仅 MINI_PROGRAM 口径（scope=MINI_PROGRAM），支持发布到小程序、小程序下线
    - 禁止：正文编辑（提供“去内容中心编辑”跳转）
- **后端约束（必须）**
  - 内容允许不挂栏目（`channelId` 可为空）；但发布到官网（scope=WEB）必须先分配栏目。
- **小程序配置中心约束（本期决定）**
  - INFO_PAGE 不再支持手写 Markdown block；仅允许 `cmsContent` 引用内容中心产出的 CMS 内容。

## 7. 图片与资源（本期口径）

- 运营在 CMS 正文使用 Markdown 图片语法：`![alt](url)`
- 图片 URL 暂时来自：
  - `POST /api/v1/uploads/images`（返回 `/static/uploads/...`）
  - 或运营粘贴外部 https URL（如临时图床）
- 安全：后端 Markdown→HTML 会做 bleach 清洗；允许 `img src`（http/https/相对路径）。

## 8. 验收（DoD，最小）

- Admin 侧：同一条 CMS 内容可分别发布到 `WEB` 与 `MINI_PROGRAM`，互不影响。
- 小程序：
  - INFO_PAGE 引用 `cmsContent` 时，运行时按 `contentId` 拉取 `GET /api/v1/mini-program/cms/contents/{id}` 并渲染 `contentHtml`
  - 未发布/已下线/超出有效期：应表现为 NOT_FOUND 或“内容暂不可用”（以端侧兜底为准）
  - 图片可展示（基于 `contentHtml` 中 `<img src>` + `/static/uploads/...`）
- 回滚：不影响既有 Banner/快捷入口/聚合页配置结构与跳转；不影响 INFO_PAGE 纯 Markdown 模式。

## 9. 未决问题（需要你确认）

1) 聚合页自动内容列表：
   - 本期不做（沿用既有 block 与手工维护条目方式）。
2) 转发/分享：
   - 本期默认依赖微信右上角菜单的系统分享能力，不做自定义分享卡片逻辑；如后续要做需单独立项（涉及标题/封面/路径参数策略）。



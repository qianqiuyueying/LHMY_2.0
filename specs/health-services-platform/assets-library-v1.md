## 资产库 v1（图片）：统一管理、去重复用、为 OSS 预留

> 状态：草案（已确认方向：实现）

### 背景
- 当前图片上传接口 `POST /api/v1/uploads/images`：每次上传都会生成新文件名并落盘。
- 问题：
  - 同一张图片反复上传会造成磁盘浪费
  - 缺少“统一管理/检索/复用/清理”能力
  - 未来切 OSS/图床可能牵动多处逻辑

### 目标（P0）
- **资产库（图片）**：可列表/检索/复用
- **上传去重**：同文件（按 sha256）重复上传返回同一 URL，不重复落盘
- **存储抽象**：后端封装 StorageProvider（LOCAL 先落盘，未来切 OSS 不改业务 API）

### 非目标（本期不做）
- 不做复杂目录/标签/权限模型
- 不做富媒体（视频/PDF）与转码

### 数据模型（v1）
表：`assets`
- `id` (uuid)
- `kind` = `IMAGE`
- `sha256`（唯一索引）
- `sizeBytes`
- `mime`
- `ext`
- `storage` = `LOCAL`（预留 OSS）
- `storageKey`（本地可用相对路径，如 `uploads/2025/12/xxx.jpg`）
- `url`（对外可访问 URL，如 `/static/uploads/2025/12/xxx.jpg` 或未来 `https://cdn/...`）
- `originalFilename`（可选）
- `createdAt/createdByActorType/createdByActorId`

### API（v1）
#### 上传（复用现有）
- `POST /api/v1/uploads/images`
  - 输入：multipart file
  - 输出：`{ url }`
  - 语义增强：
    - 服务端计算 sha256，若已存在资产：直接返回已存在 `url`
    - 否则：存储到 LOCAL 并创建 `assets` 记录

#### 管理（ADMIN）
- `GET /api/v1/admin/assets`
  - query：`kind=IMAGE`、`keyword?`、`page/pageSize`
  - 返回：`{ items[{id,url,sha256,sizeBytes,mime,createdAt,originalFilename?}], page,pageSize,total }`

### 前端接入（admin）
- 内容中心（CMS）：
  - 封面：支持“上传封面/从资产库选择”
  - 正文：支持“上传插图/从资产库选择并插入 Markdown”

### 验收（DoD）
- 同一张图片重复上传：返回相同 URL（磁盘不增长、资产不重复）
- admin 可从资产库选择图片用于封面/正文
- 切换 OSS：只需新增/替换 StorageProvider 实现，不改前端、不改 CMS 数据结构



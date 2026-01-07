# 全站时间与时区契约（你已拍板）

> 目标：消除“服务器/容器时区差异”导致的时间偏移；同时避免把“业务日期/周期语义”误当成时间戳处理。

## 1. 核心结论（必须遵守）

### 1.1 Timestamp（事件时间 / 发生时刻）

适用字段：
- `createdAt`
- `updatedAt`
- 其它明确为事件时间的 `*At` 字段（例如 `paidAt/canceledAt/deliveredAt/...`）

规则：
- **存储（DB）**：统一使用 **UTC** 存储（若 DB 字段为无时区类型，如 MySQL `DATETIME`，约定其数值语义为 UTC）
- **API 出参**：统一输出为 **UTC 的 ISO 8601 字符串，必须带 `Z`**  
  例：`2026-01-07T12:34:56Z`
- **前端展示**：
  - Admin 端：**固定展示为北京时间（UTC+8）**
  - H5 / 小程序 / 官网（用户端）：**按用户设备本地时区展示**

### 1.2 Business Date / Period（业务自然日 / 周期语义）

适用字段（示例）：
- `validUntil`（通常是“日期截止”，不代表某个精确时刻）
- `cycle`（`YYYY-MM`）
- `dateFrom/dateTo`（`YYYY-MM-DD`，用于筛选的业务自然日边界）

规则：
- 这些字段**不是 datetime/timestamp**，不应被统一“UTC+Z”策略强制转换
- 若需要与 DB 的 timestamp 字段比较（例如用 `dateFrom/dateTo` 过滤 `created_at`），应当：
  - **先在规格中明确该接口的“自然日口径时区”**（例如 Admin 报表类按北京时间自然日）
  - 再在实现中将“自然日起止边界”换算为 UTC 范围进行查询（这是实现细节，不改变字段语义）

## 2. 样板域：权益（用户侧发放/使用链路）

### 2.1 字段语义（必须清晰）
- **业务日期（YYYY-MM-DD，不做 UTC 转换）**
  - `validFrom`：生效日期（含当日）
  - `validUntil`：到期日期（含当日）
- **事件时间戳（UTC ISO8601 + Z）**
  - `createdAt`：权益发放/生成时间
  - `activatedAt`：**首次核销成功时间**（作为“首次激活/首次使用”事件的统一口径；无核销记录则为 null）
  - `usedAt`：权益状态变为 `USED` 时的时间（实现上取最后一次核销成功时间；未 `USED` 则为 null）

### 2.2 有效期校验（业务日期口径）
- 核销/可用性判断时，`validFrom/validUntil` 按 **北京时间（UTC+8）自然日**解释：
  - today（北京） < validFrom → 未生效
  - today（北京） > validUntil → 已过期

## 3. CMS（内容中心/官网/小程序投放）

### 3.1 字段语义
- **事件时间戳（UTC ISO8601 + Z）**
  - `publishedAt`（官网发布时刻）
  - `mpPublishedAt`（小程序发布时刻）
  - `createdAt/updatedAt`
  - `effectiveFrom/effectiveUntil`（生效窗口，用于读侧过滤）

### 3.2 展示口径
- Admin：按北京时间展示上述 timestamp
- Website/H5/小程序：按用户设备本地时区展示上述 timestamp

### 3.3 入参解析（写侧）
- `effectiveFrom/effectiveUntil` 支持：
  - ISO8601（可带 `Z` 或 `+08:00` 等 offset），后端统一换算并以 **UTC naive datetime** 存储
  - `YYYY-MM-DD`：
    - `effectiveFrom` 解释为 **北京时间当日 00:00:00**
    - `effectiveUntil` 解释为 **北京时间当日 23:59:59**

### 1.3 混合语义字段（禁止模糊）

若某字段既可能被当作“日期”又可能被当作“时间戳”，必须二选一：
- **重命名**（推荐）：例如 `validUntilDate` vs `validUntilAt`
- 或在对应 specs 中**明确语义**（字段类型、格式、时区口径、展示规则），禁止“靠猜”



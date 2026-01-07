# 代码结构说明

> **说明**：这个文档帮助你快速了解项目结构，知道代码在哪里，怎么找到需要的文件。

## 1. 后端目录结构

### 1.1 整体结构

```
backend/
├── app/                    # 主应用代码
│   ├── main.py            # 应用入口（启动、中间件配置）
│   ├── api/               # API 路由
│   ├── models/            # 数据库模型（ORM）
│   ├── services/          # 业务逻辑层
│   ├── middleware/        # 中间件（鉴权、日志等）
│   ├── utils/             # 工具函数
│   ├── tasks/             # 异步任务（Celery）
│   └── static/            # 静态文件
├── tests/                 # 测试代码
├── alembic/               # 数据库迁移
└── scripts/               # 脚本工具
```

### 1.2 核心目录说明

#### `backend/app/main.py` - 应用入口

**作用**：FastAPI 应用的启动入口，配置中间件、路由、静态文件等。

**关键内容**：
- 应用初始化
- 中间件注册（CORS、日志、鉴权等）
- 路由注册（`/api/v1`）
- 生产环境配置检查

**什么时候看**：
- 需要了解应用如何启动
- 需要添加全局中间件
- 需要修改 CORS 配置

#### `backend/app/api/` - API 路由层

**作用**：定义所有的 HTTP 接口。

**结构**：
```
api/
├── router.py              # 路由聚合（所有路由在这里注册）
└── v1/                    # v1 版本的 API
    ├── router.py          # v1 路由聚合
    ├── auth.py            # 用户认证相关
    ├── admin_*.py         # 管理后台相关接口
    ├── dealer_*.py         # 经销商相关接口
    ├── provider_*.py      # 服务提供方相关接口
    ├── orders.py          # 订单相关
    ├── bookings.py        # 预约相关
    ├── entitlements.py    # 权益相关
    ├── venues.py          # 场所相关
    └── ...                # 其他业务接口
```

**命名规则**：
- `admin_*`：管理后台接口（需要管理员权限）
- `dealer_*`：经销商接口（需要经销商权限）
- `provider_*`：服务提供方接口（需要提供方权限）
- 其他：通用接口（用户、小程序等）

**查找接口的方法**：
1. 看 URL 路径，比如 `/api/v1/admin/users` → `admin_users.py`
2. 看 `router.py` 中的路由注册
3. 搜索关键词（比如"用户"→ `users.py` 或 `admin_users.py`）

**关键文件**：
- `api/v1/router.py`：所有 v1 路由的聚合点，新接口在这里注册

#### `backend/app/models/` - 数据库模型

**作用**：定义数据库表结构和 ORM 模型。

**文件说明**：
- `base.py`：基础模型类（所有模型继承这个）
- `user.py`：用户模型
- `order.py`：订单模型
- `booking.py`：预约模型
- `venue.py`：场所模型
- `entitlement.py`：权益模型
- `product.py`：商品模型
- `dealer.py`：经销商模型
- `provider.py`：服务提供方模型
- `enums.py`：枚举类型定义
- ...（其他业务模型）

**查找模型的方法**：
- 看文件名，通常和业务实体对应
- 搜索表名或字段名

**注意事项**：
- 修改模型后需要生成迁移：`uv run alembic revision --autogenerate -m "描述"`
- 应用迁移：`uv run alembic upgrade head`

#### `backend/app/services/` - 业务逻辑层

**作用**：实现核心业务逻辑，API 层调用这里的方法。

**文件说明**：
- `rbac.py`：权限控制逻辑
- `order_rules.py`：订单业务规则
- `booking_rules.py`：预约业务规则
- `entitlement_*.py`：权益相关业务逻辑
- `pricing.py`：价格计算
- `payment_callbacks.py`：支付回调处理
- `idempotency.py`：幂等性处理
- `user_identity_service.py`：用户身份服务
- ...（其他业务服务）

**命名规则**：
- `*_rules.py`：业务规则（验证、状态转换等）
- `*_state_machine.py`：状态机（订单状态、权益状态等）
- `*_service.py`：服务类（复杂业务逻辑）

**使用方式**：
- API 层调用 services 中的函数
- Services 调用 models 操作数据库
- Services 之间可以互相调用

#### `backend/app/middleware/` - 中间件

**作用**：处理请求/响应的通用逻辑。

**文件说明**：
- `rbac_context.py`：权限上下文（解析 token，设置用户信息）
- `request_id.py`：请求 ID（每个请求生成唯一 ID）
- `request_logger.py`：请求日志（记录请求和响应）
- `audit_log.py`：审计日志（记录重要操作）
- `exceptions.py`：异常处理（统一错误响应格式）

**什么时候修改**：
- 需要修改鉴权逻辑
- 需要修改日志格式
- 需要添加新的全局处理逻辑

#### `backend/app/utils/` - 工具函数

**作用**：通用工具函数，不涉及业务逻辑。

**文件说明**：
- `settings.py`：配置管理（从环境变量读取配置）
- `db.py`：数据库连接和会话管理
- `jwt_*.py`：JWT token 生成和解析（不同角色的 token）
- `response.py`：统一响应格式
- `logging.py`：日志配置
- `redis_client.py`：Redis 客户端
- `datetime_iso.py`：日期时间工具

**使用方式**：
- 在 API、services、models 中导入使用
- 通常是纯函数，不依赖业务上下文

#### `backend/app/tasks/` - 异步任务

**作用**：Celery 异步任务（耗时操作、定时任务等）。

**文件说明**：
- `inventory.py`：库存相关任务

**使用方式**：
- 在 services 中调用：`from app.tasks.inventory import some_task; some_task.delay(...)`

### 1.3 如何找到代码

**场景 1：我要改一个接口**
1. 看接口路径，比如 `/api/v1/admin/users`
2. 找到 `backend/app/api/v1/admin_users.py`
3. 看接口实现，找到调用的 service
4. 修改 service 或 model

**场景 2：我要改数据库表结构**
1. 找到对应的 model，比如 `backend/app/models/user.py`
2. 修改模型
3. 生成迁移：`uv run alembic revision --autogenerate -m "描述"`
4. 应用迁移：`uv run alembic upgrade head`

**场景 3：我要加一个业务规则**
1. 找到相关的 service 文件，比如 `backend/app/services/order_rules.py`
2. 添加新的规则函数
3. 在 API 或 service 中调用

**场景 4：我要看权限是怎么控制的**
1. 看 `backend/app/middleware/rbac_context.py`（权限上下文）
2. 看 `backend/app/services/rbac.py`（权限检查逻辑）
3. 看 API 文件中的 `require_admin_context` 等装饰器

## 2. 前端目录结构

### 2.1 整体结构

```
frontend/
├── admin/          # 管理后台（Vue3 + Element Plus）
├── h5/             # H5 页面（Vue3 + Vant4）
├── website/        # 企业官网（Vue3 + Naive UI）
├── mini-program/   # 微信小程序（原生）
└── shared/         # 共享代码（TypeScript，Web 三端共用）
```

### 2.2 Admin 管理后台 (`frontend/admin/`)

**技术栈**：Vue3 + TypeScript + Element Plus + Vite

**目录结构**：
```
admin/
├── src/
│   ├── main.ts              # 应用入口
│   ├── App.vue              # 根组件
│   ├── router/
│   │   └── index.ts        # 路由配置
│   ├── layouts/
│   │   └── AppLayout.vue    # 布局组件
│   ├── pages/               # 页面组件
│   │   ├── LoginPage.vue   # 登录页
│   │   ├── admin/          # 管理员页面
│   │   ├── dealer/         # 经销商页面
│   │   └── provider/       # 服务提供方页面
│   ├── components/          # 通用组件
│   │   ├── PageHeaderBar.vue
│   │   ├── PageEmptyState.vue
│   │   └── PageErrorState.vue
│   ├── lib/                # 工具库
│   │   ├── api.ts          # API 请求封装
│   │   ├── auth.ts         # 认证相关
│   │   ├── error-handling.ts # 错误处理
│   │   ├── pagination.ts   # 分页工具
│   │   └── theme.ts        # 主题配置
│   └── assets/             # 静态资源
├── tests/
│   └── e2e/                # E2E 测试
└── vite.config.ts         # Vite 配置
```

**关键文件**：
- `src/router/index.ts`：路由配置，包含权限控制
- `src/lib/api.ts`：API 请求封装（调用后端接口）
- `src/lib/auth.ts`：认证相关（登录、token 管理）
- `src/pages/admin/`：管理员功能页面
- `src/pages/dealer/`：经销商功能页面
- `src/pages/provider/`：服务提供方功能页面

**查找页面**：
- 看路由路径，比如 `/admin/users` → `src/pages/admin/UsersPage.vue`
- 看 `router/index.ts` 中的路由定义

### 2.3 H5 (`frontend/h5/`)

**技术栈**：Vue3 + TypeScript + Vant4 + Vite

**目录结构**：
```
h5/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── pages/
│   │   ├── LandingPage.vue    # 落地页
│   │   ├── BuyPage.vue        # 购买页
│   │   └── PayResultPage.vue  # 支付结果页
│   └── lib/
│       ├── api.ts            # API 请求
│       └── dealer.ts         # 经销商相关
```

**特点**：
- 主要用于服务包购买流程
- 通过经销商链接进入
- 页面较少，功能聚焦

### 2.4 Website 企业官网 (`frontend/website/`)

**技术栈**：Vue3 + TypeScript + Naive UI + Vite

**目录结构**：
```
website/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── pages/               # 页面组件
│   ├── components/          # 通用组件
│   ├── layouts/            # 布局组件
│   └── lib/                # 工具库
```

**特点**：
- 企业官网展示
- 主要是只读内容
- SEO 友好

### 2.5 Mini-Program 小程序 (`frontend/mini-program/`)

**技术栈**：微信小程序原生开发

**目录结构**：
```
mini-program/
├── app.js                   # 小程序入口
├── app.json                 # 小程序配置
├── app.wxss                 # 全局样式
├── pages/                   # 页面
│   ├── index/              # 首页
│   ├── mall/               # 商城
│   ├── booking/            # 预约
│   ├── entitlement/        # 权益
│   ├── order/              # 订单
│   └── profile/            # 个人中心
├── utils/                   # 工具函数
│   ├── api.js              # API 请求
│   └── config.js           # 配置
└── custom-tab-bar/          # 自定义 tabBar
```

**特点**：
- 微信小程序原生开发
- 不依赖 shared 目录（有自己的工具函数）
- 每个页面包含 4 个文件：`.js`、`.json`、`.wxml`、`.wxss`

**查找页面**：
- 看 `app.json` 中的页面路径配置
- 页面目录名通常对应功能

### 2.6 如何找到前端代码

**场景 1：我要改管理后台的某个页面**
1. 看路由路径，比如 `/admin/users`
2. 在 `frontend/admin/src/router/index.ts` 中找到路由定义
3. 找到对应的页面组件，比如 `src/pages/admin/UsersPage.vue`
4. 修改页面组件

**场景 2：我要改 API 请求**
1. 找到对应的 `lib/api.ts` 文件
2. 看 API 函数定义
3. 修改请求参数或处理逻辑

**场景 3：我要加一个通用组件**
1. 在 `src/components/` 下创建新组件
2. 在需要的页面中导入使用

**场景 4：我要改路由或权限**
1. 修改 `src/router/index.ts`
2. 路由守卫逻辑也在里面

## 3. 共享代码说明 (`frontend/shared/`)

### 3.1 作用

`frontend/shared/` 目录包含 Web 三端（admin、h5、website）共用的纯逻辑代码。

**注意**：小程序不使用这个目录，因为它有自己的工具函数。

### 3.2 目录结构

```
shared/
├── http/                    # HTTP 请求相关
│   ├── base.ts             # 基础配置（base URL 等）
│   ├── envelope.ts          # 响应体解析（统一响应格式）
│   ├── idempotency.ts       # 幂等性 key 生成
│   ├── json.ts              # JSON 处理
│   └── query.ts             # Query 参数处理
├── auth/                    # 认证相关
│   └── actor.ts            # 用户角色类型定义
└── storage/                 # 存储相关
    └── localStorage.ts     # localStorage 封装
```

### 3.3 使用方式

**在 admin/h5/website 中使用**：

```typescript
// 导入共享代码
import { normalizeBaseUrl } from '@shared/http/base'
import { Actor } from '@shared/auth/actor'
import { safeGetItem, safeSetItem } from '@shared/storage/localStorage'
```

**配置别名**：
- 在 `vite.config.ts` 中配置了 `@shared` 别名
- 指向 `frontend/shared` 目录

### 3.4 什么时候用共享代码

**适合放在 shared**：
- HTTP 请求封装（统一响应格式处理）
- 工具函数（不依赖 UI 框架）
- 类型定义（多个端共用）
- 存储封装（localStorage 安全封装）

**不适合放在 shared**：
- UI 组件（每个端用的 UI 库不同）
- 业务逻辑（各端业务不同）
- 路由配置（各端路由不同）

### 3.5 修改共享代码的注意事项

- **向后兼容**：修改时要考虑不影响现有使用
- **测试**：修改后要在三个端都测试一下
- **文档**：如果添加新功能，最好加注释说明

## 4. 关键文件索引

### 4.1 后端关键文件

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `backend/app/main.py` | 应用入口、中间件配置 | 启动问题、添加中间件 |
| `backend/app/api/v1/router.py` | 路由聚合 | 查找接口、添加新接口 |
| `backend/app/utils/settings.py` | 配置管理 | 查看/修改配置项 |
| `backend/app/utils/db.py` | 数据库连接 | 数据库相关问题 |
| `backend/app/middleware/rbac_context.py` | 权限上下文 | 权限相关问题 |
| `backend/app/services/rbac.py` | 权限检查 | 权限逻辑问题 |
| `backend/app/models/base.py` | 基础模型 | 了解模型结构 |
| `backend/app/models/enums.py` | 枚举定义 | 查找枚举值 |

### 4.2 前端关键文件

#### Admin

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `frontend/admin/src/router/index.ts` | 路由配置 | 路由、权限问题 |
| `frontend/admin/src/lib/api.ts` | API 请求 | API 调用问题 |
| `frontend/admin/src/lib/auth.ts` | 认证逻辑 | 登录、token 问题 |
| `frontend/admin/src/App.vue` | 根组件 | 全局逻辑 |
| `frontend/admin/src/layouts/AppLayout.vue` | 布局组件 | 布局问题 |

#### H5

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `frontend/h5/src/lib/api.ts` | API 请求 | API 调用问题 |
| `frontend/h5/src/pages/BuyPage.vue` | 购买页 | 购买流程问题 |

#### Website

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `frontend/website/src/lib/api.ts` | API 请求 | API 调用问题 |

#### Mini-Program

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `frontend/mini-program/app.js` | 小程序入口 | 全局逻辑 |
| `frontend/mini-program/app.json` | 小程序配置 | 页面配置、tabBar |
| `frontend/mini-program/utils/api.js` | API 请求 | API 调用问题 |

### 4.3 共享代码关键文件

| 文件路径 | 作用 | 什么时候看 |
|---------|------|-----------|
| `frontend/shared/http/envelope.ts` | 响应体解析 | 统一响应格式问题 |
| `frontend/shared/http/idempotency.ts` | 幂等性 key | 幂等性相关问题 |
| `frontend/shared/storage/localStorage.ts` | 存储封装 | 存储相关问题 |

### 4.4 配置文件

| 文件路径 | 作用 |
|---------|------|
| `pyproject.toml` | Python 项目配置（依赖、工具配置） |
| `backend/alembic.ini` | 数据库迁移配置 |
| `frontend/*/vite.config.ts` | Vite 构建配置 |
| `frontend/*/tsconfig.json` | TypeScript 配置 |
| `frontend/*/eslint.config.js` | ESLint 配置 |
| `docker-compose.yml` | Docker 容器配置 |

## 5. 快速查找指南

### 5.1 我要改一个功能，代码在哪里？

**步骤**：
1. **确定是前端还是后端**
   - 页面、交互 → 前端
   - 接口、数据 → 后端

2. **如果是后端**：
   - 看接口路径，找到对应的 API 文件
   - 看 API 文件调用了哪些 service
   - 看 service 操作了哪些 model

3. **如果是前端**：
   - 看页面路径，找到对应的页面组件
   - 看页面调用了哪些 API
   - 看 API 函数在 `lib/api.ts` 中

### 5.2 我要加一个新功能，代码放哪里？

**后端**：
1. 如果需要新接口：在 `backend/app/api/v1/` 下创建新文件
2. 在 `backend/app/api/v1/router.py` 中注册路由
3. 如果需要新业务逻辑：在 `backend/app/services/` 下创建或修改文件
4. 如果需要新数据表：在 `backend/app/models/` 下创建模型，生成迁移

**前端**：
1. 如果需要新页面：在 `src/pages/` 下创建页面组件
2. 在 `src/router/index.ts` 中添加路由
3. 如果需要新 API 调用：在 `src/lib/api.ts` 中添加函数
4. 如果需要新组件：在 `src/components/` 下创建

### 5.3 我要调试一个问题，从哪里开始？

1. **看错误信息**：错误信息通常指向具体文件
2. **看日志**：后端日志在控制台，前端在浏览器控制台
3. **看调用栈**：从错误发生的地方往上找
4. **看相关代码**：找到相关文件，看逻辑是否正确

### 5.4 我要了解一个功能的完整流程

1. **从前端开始**：找到页面组件，看用户操作
2. **看 API 调用**：看调用了哪个接口
3. **看后端接口**：找到对应的 API 文件
4. **看业务逻辑**：看调用了哪些 service
5. **看数据操作**：看操作了哪些 model

## 6. 常见问题

### Q: 为什么后端有这么多 `admin_*.py` 文件？

A: 因为管理后台功能很多，按功能模块拆分成多个文件，方便维护。比如：
- `admin_users.py`：用户管理
- `admin_venues.py`：场所管理
- `admin_orders.py`：订单管理

### Q: 为什么前端有三个项目（admin、h5、website）？

A: 因为面向的用户不同：
- `admin`：管理后台（管理员、经销商、服务提供方使用）
- `h5`：移动端购买页面（用户通过经销商链接购买）
- `website`：企业官网（展示信息）

### Q: 小程序为什么不使用 shared 目录？

A: 因为小程序是原生开发，不依赖 Node.js 工具链，而且有自己的 API（`wx.request` 等），所以有自己的工具函数。

### Q: 我该在哪里写业务逻辑？

A: 
- **后端**：业务逻辑写在 `services/` 目录，API 层只负责接收请求和返回响应
- **前端**：简单的逻辑可以直接在组件中，复杂的可以提取到 `lib/` 目录

### Q: 模型（models）和服务（services）的区别？

A:
- **models**：定义数据结构，操作数据库（CRUD）
- **services**：实现业务逻辑，调用 models，处理业务规则

---

**最后提醒**：这个文档是快速参考，具体代码还是要看实际文件。如果找不到代码，可以：
1. 搜索关键词
2. 看错误信息指向的文件
3. 问项目负责人


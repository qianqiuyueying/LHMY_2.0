# 健康服务平台 - 完整测试检查清单

> **完整测试参考**: 用于完整功能回归测试，详细步骤请参考 `09-manual-testing-guide.md`

## 基础检查（5分钟）

- [ ] **健康检查**
  ```bash
  curl http://localhost:8000/api/v1/health/live    # 应返回 200
  curl http://localhost:8000/api/v1/health/ready    # 应返回 200
  ```

- [ ] **OpenAPI 文档**
  - 浏览器打开: `http://localhost:8000/docs`
  - 检查所有接口是否显示
  - 检查接口分组是否正确

- [ ] **Metrics 监控**
  ```bash
  curl http://localhost:8000/metrics  # 应返回 Prometheus 格式指标
  ```

- [ ] **容器状态**
  ```bash
  docker ps  # 所有容器应为 healthy
  docker logs lhmy_backend --tail 50  # 检查启动日志
  ```

## 认证授权测试（15分钟）

### Admin 管理员认证

- [ ] **登录**
  - 访问: `/admin/login`
  - 使用管理员账号登录
  - 检查是否跳转到工作台
  - 检查 localStorage 中 token 是否正确保存

- [ ] **2FA 双因素认证**（如已配置）
  - 访问: `/admin-2fa`
  - 输入验证码
  - 检查验证流程

- [ ] **修改密码**
  - 访问: `/account/security`
  - 修改密码
  - 使用新密码重新登录

- [ ] **绑定手机号**（如已实现）
  - 访问安全设置
  - 绑定手机号
  - 验证绑定成功

- [ ] **登出**
  - 点击登出
  - 检查 token 是否清除
  - 检查是否跳转到登录页

### Dealer 经销商认证

- [ ] **登录**
  - 访问: `/dealer/login`
  - 使用经销商账号登录
  - 检查跳转到经销商工作台

- [ ] **注册**（如已实现）
  - 访问注册页面
  - 完成注册流程
  - 验证注册成功

- [ ] **修改密码**
  - 访问安全设置
  - 修改密码

### Provider 服务提供方认证

- [ ] **登录**
  - 访问: `/provider/login`
  - 使用服务提供方账号登录
  - 检查跳转到工作台

- [ ] **注册**（如已实现）
  - 完成注册流程

- [ ] **修改密码**
  - 访问安全设置
  - 修改密码

### 小程序认证

- [ ] **小程序登录**
  - 打开小程序
  - 检查自动登录流程
  - 检查 token 保存

- [ ] **小程序登出**
  - 在个人中心登出
  - 检查 token 清除

### H5 用户认证

- [ ] **短信验证码登录**
  - 输入手机号
  - 获取验证码
  - 输入验证码登录
  - 检查 token 保存

### 权限验证

- [ ] **未登录访问**
  - 未登录访问 `/admin/*` → 应跳转登录页
  - 未登录访问 `/dealer/*` → 应跳转登录页
  - 未登录访问 `/provider/*` → 应跳转登录页

- [ ] **跨角色访问**
  - Dealer 访问 `/admin/*` → 应返回 403
  - Provider 访问 `/admin/*` → 应返回 403
  - Admin 访问 `/dealer/*` → 应返回 403

- [ ] **Token 过期**
  - 使用过期 token 访问接口
  - 应返回 401 并提示重新登录

## H5 购买链路测试（20分钟）

### 前置数据准备

- [ ] **创建服务包模板**（Admin）
  - 访问: `/admin/service-packages`
  - 创建服务包模板
  - 配置服务内容

- [ ] **创建可售卡**（Admin）
  - 访问: `/admin/sellable-cards`
  - 创建可售卡
  - 关联服务包模板
  - 设置价格和区域级别
  - 启用可售卡

- [ ] **创建经销商投放链接**（Dealer 或 Admin）
  - 访问: `/dealer/links` 或 `/admin/dealer-links`
  - 创建投放链接
  - 关联可售卡
  - 设置有效期
  - 复制链接 URL

### H5 页面测试

- [ ] **落地页 - 经销商首页**
  - 访问: `/h5?dealerLinkId={id}`
  - 检查经销商信息显示
  - 检查可售卡列表显示
  - 检查卡片摘要（服务类别×次数）
  - 点击卡片进入购买页

- [ ] **落地页 - 直达购卡页**
  - 访问: `/h5?dealerLinkId={id}&sellableCardId={id}`
  - 应自动跳转到购买页

- [ ] **落地页 - 无经销商链接**
  - 访问: `/h5`
  - "立即购买"按钮应不可点击
  - 应提示"请通过经销商投放链接购买"

- [ ] **购买页 - 页面加载**
  - 访问: `/h5/buy?dealerLinkId={id}&sellableCardId={id}`
  - 检查卡片信息正确显示
  - 检查服务内容展示
  - 检查价格显示

- [ ] **购买页 - 区域选择**（省/市卡）
  - 测试省份选择
  - 测试城市选择
  - 测试搜索功能
  - 验证省卡必须选到省，市卡必须选到市

- [ ] **购买页 - 短信验证码**
  - 输入手机号
  - 点击"获取验证码"
  - 检查是否收到短信
  - 检查按钮倒计时（60秒）
  - 测试倒计时期间不可重复点击

- [ ] **购买页 - 服务协议**
  - 点击"服务协议"链接
  - 检查协议内容加载
  - 检查协议弹窗显示

- [ ] **购买页 - 提交订单**
  - 填写手机号、验证码
  - 选择区域（如需要）
  - 勾选服务协议
  - 点击"立即购买"
  - 检查订单创建成功
  - 检查返回订单 ID

- [ ] **购买页 - 幂等性测试**
  - 使用相同 Idempotency-Key 重复提交
  - 应返回相同订单 ID（不重复创建）

- [ ] **支付流程 - 发起支付**
  - 订单创建后自动发起支付
  - 检查支付参数返回
  - 检查微信支付参数（prepayId 等）

- [ ] **支付流程 - 支付成功**
  - 完成支付（测试环境可使用沙箱）
  - 检查订单状态更新为 PAID
  - 检查跳转到支付结果页

- [ ] **支付流程 - 支付失败**
  - 取消支付或支付失败
  - 检查错误提示
  - 检查可重试支付

- [ ] **支付结果页 - 成功**
  - 访问: `/h5/pay/result?status=success&dealerLinkId=...`
  - 检查成功提示
  - 检查"打开小程序查看权益"提示
  - 测试小程序跳转（如已配置）

- [ ] **支付结果页 - 失败**
  - 访问: `/h5/pay/result?status=failed&reason=...`
  - 检查失败原因显示
  - 检查重试支付入口

## 小程序功能测试（40分钟）

### 小程序启动与登录

- [ ] **首次启动**
  - 打开小程序
  - 检查自动登录流程
  - 检查 token 保存
  - 检查跳转到首页

- [ ] **Token 验证**
  - 启动时检查已有 token
  - Token 有效：直接进入首页
  - Token 无效：重新登录

### 首页功能

- [ ] **入口配置加载**
  - 检查 Banner 轮播显示
  - 检查快捷入口列表
  - 检查"更多入口"功能
  - 测试入口点击跳转

- [ ] **推荐内容**
  - 检查推荐场所列表
  - 检查推荐商品列表
  - 测试点击跳转

- [ ] **搜索功能**
  - 在首页搜索框输入关键词
  - 检查跳转到搜索页
  - 检查搜索结果

- [ ] **错误处理**
  - 检查图片加载失败占位
  - 检查网络错误提示
  - 检查重试功能

### 商城功能

- [ ] **商品分类**
  - 进入商城页
  - 检查分类列表
  - 测试分类切换

- [ ] **商品列表**
  - 检查商品列表加载
  - 测试分页加载
  - 测试筛选功能
  - 测试搜索功能

- [ ] **商品详情**
  - 点击商品进入详情页
  - 检查商品信息显示
  - 检查商品图片
  - 测试加入购物车
  - 测试立即购买

- [ ] **购物车**
  - 添加商品到购物车
  - 检查购物车数量更新
  - 进入购物车页面
  - 检查商品列表
  - 测试修改数量
  - 测试删除商品
  - 测试结算功能

### 订单功能

- [ ] **创建订单**
  - 从购物车结算
  - 选择收货地址
  - 提交订单
  - 检查订单创建成功

- [ ] **订单列表**
  - 进入订单列表页
  - 检查订单状态筛选
  - 测试分页加载
  - 测试下拉刷新

- [ ] **订单详情**
  - 点击订单进入详情
  - 检查订单信息
  - 检查订单状态
  - 测试支付功能
  - 测试确认收货

- [ ] **订单支付**
  - 在订单详情页点击支付
  - 检查支付参数
  - 调用微信支付
  - 完成支付
  - 检查订单状态更新

### 权益功能

- [ ] **权益列表**
  - 进入"我的权益"页面
  - 检查权益列表显示
  - 检查剩余次数显示
  - 测试权益筛选

- [ ] **权益详情**
  - 点击权益进入详情
  - 检查权益信息
  - 检查服务内容
  - 检查使用记录

- [ ] **权益转赠**
  - 在权益详情页
  - 测试转赠功能
  - 输入接收方信息
  - 完成转赠

- [ ] **预约服务**
  - 选择权益
  - 选择服务提供方
  - 选择场所
  - 选择日期和时间段
  - 提交预约
  - 检查预约创建成功
  - 检查权益次数扣减

- [ ] **预约管理**
  - 查看预约列表
  - 检查预约状态
  - 测试取消预约

### 地址管理

- [ ] **地址列表**
  - 进入地址管理页
  - 检查地址列表
  - 测试选择默认地址

- [ ] **添加地址**
  - 点击添加地址
  - 填写地址信息
  - 保存地址
  - 检查添加成功

- [ ] **编辑地址**
  - 点击编辑地址
  - 修改地址信息
  - 保存修改

- [ ] **删除地址**
  - 删除地址
  - 检查删除成功

### 个人中心

- [ ] **个人信息**
  - 查看个人信息
  - 编辑个人信息
  - 检查信息更新

- [ ] **企业绑定**（如已实现）
  - 绑定企业
  - 检查绑定状态

- [ ] **AI 对话**
  - 进入 AI 对话页
  - 发送消息
  - 检查回复
  - 测试对话历史

- [ ] **客服与帮助**
  - 进入客服页面
  - 检查帮助内容

### 聚合页和信息页

- [ ] **聚合页**
  - 通过入口进入聚合页
  - 检查页面内容加载
  - 检查集合商品列表

- [ ] **信息页**
  - 通过入口进入信息页
  - 检查页面内容显示

### WebView 功能

- [ ] **外链打开**
  - 打开 web-view 页面
  - 检查页面加载
  - 检查错误处理
  - 检查超时提示

## 管理后台功能测试（120分钟）

### Admin 管理员功能

#### 工作台

- [ ] **统计数据**
  - 访问: `/admin/dashboard`
  - 检查统计数据正确显示
  - 检查图表正常渲染
  - 检查数据刷新

#### 用户管理

- [ ] **用户列表**
  - 访问: `/admin/users`
  - 检查用户列表显示
  - 测试搜索功能
  - 测试筛选功能
  - 测试分页功能

- [ ] **用户详情**
  - 点击用户查看详情
  - 检查用户信息完整
  - 检查订单记录
  - 检查权益记录

#### 账号管理

- [ ] **管理员账号**
  - 访问: `/admin/accounts`
  - 查看管理员账号列表
  - 创建管理员账号
  - 重置密码
  - 暂停/激活账号

- [ ] **服务提供方账号**
  - 查看服务提供方账号列表
  - 创建服务提供方账号
  - 重置密码
  - 暂停/激活账号

- [ ] **服务提供方员工账号**
  - 查看员工账号列表
  - 创建员工账号
  - 重置密码
  - 暂停/激活账号

- [ ] **经销商账号**
  - 查看经销商账号列表
  - 创建经销商账号
  - 重置密码
  - 暂停/激活账号

#### 订单管理

- [ ] **订单列表**
  - 访问: `/admin/orders`
  - 检查订单列表显示
  - 测试订单类型筛选
  - 测试状态筛选
  - 测试日期筛选
  - 测试搜索功能

- [ ] **商品订单管理**
  - 访问: `/admin/orders/ecommerce-product`
  - 查看商品订单列表
  - 测试发货功能
  - 测试标记已送达

- [ ] **服务包订单管理**
  - 访问: `/admin/orders/service-package`
  - 查看服务包订单列表
  - 检查订单详情

- [ ] **订单详情**
  - 点击订单查看详情
  - 检查订单信息
  - 检查订单状态流转

#### 售后管理

- [ ] **售后单列表**
  - 访问: `/admin/after-sales`
  - 检查售后单列表
  - 测试筛选功能

- [ ] **售后审核**
  - 查看售后单详情
  - 审核通过售后单
  - 审核拒绝售后单
  - 检查状态更新

#### 权益管理

- [ ] **权益列表**
  - 访问: `/admin/entitlements`
  - 检查权益列表
  - 测试筛选功能

- [ ] **权益详情**
  - 查看权益详情
  - 检查权益信息
  - 检查使用记录

- [ ] **权益转赠记录**
  - 查看转赠记录列表
  - 检查转赠详情

#### 预约管理

- [ ] **预约列表**
  - 访问: `/admin/bookings`
  - 检查预约列表
  - 测试筛选功能

- [ ] **预约详情**
  - 查看预约详情
  - 检查预约信息

#### 服务包管理

- [ ] **服务包列表**
  - 访问: `/admin/service-packages`
  - 检查服务包列表
  - 创建服务包
  - 编辑服务包
  - 查看服务包详情

- [ ] **服务包定价**
  - 访问: `/admin/service-package-pricing`
  - 查看定价配置
  - 更新定价
  - 发布定价
  - 下架定价

#### 服务分类管理

- [ ] **服务分类列表**
  - 访问: `/admin/service-categories`
  - 检查分类列表
  - 创建服务分类
  - 编辑服务分类
  - 启用/禁用分类

#### 可售卡管理

- [ ] **可售卡列表**
  - 访问: `/admin/sellable-cards`
  - 检查可售卡列表
  - 创建可售卡
  - 编辑可售卡
  - 启用/禁用可售卡

#### 场所管理

- [ ] **场所列表**
  - 访问: `/admin/venues`
  - 检查场所列表
  - 测试筛选功能
  - 查看场所详情

- [ ] **场所审核**
  - 审核通过场所
  - 审核拒绝场所
  - 发布场所
  - 下架场所

#### 商品管理

- [ ] **商品列表**
  - 访问: `/admin/products`
  - 检查商品列表
  - 测试筛选功能

- [ ] **商品审核**
  - 审核通过商品
  - 审核拒绝商品
  - 下架商品

#### 标签管理

- [ ] **标签列表**
  - 访问: `/admin/tags`
  - 检查标签列表
  - 创建标签
  - 编辑标签

#### 经销商管理

- [ ] **经销商结算**
  - 访问: `/admin/dealer-settlements`
  - 查看结算单列表
  - 配置分账比例
  - 生成结算单
  - 标记已结算

- [ ] **经销商佣金配置**
  - 查看佣金配置
  - 更新佣金比例

#### 服务提供方入驻管理

- [ ] **健康证审核**
  - 访问: `/admin/provider-onboarding/health-card`
  - 查看健康证审核列表
  - 审核通过/拒绝健康证

#### 企业管理

- [ ] **企业列表**
  - 访问: `/admin/enterprises`
  - 检查企业列表
  - 查看企业详情

- [ ] **企业绑定**
  - 访问: `/admin/enterprise-bindings`
  - 查看企业绑定关系

#### CMS 内容管理

- [ ] **内容中心**
  - 访问: `/admin/cms/content-center`
  - 查看栏目列表
  - 创建栏目
  - 编辑栏目
  - 创建内容
  - 编辑内容
  - 发布内容
  - 下架内容

- [ ] **官网内容投放**
  - 访问: `/admin/cms/website`
  - 管理官网内容

- [ ] **小程序内容投放**
  - 访问: `/admin/cms/mini-program`
  - 管理小程序内容

#### 小程序配置

- [ ] **小程序配置**
  - 访问: `/admin/mini-program`
  - 查看小程序配置
  - 更新首页推荐场所
  - 更新首页推荐商品
  - 管理入口列表
  - 发布/下架入口
  - 管理页面
  - 发布/下架页面
  - 管理集合
  - 发布/下架集合

#### 官网配置

- [ ] **首页推荐场所**
  - 访问: `/admin/website/home/recommended-venues`
  - 更新推荐场所

- [ ] **页脚配置**
  - 访问: `/admin/website/footer-config`
  - 更新页脚配置

- [ ] **外部链接**
  - 访问: `/admin/website/external-links`
  - 管理外部链接

- [ ] **SEO 配置**
  - 访问: `/admin/website/site-seo`
  - 更新 SEO 配置

- [ ] **导航控制**
  - 访问: `/admin/website/nav-control`
  - 更新导航配置

- [ ] **维护模式**
  - 访问: `/admin/website/maintenance-mode`
  - 开启/关闭维护模式

#### 区域管理

- [ ] **城市管理**
  - 访问: `/admin/regions/cities`
  - 查看城市列表
  - 管理城市配置

#### 法律协议管理

- [ ] **协议列表**
  - 访问: `/admin/legal/agreements`
  - 查看协议列表
  - 查看协议详情
  - 更新协议内容
  - 发布协议
  - 下架协议

#### AI 配置

- [ ] **AI 配置**
  - 访问: `/admin/ai`
  - 查看 AI 配置
  - 更新 AI 配置

#### 通知管理

- [ ] **发送通知**
  - 访问: `/admin/notifications/send`
  - 创建通知
  - 选择接收者
  - 发送通知

- [ ] **通知接收者**
  - 查看通知接收者列表

#### 审计日志

- [ ] **审计日志**
  - 访问: `/admin/audit-logs`
  - 查看审计日志列表
  - 测试筛选功能
  - 检查日志详情
  - 验证关键操作是否记录

#### 资产管理

- [ ] **资产列表**
  - 访问: `/admin/assets`
  - 查看资产列表

### Dealer 经销商功能

#### 工作台

- [ ] **工作台统计**
  - 访问: `/dealer/dashboard`
  - 检查统计数据

#### 投放链接管理

- [ ] **链接列表**
  - 访问: `/dealer/links`
  - 查看投放链接列表
  - 创建投放链接
  - 设置有效期
  - 检查链接 URL 生成
  - 禁用链接

- [ ] **链接详情**
  - 查看链接详情
  - 检查关联的可售卡

#### 订单归属

- [ ] **订单列表**
  - 访问: `/dealer/orders`
  - 查看订单列表
  - 测试支付状态筛选
  - 测试日期筛选
  - 测试按链接筛选
  - 检查订单卡片摘要

- [ ] **订单导出**
  - 导出订单 CSV
  - 检查导出文件格式

#### 结算管理

- [ ] **结算记录**
  - 访问: `/dealer/settlements`
  - 查看结算记录列表
  - 查看结算单详情

- [ ] **结算账户**
  - 查看结算账户信息
  - 更新打款信息

#### 通知管理

- [ ] **通知列表**
  - 访问: `/dealer/notifications`
  - 查看通知列表
  - 标记通知已读

### Provider 服务提供方功能

#### 工作台

- [ ] **工作台统计**
  - 访问: `/provider/workbench`
  - 检查统计数据
  - 检查入驻状态

- [ ] **入驻流程**
  - 签署基础设施协议
  - 提交健康证
  - 检查入驻状态更新

#### 场所管理

- [ ] **场所列表**
  - 访问: `/provider/venues`
  - 查看场所列表
  - 查看场所详情
  - 更新场所信息
  - 提交展示申请

#### 服务配置

- [ ] **服务管理**
  - 访问: `/provider/services`
  - 查看服务列表
  - 创建服务
  - 编辑服务
  - 配置服务参数

#### 商品管理

- [ ] **商品列表**
  - 访问: `/provider/products`
  - 查看商品列表
  - 创建商品（实物商品/服务商品）
  - 编辑商品
  - 配置库存、运费、重量（实物商品）
  - 提交审核

#### 排班管理

- [ ] **排班设置**
  - 访问: `/provider/schedules`
  - 查看排班列表
  - 批量设置排班
  - 检查排班显示

#### 预约管理

- [ ] **预约列表**
  - 访问: `/provider/bookings`
  - 查看预约列表
  - 测试筛选功能

- [ ] **预约确认**
  - 确认预约
  - 取消预约
  - 检查状态更新

#### 核销管理

- [ ] **核销记录**
  - 访问: `/provider/redemptions`
  - 查看核销记录列表

- [ ] **核销操作**
  - 访问: `/provider/redeem`
  - 扫描权益码
  - 核销权益
  - 检查核销成功
  - 检查权益次数扣减

#### 通知管理

- [ ] **通知列表**
  - 访问: `/provider/notifications`
  - 查看通知列表
  - 标记通知已读

## API 接口测试（60分钟）

### 接口分类测试

#### 认证相关接口

- [ ] **Admin 认证**
  - `POST /api/v1/admin/auth/login` - 登录
  - `POST /api/v1/admin/auth/logout` - 登出
  - `POST /api/v1/admin/auth/refresh` - 刷新 token
  - `POST /api/v1/admin/auth/change-password` - 修改密码
  - `GET /api/v1/admin/auth/security` - 安全设置

- [ ] **Dealer 认证**
  - `POST /api/v1/dealer/auth/login` - 登录
  - `POST /api/v1/dealer/auth/register` - 注册
  - `POST /api/v1/dealer/auth/change-password` - 修改密码

- [ ] **Provider 认证**
  - `POST /api/v1/provider/auth/login` - 登录
  - `POST /api/v1/provider/auth/logout` - 登出
  - `POST /api/v1/provider/auth/refresh` - 刷新 token
  - `POST /api/v1/provider/auth/register` - 注册
  - `POST /api/v1/provider/auth/change-password` - 修改密码

- [ ] **小程序认证**
  - `POST /api/v1/mini-program/auth/login` - 登录
  - `POST /api/v1/mini-program/auth/logout` - 登出

- [ ] **H5 用户认证**
  - `POST /api/v1/auth/request-sms-code` - 获取验证码
  - `POST /api/v1/auth/login` - 登录

#### 用户相关接口

- [ ] **用户信息**
  - `GET /api/v1/users/profile` - 获取用户信息
  - `PATCH /api/v1/users/profile` - 更新用户信息
  - `GET /api/v1/admin/users` - 管理员获取用户列表
  - `GET /api/v1/admin/users/{id}` - 管理员获取用户详情

- [ ] **用户地址**
  - `GET /api/v1/user-addresses` - 获取地址列表
  - `POST /api/v1/user-addresses` - 添加地址
  - `GET /api/v1/user-addresses/{id}` - 获取地址详情
  - `PUT /api/v1/user-addresses/{id}` - 更新地址
  - `DELETE /api/v1/user-addresses/{id}` - 删除地址

#### 订单相关接口

- [ ] **订单操作**
  - `GET /api/v1/orders` - 获取订单列表
  - `POST /api/v1/orders` - 创建订单（需 Idempotency-Key）
  - `GET /api/v1/orders/{id}` - 获取订单详情
  - `POST /api/v1/orders/{id}/pay` - 支付订单（需 Idempotency-Key）
  - `POST /api/v1/orders/{id}/confirm-received` - 确认收货

- [ ] **管理员订单操作**
  - `GET /api/v1/admin/orders` - 获取订单列表
  - `POST /api/v1/admin/orders/{id}/ship` - 发货
  - `POST /api/v1/admin/orders/{id}/deliver` - 标记已送达

- [ ] **经销商订单**
  - `GET /api/v1/dealer/orders` - 获取订单列表
  - `GET /api/v1/dealer/orders/export` - 导出订单

#### 购物车相关接口

- [ ] **购物车操作**
  - `GET /api/v1/cart` - 获取购物车
  - `POST /api/v1/cart/add` - 添加商品（需 Idempotency-Key）
  - `POST /api/v1/cart/update` - 更新购物车（需 Idempotency-Key）

#### 权益相关接口

- [ ] **权益操作**
  - `GET /api/v1/entitlements` - 获取权益列表
  - `GET /api/v1/entitlements/{id}` - 获取权益详情
  - `POST /api/v1/entitlements/{id}/redeem` - 核销权益（需 Idempotency-Key）
  - `POST /api/v1/entitlements/{id}/transfer` - 转赠权益（需 Idempotency-Key）

- [ ] **管理员权益**
  - `GET /api/v1/admin/entitlements` - 获取权益列表
  - `GET /api/v1/admin/entitlements/{id}` - 获取权益详情
  - `GET /api/v1/admin/entitlement-transfers` - 获取转赠记录

#### 预约相关接口

- [ ] **预约操作**
  - `GET /api/v1/bookings` - 获取预约列表
  - `POST /api/v1/bookings` - 创建预约（需 Idempotency-Key）
  - `GET /api/v1/bookings/{id}` - 获取预约详情
  - `POST /api/v1/bookings/{id}/cancel` - 取消预约

- [ ] **服务提供方预约**
  - `GET /api/v1/provider/bookings` - 获取预约列表
  - `PUT /api/v1/bookings/{id}/confirm` - 确认预约
  - `POST /api/v1/provider/bookings/{id}/cancel` - 取消预约

#### 商品相关接口

- [ ] **商品查询**
  - `GET /api/v1/products` - 获取商品列表
  - `GET /api/v1/products/{id}` - 获取商品详情
  - `GET /api/v1/product-categories` - 获取商品分类

- [ ] **管理员商品**
  - `GET /api/v1/admin/products` - 获取商品列表
  - `PUT /api/v1/admin/products/{id}/approve` - 审核通过
  - `PUT /api/v1/admin/products/{id}/reject` - 审核拒绝
  - `PUT /api/v1/admin/products/{id}/off-shelf` - 下架

- [ ] **服务提供方商品**
  - `GET /api/v1/provider/products` - 获取商品列表
  - `POST /api/v1/provider/products` - 创建商品
  - `PUT /api/v1/provider/products/{id}` - 更新商品

#### 服务包相关接口

- [ ] **服务包查询**
  - `GET /api/v1/service-packages` - 获取服务包列表
  - `GET /api/v1/service-packages/{id}` - 获取服务包详情

- [ ] **管理员服务包**
  - `GET /api/v1/admin/service-packages` - 获取服务包列表
  - `POST /api/v1/admin/service-packages` - 创建服务包
  - `PUT /api/v1/admin/service-packages/{id}` - 更新服务包
  - `GET /api/v1/admin/service-package-pricing` - 获取定价
  - `PUT /api/v1/admin/service-package-pricing` - 更新定价
  - `POST /api/v1/admin/service-package-pricing/publish` - 发布定价
  - `POST /api/v1/admin/service-package-pricing/offline` - 下架定价

#### 服务分类相关接口

- [ ] **服务分类**
  - `GET /api/v1/service-categories` - 获取分类列表
  - `GET /api/v1/admin/service-categories` - 管理员获取分类列表
  - `POST /api/v1/admin/service-categories` - 创建分类
  - `PUT /api/v1/admin/service-categories/{id}` - 更新分类
  - `POST /api/v1/admin/service-categories/{id}/enable` - 启用分类
  - `POST /api/v1/admin/service-categories/{id}/disable` - 禁用分类

#### 可售卡相关接口

- [ ] **可售卡查询**
  - `GET /api/v1/sellable-cards/{id}` - 获取可售卡详情
  - `GET /api/v1/dealer/sellable-cards` - 经销商获取可售卡列表

- [ ] **管理员可售卡**
  - `GET /api/v1/admin/sellable-cards` - 获取可售卡列表
  - `POST /api/v1/admin/sellable-cards` - 创建可售卡
  - `PUT /api/v1/admin/sellable-cards/{id}` - 更新可售卡
  - `POST /api/v1/admin/sellable-cards/{id}/enable` - 启用可售卡
  - `POST /api/v1/admin/sellable-cards/{id}/disable` - 禁用可售卡

#### 场所相关接口

- [ ] **场所查询**
  - `GET /api/v1/venues` - 获取场所列表
  - `GET /api/v1/venues/{id}` - 获取场所详情
  - `GET /api/v1/venues/{id}/available-slots` - 获取可用时段

- [ ] **管理员场所**
  - `GET /api/v1/admin/venues` - 获取场所列表
  - `POST /api/v1/admin/venues/{id}/publish` - 发布场所
  - `POST /api/v1/admin/venues/{id}/approve` - 审核通过
  - `POST /api/v1/admin/venues/{id}/reject` - 审核拒绝
  - `POST /api/v1/admin/venues/{id}/offline` - 下架

- [ ] **服务提供方场所**
  - `GET /api/v1/provider/venues` - 获取场所列表
  - `PUT /api/v1/provider/venues/{id}` - 更新场所
  - `POST /api/v1/provider/venues/{id}/submit-showcase` - 提交展示
  - `GET /api/v1/provider/venues/{venueId}/services` - 获取服务列表
  - `POST /api/v1/provider/venues/{venueId}/services` - 创建服务
  - `PUT /api/v1/provider/venues/{venueId}/services/{id}` - 更新服务
  - `GET /api/v1/provider/venues/{venueId}/schedules` - 获取排期
  - `PUT /api/v1/provider/venues/{venueId}/schedules/batch` - 批量更新排期

#### 经销商相关接口

- [ ] **经销商链接**
  - `GET /api/v1/dealer-links` - 获取链接列表
  - `POST /api/v1/dealer-links` - 创建链接（需 Idempotency-Key）
  - `POST /api/v1/dealer-links/{id}/disable` - 禁用链接
  - `GET /api/v1/dealer-links/verify` - 验证链接

- [ ] **经销商结算**
  - `GET /api/v1/dealer/settlements` - 获取结算记录
  - `GET /api/v1/dealer/settlement-account` - 获取结算账户
  - `PUT /api/v1/dealer/settlement-account` - 更新结算账户

- [ ] **管理员经销商管理**
  - `GET /api/v1/admin/dealer-commission` - 获取佣金配置
  - `PUT /api/v1/admin/dealer-commission` - 更新佣金配置
  - `POST /api/v1/admin/dealer-settlements/generate` - 生成结算单
  - `GET /api/v1/admin/dealer-settlements` - 获取结算单列表
  - `POST /api/v1/admin/dealer-settlements/{id}/mark-settled` - 标记已结算

#### 配置相关接口

- [ ] **小程序配置**
  - `GET /api/v1/mini-program/entries` - 获取入口列表
  - `GET /api/v1/mini-program/home/recommended-venues` - 获取推荐场所
  - `GET /api/v1/mini-program/home/recommended-products` - 获取推荐商品
  - `GET /api/v1/mini-program/pages/{id}` - 获取页面详情
  - `GET /api/v1/mini-program/collections/{id}/items` - 获取集合商品

- [ ] **官网配置**
  - `GET /api/v1/website/home/recommended-venues` - 获取推荐场所
  - `GET /api/v1/website/footer/config` - 获取页脚配置
  - `GET /api/v1/website/external-links` - 获取外部链接
  - `GET /api/v1/website/site-seo` - 获取 SEO 配置
  - `GET /api/v1/website/nav-control` - 获取导航控制
  - `GET /api/v1/website/maintenance-mode` - 获取维护模式

- [ ] **H5 配置**
  - `GET /api/v1/h5/landing/faq-terms` - 获取 FAQ 条款
  - `GET /api/v1/h5/legal/service-agreement` - 获取服务协议
  - `GET /api/v1/h5/mini-program/launch` - 获取小程序启动参数
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}` - 获取经销商链接信息
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards` - 获取可售卡列表
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards/{sellableCardId}` - 获取可售卡详情

#### CMS 相关接口

- [ ] **小程序 CMS**
  - `GET /api/v1/mini-program/cms/channels` - 获取栏目列表
  - `GET /api/v1/mini-program/cms/contents` - 获取内容列表
  - `GET /api/v1/mini-program/cms/contents/{id}` - 获取内容详情

- [ ] **官网 CMS**
  - `GET /api/v1/website/cms/channels` - 获取栏目列表
  - `GET /api/v1/website/cms/contents` - 获取内容列表
  - `GET /api/v1/website/cms/contents/{id}` - 获取内容详情

- [ ] **管理员 CMS**
  - `GET /api/v1/admin/cms/channels` - 获取栏目列表
  - `POST /api/v1/admin/cms/channels` - 创建栏目
  - `PUT /api/v1/admin/cms/channels/{id}` - 更新栏目
  - `GET /api/v1/admin/cms/contents` - 获取内容列表
  - `POST /api/v1/admin/cms/contents` - 创建内容
  - `PUT /api/v1/admin/cms/contents/{id}` - 更新内容
  - `POST /api/v1/admin/cms/contents/{id}/publish` - 发布内容
  - `POST /api/v1/admin/cms/contents/{id}/offline` - 下架内容

#### 其他接口

- [ ] **区域接口**
  - `GET /api/v1/regions/cities` - 获取城市列表
  - `GET /api/v1/admin/regions` - 管理员获取地区列表

- [ ] **标签接口**
  - `GET /api/v1/tags` - 获取标签列表

- [ ] **分类节点接口**
  - `GET /api/v1/taxonomy-nodes` - 获取分类节点列表

- [ ] **法律协议接口**
  - `GET /api/v1/legal/agreements/{code}` - 获取协议内容
  - `GET /api/v1/admin/legal/agreements` - 管理员获取协议列表
  - `PUT /api/v1/admin/legal/agreements/{code}` - 更新协议
  - `POST /api/v1/admin/legal/agreements/{code}/publish` - 发布协议
  - `POST /api/v1/admin/legal/agreements/{code}/offline` - 下架协议

- [ ] **AI 接口**
  - `POST /api/v1/ai/chat` - AI 对话（需 Idempotency-Key）
  - `GET /api/v1/admin/ai/config` - 获取 AI 配置
  - `PUT /api/v1/admin/ai/config` - 更新 AI 配置

- [ ] **通知接口**
  - `GET /api/v1/admin/notifications` - 获取通知列表
  - `POST /api/v1/admin/notifications` - 创建通知（需 Idempotency-Key）
  - `GET /api/v1/admin/notification-receivers` - 获取接收者列表
  - `GET /api/v1/dealer/notifications` - 经销商获取通知列表
  - `GET /api/v1/provider/notifications` - 服务提供方获取通知列表

- [ ] **售后接口**
  - `GET /api/v1/after-sales/cases` - 获取售后单列表
  - `POST /api/v1/after-sales/cases` - 创建售后单
  - `GET /api/v1/after-sales/cases/{id}` - 获取售后单详情
  - `GET /api/v1/admin/after-sales/cases` - 管理员获取售后单列表
  - `POST /api/v1/admin/after-sales/cases/{id}/approve` - 审核通过
  - `POST /api/v1/admin/after-sales/cases/{id}/reject` - 审核拒绝

- [ ] **文件上传接口**
  - `POST /api/v1/uploads/images` - 上传图片

- [ ] **审计日志接口**
  - `GET /api/v1/admin/audit-logs` - 获取审计日志

- [ ] **资产管理接口**
  - `GET /api/v1/admin/assets` - 获取资产列表

### 接口规范测试

- [ ] **请求格式**
  - Content-Type: `application/json`
  - Authorization header 格式正确
  - Idempotency-Key header（写操作）

- [ ] **响应格式**
  - 成功响应: `{"success": true, "data": {...}}`
  - 错误响应: `{"success": false, "error": {...}}`
  - 错误码规范（UNAUTHENTICATED, FORBIDDEN 等）
  - requestId 存在

- [ ] **分页参数**
  - `page`、`pageSize` 参数
  - 响应包含 `total`、`page`、`pageSize`

- [ ] **幂等性**
  - 写操作支持 Idempotency-Key
  - 相同 Key 重复请求返回相同结果

## 边界与异常测试（30分钟）

### 输入验证

- [ ] **必填字段**
  - 不填写必填字段提交 → 应返回 400
  - 错误信息应明确指示缺失字段

- [ ] **字段格式**
  - 邮箱格式错误 → 应返回 400
  - 手机号格式错误 → 应返回 400
  - 日期格式错误 → 应返回 400
  - URL 格式错误 → 应返回 400

- [ ] **字段长度**
  - 输入超长字符串 → 应返回 400 或截断
  - 输入空字符串 → 应返回 400（如必填）

- [ ] **特殊字符**
  - 输入 SQL 注入字符 → 应正确处理
  - 输入 XSS 字符 → 应正确转义
  - 输入特殊 Unicode 字符 → 应正确处理

- [ ] **数值范围**
  - 输入负数价格 → 应返回 400
  - 输入超大数值 → 应返回 400
  - 输入小数位数超限 → 应返回 400
  - 输入 0 或负数数量 → 应返回 400

### 权限边界

- [ ] **未登录访问**
  - 访问需要登录的接口 → 应返回 401
  - 错误码: UNAUTHENTICATED

- [ ] **跨角色访问**
  - Dealer 访问 Admin 接口 → 应返回 403
  - Provider 访问 Admin 接口 → 应返回 403
  - Admin 访问 Dealer 接口 → 应返回 403
  - 错误码: FORBIDDEN

- [ ] **资源所有权**
  - 访问其他用户的订单 → 应返回 403
  - 访问其他用户的权益 → 应返回 403
  - 访问其他用户的地址 → 应返回 403

- [ ] **Token 过期**
  - 使用过期 token → 应返回 401
  - 提示重新登录

- [ ] **Token 无效**
  - 使用无效 token → 应返回 401
  - 使用伪造 token → 应返回 401

### 业务规则验证

- [ ] **库存检查**
  - 购买超出库存的商品 → 应拒绝
  - 错误信息应明确
  - 并发购买同一商品 → 应正确处理

- [ ] **状态流转**
  - 已支付订单再次支付 → 应拒绝
  - 已取消订单确认收货 → 应拒绝
  - 未支付订单发货 → 应拒绝（或允许）
  - 检查状态机规则

- [ ] **时间限制**
  - 过期的投放链接 → 应拒绝使用
  - 过期的优惠券 → 应拒绝使用
  - 预约时间冲突 → 应拒绝

- [ ] **数量限制**
  - 购买数量超过限制 → 应拒绝
  - 权益转赠次数限制 → 应检查

- [ ] **重复操作**
  - 重复支付 → 应拒绝或返回原订单
  - 重复创建相同订单 → 应使用幂等性处理
  - 重复核销 → 应拒绝

- [ ] **依赖检查**
  - 删除有关联数据的分类 → 应拒绝
  - 禁用有订单的可售卡 → 应检查
  - 删除有预约的场所 → 应检查

### 异常场景

- [ ] **网络异常**
  - 模拟网络超时 → 应返回超时错误
  - 模拟网络断开 → 应返回连接错误
  - 错误提示应友好

- [ ] **服务异常**
  - 停止数据库服务 → 应返回 503 或错误信息
  - 停止 Redis 服务 → 应返回 503 或错误信息
  - 停止 RabbitMQ 服务 → 应检查影响范围
  - 错误信息应明确

- [ ] **数据一致性**
  - 并发操作同一资源 → 应保持数据一致
  - 并发创建订单 → 应正确处理
  - 并发核销权益 → 应正确处理
  - 检查无脏数据

- [ ] **资源不存在**
  - 访问不存在的订单 → 应返回 404
  - 访问不存在的用户 → 应返回 404
  - 访问不存在的商品 → 应返回 404
  - 错误码: NOT_FOUND

- [ ] **状态冲突**
  - 订单状态冲突 → 应返回 409
  - 错误码: STATE_CONFLICT
  - 错误信息应明确

- [ ] **频率限制**
  - 频繁请求验证码 → 应限制频率
  - 频繁登录失败 → 应锁定账号
  - 错误码: RATE_LIMITED

### 数据完整性

- [ ] **关联数据**
  - 删除有订单的用户 → 应检查关联
  - 删除有商品的分类 → 应检查关联
  - 删除有预约的场所 → 应检查关联

- [ ] **级联操作**
  - 删除订单 → 应检查权益创建
  - 取消预约 → 应检查权益恢复
  - 核销权益 → 应检查次数扣减

## 性能与稳定性测试（20分钟）

### 响应时间测试

- [ ] **列表接口**
  - 用户列表 < 500ms
  - 订单列表 < 500ms
  - 商品列表 < 500ms
  - 权益列表 < 500ms

- [ ] **详情接口**
  - 订单详情 < 300ms
  - 用户详情 < 300ms
  - 商品详情 < 300ms
  - 权益详情 < 300ms

- [ ] **写操作**
  - 创建订单 < 1000ms
  - 支付订单 < 1000ms
  - 创建预约 < 1000ms

- [ ] **健康检查**
  - liveness < 50ms
  - readiness < 200ms

### 并发测试

- [ ] **健康检查并发**
  ```bash
  ab -n 1000 -c 100 http://localhost:8000/api/v1/health/live
  ```
  - 错误率 < 1%
  - 平均响应时间 < 100ms

- [ ] **列表接口并发**
  ```bash
  ab -n 500 -c 50 -H "Authorization: Bearer {token}" \
    http://localhost:8000/api/v1/admin/users
  ```
  - 错误率 < 1%
  - 平均响应时间 < 500ms

- [ ] **写操作并发**
  - 并发创建订单（10个并发）
  - 检查幂等性
  - 检查数据一致性

### 负载测试

- [ ] **数据库压力**
  - 模拟大量并发查询
  - 检查数据库性能
  - 检查连接池状态

- [ ] **缓存性能**
  - 检查 Redis 命中率
  - 检查缓存更新

### 稳定性测试

- [ ] **长时间运行**
  - 系统运行 24 小时
  - 检查内存泄漏
  - 检查错误日志
  - 检查性能下降

- [ ] **容器重启**
  - 重启后端容器
  - 检查服务恢复
  - 检查数据不丢失
  - 检查连接恢复

- [ ] **数据库重启**
  - 重启 MySQL 容器
  - 检查连接恢复
  - 检查数据完整性

- [ ] **Redis 重启**
  - 重启 Redis 容器
  - 检查缓存恢复
  - 检查服务正常

### 资源使用

- [ ] **内存使用**
  - 检查容器内存使用
  - 检查是否有内存泄漏

- [ ] **CPU 使用**
  - 检查 CPU 使用率
  - 检查是否有 CPU 瓶颈

- [ ] **磁盘使用**
  - 检查日志文件大小
  - 检查数据库文件大小

## 日志与监控测试（15分钟）

### 错误日志

- [ ] **查看错误日志**
  ```bash
  docker logs lhmy_backend | grep ERROR
  docker logs lhmy_backend | grep WARN
  ```
  - 检查是否有严重错误
  - 检查警告信息

- [ ] **日志格式**
  - 检查日志格式统一
  - 检查 requestId 存在
  - 检查时间戳格式

- [ ] **日志级别**
  - 检查日志级别正确
  - 生产环境不应有 DEBUG 日志

### 审计日志

- [ ] **关键操作记录**
  - Admin 后台 → 审计日志
  - 检查创建订单是否记录
  - 检查修改密码是否记录
  - 检查账号操作是否记录
  - 检查权限变更是否记录

- [ ] **审计日志查询**
  - 测试筛选功能
  - 测试日期范围查询
  - 测试操作类型筛选
  - 测试用户筛选

- [ ] **审计日志详情**
  - 查看日志详情
  - 检查操作信息完整
  - 检查操作时间准确

### Metrics 监控

- [ ] **Prometheus Metrics**
  ```bash
  curl http://localhost:8000/metrics
  ```
  - 检查指标格式正确
  - 检查 HTTP 请求指标
  - 检查错误率指标

- [ ] **指标完整性**
  - 检查关键指标存在
  - 检查指标值合理

### 请求追踪

- [ ] **RequestId**
  - 检查每个请求都有 requestId
  - 检查 requestId 在日志中一致
  - 检查 requestId 在响应中返回

- [ ] **日志关联**
  - 使用 requestId 追踪请求
  - 检查日志链路完整

## 文件上传测试（10分钟）

- [ ] **图片上传**
  - 上传正常图片 → 应成功
  - 检查文件大小限制
  - 检查文件格式限制
  - 检查返回 URL 正确

- [ ] **异常文件**
  - 上传超大文件 → 应拒绝
  - 上传错误格式 → 应拒绝
  - 上传恶意文件 → 应拒绝

- [ ] **图片显示**
  - 检查上传的图片可正常显示
  - 检查图片 URL 可访问

## 官网功能测试（15分钟）

- [ ] **首页**
  - 访问官网首页
  - 检查推荐场所显示
  - 检查页面加载正常

- [ ] **内容页面**
  - 访问 CMS 内容页
  - 检查内容显示正确
  - 检查图片加载

- [ ] **SEO**
  - 检查 SEO 配置生效
  - 检查 meta 标签
  - 检查页面标题

- [ ] **维护模式**
  - 开启维护模式
  - 检查维护页面显示
  - 关闭维护模式
  - 检查正常页面恢复

## 集成测试（20分钟）

- [ ] **完整购买流程**
  1. H5 创建订单
  2. 完成支付
  3. 小程序查看权益
  4. 创建预约
  5. Provider 确认预约
  6. 核销权益
  7. Admin 查看订单和权益记录

- [ ] **完整商品购买流程**
  1. 小程序浏览商品
  2. 加入购物车
  3. 创建订单
  4. 完成支付
  5. Admin 发货
  6. 用户确认收货

- [ ] **经销商完整流程**
  1. Dealer 创建投放链接
  2. H5 通过链接购买
  3. 完成支付
  4. Dealer 查看订单归属
  5. Admin 生成结算单
  6. Admin 标记已结算

- [ ] **服务提供方完整流程**
  1. Provider 注册/登录
  2. 签署协议
  3. 提交健康证
  4. Admin 审核健康证
  5. Provider 创建场所
  6. Admin 审核场所
  7. Provider 配置服务
  8. Provider 设置排班
  9. 用户创建预约
  10. Provider 确认预约
  11. Provider 核销权益

---

## 快速回归路径（最小测试集）

如果时间有限，按以下顺序测试核心功能：

### 最小回归测试（35分钟）

1. **基础检查** (2分钟)
   - 健康检查接口
   - 容器状态
   - OpenAPI 文档

2. **认证测试** (3分钟)
   - Admin 登录
   - Dealer 登录
   - Provider 登录
   - 权限验证

3. **H5 购买链路** (10分钟)
   - 创建可售卡和投放链接
   - 访问 H5 落地页
   - 完成购买流程
   - 完成支付

4. **小程序核心功能** (10分钟)
   - 小程序登录
   - 浏览商品
   - 加入购物车
   - 创建订单
   - 查看权益列表

5. **管理后台核心操作** (10分钟)
   - Admin: 查看订单列表、用户列表、工作台统计
   - Dealer: 查看订单归属、投放链接
   - Provider: 查看预约列表、核销记录

### 中等回归测试（90分钟）

在最小回归基础上，增加：

6. **管理后台完整功能** (30分钟)
   - Admin: 可售卡管理、服务包管理、场所审核
   - Dealer: 结算账户管理
   - Provider: 商品管理、排班管理

7. **小程序完整功能** (15分钟)
   - 权益详情、预约创建、地址管理
   - AI 对话、个人中心

8. **API 接口测试** (15分钟)
   - 抽查关键接口
   - 测试幂等性
   - 测试错误处理

### 完整回归测试（4-6小时）

按照本文档所有章节逐项测试，确保所有功能正常。

---

## 测试优先级说明

### P0 - 核心功能（必须测试）
- 健康检查
- 认证授权
- H5 购买链路
- 小程序核心功能
- 订单管理
- 支付流程

### P1 - 重要功能（建议测试）
- 管理后台主要功能
- 权益管理
- 预约管理
- 经销商功能
- 服务提供方功能

### P2 - 一般功能（可选测试）
- CMS 内容管理
- 配置管理
- 审计日志
- 性能测试
- 边界测试

---

## 测试时间估算

| 测试类型 | 预计时间 | 优先级 |
|---------|---------|--------|
| 基础检查 | 5分钟 | P0 |
| 认证测试 | 15分钟 | P0 |
| H5 购买链路 | 20分钟 | P0 |
| 小程序功能 | 40分钟 | P0 |
| 管理后台功能 | 120分钟 | P1 |
| API 接口测试 | 60分钟 | P1 |
| 边界与异常测试 | 30分钟 | P1 |
| 性能测试 | 20分钟 | P2 |
| 日志与监控 | 15分钟 | P2 |
| 文件上传 | 10分钟 | P1 |
| 官网功能 | 15分钟 | P2 |
| 集成测试 | 20分钟 | P1 |

**总计**: 约 6-7 小时完成完整测试

---

## 测试问题记录模板

```
【问题编号】: #001
【测试时间】: 2026-01-06
【测试模块】: H5 购买链路
【测试步骤】:
1. 访问 /h5?dealerLinkId=xxx
2. 点击购买按钮
【预期结果】: 跳转到购买页
【实际结果】: 页面报错 500
【错误信息】: [粘贴错误日志]
【环境信息】: Docker Compose, Windows 10
【优先级】: P0/P1/P2
```

---

**最后更新**: 2026-01-06


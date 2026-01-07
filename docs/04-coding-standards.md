# 代码规范与开发规范（实用版）

> **说明**：这是一个"最小可用"的规范文档，只包含日常开发中实际会用到的内容。随着项目发展，可以逐步补充更多细节。

## 1. 提交代码前必做检查（5分钟搞定）

### 后端（Python）

在提交代码前，运行这些命令确保没问题：

```bash
# 1. 格式化代码（自动修复格式问题）
uv run black backend/app backend/tests

# 2. 检查代码格式（不修改，只看有没有问题）
uv run black --check backend/app backend/tests

# 3. 代码检查（检查常见错误）
uv run flake8 backend/app backend/tests

# 4. 类型检查（可选，如果报错太多可以先跳过）
uv run mypy backend/app

# 5. 运行测试
uv run pytest backend
```

**如果某个命令报错**：
- `black` 报错：直接运行 `uv run black <文件路径>` 让它自动修复
- `flake8` 报错：看错误信息，通常是导入顺序、未使用的变量等问题，手动修复
- `mypy` 报错：如果太多可以先不管，但尽量修复明显的类型错误
- `pytest` 报错：必须修复，测试不通过不能提交

### 前端（TypeScript/Vue）

在提交代码前，运行这些命令：

```bash
# 进入对应的前端目录，比如 frontend/admin
cd frontend/admin

# 1. 类型检查
npm run typecheck

# 2. 代码检查
npm run lint
```

**如果报错**：
- `typecheck` 报错：通常是类型不匹配，看错误信息修复
- `lint` 报错：可以尝试 `npm run lint -- --fix` 自动修复（如果有这个命令），或者手动修复

**注意**：三个前端项目（admin、h5、website）都需要检查，如果只改了其中一个，只检查那个就行。

## 2. Git 提交规范（简单版）

### 提交消息格式

```
<类型>: <简短描述>

<详细说明（可选）>
```

**类型**（选一个）：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `refactor`: 重构代码（不改变功能）
- `style`: 代码格式调整（不影响功能）
- `test`: 添加或修改测试
- `chore`: 其他杂项（比如更新依赖）

**示例**：
```
feat: 添加用户管理页面

- 实现用户列表展示
- 添加搜索功能
```

```
fix: 修复登录后跳转错误
```

```
docs: 更新README中的安装说明
```

### 分支命名（简单版）

- 新功能：`feature/功能名称`，比如 `feature/user-management`
- 修复bug：`bugfix/问题描述`，比如 `bugfix/login-redirect`
- 紧急修复：`hotfix/问题描述`

**工作流程**：
1. 从 `main` 或 `develop` 分支创建新分支
2. 在新分支上开发
3. 提交前运行上面的检查命令
4. 创建 Pull Request
5. 代码审查通过后合并

## 3. Spec-Driven 开发流程（必须遵守）

### 开发前

1. **先看规格文档**：
   - 主规格：`specs/health-services-platform/design.md`
   - 任务清单：`specs/health-services-platform/tasks.md`
   - 相关事实清单：`specs/health-services-platform/facts/`

2. **在 tasks.md 中创建或找到对应任务**：
   - 如果没有任务，先创建一个
   - 明确验收标准（怎么做算完成）

### 开发中

- **严格按照规格实现**，不要自己加功能
- **如果发现规格有问题或不清楚**：
  - 先停下来
  - 问清楚或补充规格
  - 再继续开发

### 开发后

1. **更新事实清单**（`specs/health-services-platform/facts/`）：
   - 记录你改了哪些文件
   - 记录新增了哪些接口/函数
   - 记录关键配置变更

2. **更新任务状态**：
   - 在 `tasks.md` 中标记任务完成
   - 可以简单说明完成情况

## 4. 代码审查清单（提交PR前自己检查）

### 基础检查（必须）

- [ ] 代码能正常运行（本地测试过）
- [ ] 没有明显的bug（比如空指针、未处理异常）
- [ ] 没有提交调试代码（console.log、print等）
- [ ] 没有提交敏感信息（密码、密钥等）

### 代码质量（尽量做到）

- [ ] 变量和函数命名清晰（能看懂是干什么的）
- [ ] 没有明显的重复代码
- [ ] 复杂逻辑有注释说明
- [ ] 代码格式正确（运行过格式化工具）

### 测试（尽量做到）

- [ ] 新功能有测试（至少手动测试过）
- [ ] 修复bug时有测试验证修复成功
- [ ] 没有破坏现有功能（运行过相关测试）

### Spec-Driven 检查（必须）

- [ ] 变更可以追溯到规格文档（在PR描述中说明）
- [ ] 实现符合规格要求（没有自己加功能）
- [ ] 已更新相关事实清单（如果适用）

## 5. 常见问题速查

### Q: Black 格式化后代码变了很多，正常吗？
A: 正常。Black 会自动调整代码格式，让它符合规范。提交前运行一次就行。

### Q: Flake8 报错说导入顺序不对，怎么办？
A: 标准库 → 第三方库 → 本地库，每类之间空一行。或者运行 `uv run black` 让它自动整理。

### Q: MyPy 报错太多，可以先不管吗？
A: 如果项目刚开始用类型检查，可以先修复明显的错误，其他的慢慢来。但新代码尽量写对类型。

### Q: ESLint 报错看不懂怎么办？
A: 看错误信息里的规则名称，去 ESLint 官网查一下。大部分是格式问题，可以尝试自动修复。

### Q: 类型检查报错，但代码能跑，要修复吗？
A: 要。类型错误说明代码可能有问题，或者类型定义不准确。尽量修复，这样代码更可靠。

### Q: 测试写不好，可以先不写吗？
A: 关键功能（比如登录、支付）必须有测试。其他功能可以先手动测试，但尽量补上自动化测试。

## 6. 工具命令速查表

### 后端

| 操作 | 命令 |
|------|------|
| 格式化代码 | `uv run black backend/app backend/tests` |
| 检查格式 | `uv run black --check backend/app backend/tests` |
| 代码检查 | `uv run flake8 backend/app backend/tests` |
| 类型检查 | `uv run mypy backend/app` |
| 运行测试 | `uv run pytest backend` |
| 运行单个测试文件 | `uv run pytest backend/tests/某个文件.py` |

### 前端（以 admin 为例）

| 操作 | 命令 |
|------|------|
| 类型检查 | `cd frontend/admin && npm run typecheck` |
| 代码检查 | `cd frontend/admin && npm run lint` |
| 构建 | `cd frontend/admin && npm run build` |
| E2E测试 | `cd frontend/admin && npm run e2e` |

**注意**：h5 和 website 的命令一样，只是目录不同。

## 7. 渐进式学习建议

如果你刚开始接触这些工具，建议按这个顺序学习：

### 第一阶段（必须掌握）

1. **Git 基础**：
   - 创建分支、提交代码、创建PR
   - 提交消息格式

2. **代码格式化**：
   - 后端：`uv run black`
   - 前端：`npm run lint`（如果支持自动修复）

3. **运行测试**：
   - 后端：`uv run pytest`
   - 确保测试通过再提交

### 第二阶段（逐步掌握）

1. **代码检查工具**：
   - 后端：`flake8`（看错误信息，逐步修复）
   - 前端：`npm run lint`（理解常见错误）

2. **类型检查**：
   - 后端：`mypy`（先修复明显错误）
   - 前端：`npm run typecheck`（理解TypeScript类型）

### 第三阶段（深入理解）

1. **工具配置**：
   - 理解 `pyproject.toml`、`eslint.config.js` 等配置文件
   - 根据需要调整规则

2. **测试编写**：
   - 学习写单元测试
   - 学习写集成测试

3. **代码审查**：
   - 理解审查清单的每一项
   - 学会审查别人的代码

## 8. 需要帮助时

- **工具不会用**：先看错误信息，然后搜索"工具名 + 错误信息"
- **规格不清楚**：问项目负责人或看 `specs/` 目录下的文档
- **代码不知道怎么写**：参考项目中类似的代码
- **测试不会写**：参考 `backend/tests/` 或 `frontend/admin/tests/` 中的例子

---

**最后提醒**：这个文档是"最小可用版本"，随着项目发展和你技能提升，可以逐步补充更多内容。不要一开始就追求完美，先能用起来最重要。

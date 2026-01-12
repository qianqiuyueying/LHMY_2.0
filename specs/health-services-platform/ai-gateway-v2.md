## AI 网关 v2（Provider / Strategy 解耦，可替换三年不重写）

> 规格目的：把 AI 能力从“绑定某个模型/SDK 的配置项”升级为“可替换的能力平台”。  
> 口径：小程序只感知 **scene（场景能力）**；后端统一网关；Admin 分为 **Provider（技术配置）** 与 **Strategy（业务语义）** 两层。

---

### 1) 背景与目标

#### 1.1 背景

- AI 用途：用户引流与留存工具；健康领域知识问答（**非医疗诊断**）。
- 端侧约束：小程序端 **不直连 AI**；所有 AI 请求必须走：小程序 → 后端 → Provider。
- 现状：已存在 v1（OpenAI compatible）配置：`baseUrl + apiKey + model + systemPrompt + temperature + maxTokens`（SystemConfig `AI_CONFIG`）。
- 新引入：阿里百炼 DashScope（**应用模式** & **模型模式**）。
- 未来：可能接入其他 Provider（火山、私有模型、Agent 等）。

#### 1.2 本次目标（必须达成）

- **彻底重构 AI 配置体系**，使其：
  - 不绑定具体模型或 SDK
  - 兼容 DashScope 应用、DashScope 模型、OpenAPI compatible、未来未知 Provider
  - Admin 配置“业务语义”，而不是“技术细节”
  - 小程序只感知“AI 场景能力”，而不是模型

---

### 2) 核心设计原则（强制）

1) **Admin 不配置模型**；只配置：
   - **AI Provider（技术配置层）**
   - **AI Strategy（业务语义层）**
2) Provider 是技术实现层，Strategy 是业务语义层。
3) Provider 的差异（SDK / HTTP / App / Model）必须通过 **Adapter** 屏蔽。
4) Strategy 配置 **不得依赖** 某个 Provider 的私有字段。
5) 小程序端 **禁止出现**：
   - apiKey / appId / endpoint / model 名 / SDK 参数
6) 必须支持未来 **无痛切换 Provider**（切换不影响小程序端；历史日志可追溯）。

---

### 3) 数据模型（v2）

#### 3.1 Provider（技术配置层）

- Provider 类型（枚举，未来可扩展）：
  - `dashscope_application`
  - `dashscope_model`
  - `openapi_compatible`
  - `custom_provider`（预留）

- Provider 配置结构（逻辑结构，字段解释由 adapter 决定）：

```json
{
  "provider_type": "dashscope_application",
  "credentials": {
    "api_key": "string",
    "app_id": "string"
  },
  "endpoint": null,
  "extra": {}
}
```

OpenAPI compatible 示例：

```json
{
  "provider_type": "openapi_compatible",
  "credentials": {
    "api_key": "string"
  },
  "endpoint": "https://api.openai.com/v1",
  "extra": {
    "default_model": "gpt-4o-mini"
  }
}
```

要求：
- Provider 配置 **不强制 model**
- `endpoint` 可选（adapter 可有默认值）
- `credentials` 字段完全由 provider adapter 自行解释
- 支持「连接测试」

#### 3.2 Strategy（业务语义层）

Strategy 示例（知识问答）：

```json
{
  "scene": "knowledge_qa",
  "display_name": "健康知识助手",
  "prompt_template": "你是一个健康领域知识助手，只提供科普，不提供诊断。",
  "generation_config": {
    "temperature": 0.4,
    "max_output_tokens": 800
  },
  "constraints": {
    "forbid_medical_diagnosis": true,
    "safe_mode": true
  }
}
```

要求：
- Strategy 中不得出现：`model/apiKey/appId/endpoint/SDK 参数`
- `generation_config` 是“建议值”，Provider 不支持时允许忽略
- Strategy 必须是 Provider 无关的

#### 3.3 Provider ↔ Strategy 绑定

逻辑关系：

```json
{
  "strategy_scene": "knowledge_qa",
  "provider_id": "dashscope_app_prod"
}
```

要求：
- 一个 Strategy 可切换 Provider
- 切换不影响小程序端

---

### 4) 后端设计（v2）

#### 4.1 AI Gateway（统一入口）

统一入口伪代码：

```python
def call_ai(scene: str, user_input: str, context: dict):
    strategy = load_strategy(scene)
    provider = load_provider(strategy.provider_id)
    adapter = ProviderAdapterFactory.create(provider)
    return adapter.execute(strategy, user_input, context)
```

#### 4.2 Provider Adapter 规范（强制）

每个 Provider Adapter 必须实现：
- `supports(strategy)`：是否支持该策略（可用于提前校验/降级）
- `execute(strategy, input, context)`：执行调用并返回统一结果

Adapter 必须自动处理：
- prompt 拼接（基于 Strategy.prompt_template）
- generation_config 适配（temperature/max_output_tokens 等）
- Provider 不支持字段的降级忽略（不得反向污染 Strategy 设计）

#### 4.3 DashScope 特别说明

- DashScope 应用模式：
  - 不要求 model
  - prompt 可能由应用内部控制
- DashScope 模型模式：
  - model 放在 Provider.extra（例如 `extra.default_model` 或等价字段）
- 两者必须 **共用 Strategy**

---

### 5) 小程序端契约（v2）

#### 5.1 小程序只关心“AI 场景”

接口：
- `POST /api/v1/ai/chat`

请求体：

```json
{
  "scene": "knowledge_qa",
  "message": "熬夜对身体有什么影响？"
}
```

要求：
- 小程序端禁止：选择模型、切换 Provider、设置 temperature/tokens、传 apiKey/appId/endpoint
- AI UI 是“对话产品”，不是“模型调试器”

---

### 6) 风控与边界（必须实现）

1) 所有 AI 回复必须可被：
   - 日志记录（元数据）
   - 场景追踪（scene/strategy/provider 维度）
2) health 场景必须具备：
   - 非医疗声明
   - 拒绝诊断类问题（命中时给出拒答与引导）
3) Provider 切换不影响历史数据（历史日志需记录当时使用的 provider/strategy 标识）

---

### 7) 迁移（开发/测试阶段：不要求）

本仓库当前处于开发/测试阶段，允许清理历史配置与测试数据，因此 **不要求** 保留 v1 旧配置页面/接口，也不要求提供一键迁移能力。


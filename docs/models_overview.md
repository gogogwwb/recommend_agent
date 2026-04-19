# 数据模型概览

本文档概述了保险智能推荐Agent系统中定义的所有Pydantic数据模型。

## 模型组织结构

```
models/
├── __init__.py           # 模型导出
├── user.py              # 用户相关模型
├── product.py           # 产品相关模型
├── conversation.py      # 对话相关模型
├── compliance.py        # 合规相关模型
└── agent_state.py       # LangGraph状态模型
```

## 用户相关模型 (models/user.py)

### 枚举类型
- **MaritalStatus**: 婚姻状况 (single, married, divorced, widowed)
- **IncomeRange**: 收入区间 (low, medium_low, medium, medium_high, high)
- **RiskPreference**: 风险偏好 (conservative, balanced, aggressive)
- **HealthStatus**: 健康状况 (excellent, good, fair, poor)

### 数据模型
- **UserProfile**: 用户画像模型
  - 基本信息：年龄、职业、婚姻状况
  - 家庭结构：子女数量、被抚养人数量、家庭人数
  - 经济状况：收入区间、年收入
  - 风险偏好：风险偏好类型、风险评分
  - 健康状况：健康状态、病史、已有疾病
  - 地理位置：城市、省份
  - 包含字段验证（如子女数量与has_children一致性）

- **ExistingProduct**: 已有保障产品模型
  - 产品信息：产品ID、名称、类型
  - 保障信息：保额、保费、保障范围
  - 时间信息：购买日期、保障起止日期
  - 状态：是否有效

## 产品相关模型 (models/product.py)

### 辅助模型
- **PremiumRange**: 保费区间 (最低保费、最高保费)
- **AgeRange**: 年龄区间 (最小年龄、最大年龄)

### 核心模型
- **Product**: 保险产品模型
  - 基本信息：产品ID、名称、类型、保险公司
  - 保障信息：保障范围、保额范围、责任免除
  - 费率信息：保费区间、缴费期限、保障期限
  - 投保规则：年龄范围、职业限制、健康要求、地域限制
  - 产品特点：特点、优势、适用人群
  - 理赔信息：理赔流程、等待期、免赔额
  - 状态：是否可售、是否推荐产品
  - 向量化特征：用于RAG检索的embedding

- **CoverageGap**: 保障缺口分析模型
  - 各维度保障缺口：重疾险、医疗险、意外险、寿险
  - 当前保障情况：各类型当前保额
  - 推荐保障：各类型推荐保额
  - 分析说明：缺口分析、优先推荐

- **RecommendationResult**: 推荐结果模型
  - 推荐产品：Product对象
  - 推荐评分：排名、匹配分数、置信度
  - 推荐理由：解释、各维度匹配分数
  - 产品优势：适合原因、关键收益
  - 合规状态：是否通过合规检查、合规问题

## 对话相关模型 (models/conversation.py)

### 枚举类型
- **MessageRole**: 消息角色 (user, assistant, system)
- **IntentType**: 意图类型 (8种意图：咨询保障、比较产品、修改信息、确认推荐、提问、提供信息、闲聊、请求解释)
- **SessionStatus**: 会话状态 (active, background, completed, abandoned, archived)

### 数据模型
- **Message**: 消息模型
  - 基本信息：角色、内容、时间戳、消息ID
  - 意图和槽位：用户意图、提取的槽位（仅用户消息）
  - Agent信息：Agent名称、思考过程（仅助手消息）

- **SessionContext**: 会话上下文模型
  - 会话标识：会话ID、用户ID
  - 会话状态：状态、是否后台运行
  - 时间信息：创建时间、最后活跃时间、完成时间
  - 会话统计：对话轮数、总消息数

## 合规相关模型 (models/compliance.py)

### 枚举类型
- **ComplianceCheckType**: 合规检查类型 (age_check, occupation_check, health_check, region_check, income_check)
- **CheckResult**: 检查结果 (passed, failed, warning, manual_review)

### 数据模型
- **ComplianceCheck**: 合规检查模型
  - 检查信息：检查类型、检查结果、检查描述
  - 检查详情：未通过原因、建议
  - 检查数据：被检查的值、期望的值
  - 元数据：检查时间

- **ComplianceResult**: 合规检查结果汇总
  - 产品和用户：产品ID、用户ID
  - 总体结果：是否符合投保条件、总体检查结果
  - 详细检查：检查列表
  - 不通过原因：未通过的检查、原因
  - 建议：改进建议

- **DisclosureItem**: 信息披露项
  - 披露信息：标题、内容、是否必须披露、类别

- **DisclosureInfo**: 信息披露模型
  - 产品ID
  - 披露内容：保险责任、责任免除、犹豫期、费用说明
  - 详细披露项列表
  - 用户确认：是否已确认、确认时间
  - 元数据：生成时间、版本号

## LangGraph状态模型 (models/agent_state.py)

### 核心模型
- **AgentState**: LangGraph Agent状态模型 (TypedDict)
  - 对话管理：session_id, user_id, messages, turn_count
  - 用户画像：profile, profile_complete, risk_preference, risk_score, existing_coverage
  - 推荐相关：recommendation_candidates, recommendation_results, recommendation_generated, coverage_gap
  - 合规相关：compliance_checks, compliance_passed, disclosure_info
  - 意图和槽位：current_intent, slots, missing_slots
  - 上下文管理：full_context_prompt, compressed_history, user_preferences
  - 控制流：next_agent, current_agent, error, status
  - 会话管理：background_mode, saved_progress
  - 反馈和质量：user_feedback, feedback_reason, quality_score
  - 元数据：profile_change_history, recommendation_constraints, excluded_products

### 辅助函数
- **create_initial_state()**: 创建初始化的AgentState

### 常量
- **REQUIRED_SLOTS**: 必填槽位列表 (age, occupation, marital_status, income_range)
- **OPTIONAL_SLOTS**: 可选槽位列表 (has_children, children_count, etc.)
- **ALL_SLOTS**: 所有槽位列表

## 使用示例

### 创建用户画像
```python
from models import UserProfile, MaritalStatus, IncomeRange, RiskPreference

profile = UserProfile(
    age=30,
    occupation="软件工程师",
    marital_status=MaritalStatus.MARRIED,
    has_children=True,
    children_count=1,
    family_size=3,
    income_range=IncomeRange.MEDIUM_HIGH,
    annual_income=300000,
    risk_preference=RiskPreference.BALANCED
)
```

### 创建产品
```python
from models import Product, PremiumRange, AgeRange

product = Product(
    product_id="prod-001",
    product_name="康健一生重疾险",
    product_type="critical_illness",
    provider="平安保险",
    premium_range=PremiumRange(min_premium=5000, max_premium=15000),
    age_range=AgeRange(min_age=18, max_age=60)
)
```

### 创建消息
```python
from models import Message, MessageRole, IntentType

message = Message(
    role=MessageRole.USER,
    content="我想了解重疾险",
    intent=IntentType.CONSULT_COVERAGE,
    extracted_slots={"interested_product_type": "critical_illness"}
)
```

### 创建初始Agent状态
```python
from models import create_initial_state

state = create_initial_state(
    session_id="sess-001",
    user_id="user-001"
)
```

## 验证和测试

所有模型都包含：
- ✅ 字段验证（Pydantic validators）
- ✅ 类型检查（Python type hints）
- ✅ 序列化/反序列化支持（model_dump_json, model_validate_json）
- ✅ 示例数据（Config.json_schema_extra）
- ✅ 单元测试（tests/unit/test_models.py）

运行测试：
```bash
uv run pytest tests/unit/test_models.py -v
```

## 设计原则

1. **类型安全**: 使用Pydantic进行运行时类型验证
2. **可序列化**: 所有模型支持JSON序列化/反序列化
3. **文档化**: 每个字段都有description说明
4. **验证逻辑**: 关键字段包含自定义验证器
5. **示例数据**: 每个模型都提供使用示例
6. **模块化**: 按功能领域组织模型文件

## 下一步

- Task 3.2: 编写数据模型属性测试（用户画像序列化往返一致性）
- Task 3.3: 编写数据模型属性测试（产品数据序列化往返一致性）
- Task 3.4: 实现SQLAlchemy ORM模型

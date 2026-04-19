# LangGraph 1.x 新特性替代方案分析

## 概述

本文档分析LangGraph 1.x的三个新特性是否可以替代当前的三层内存架构设计：

1. **Store API** → 替代三层存储（Hot/Warm/Cold）？
2. **语义检索** → 替代手动压缩？
3. **子图Schema** → 替代上下文隔离？

---

## 1. Store API vs 三层存储架构

### Store API 是什么？

LangGraph 1.x的Store API提供了**持久化键值存储**，用于在对话会话之间共享和检索信息。

**核心特性**：
- 跨会话的持久化存储
- 命名空间隔离（namespace）
- 支持搜索和过滤
- 与LangGraph状态分离

**典型用例**：
```python
from langgraph.store import InMemoryStore

# 创建store
store = InMemoryStore()

# 存储用户画像（跨会话持久化）
store.put(
    namespace=["users", user_id],
    key="profile",
    value={
        "age": 30,
        "income_range": "100k-200k",
        "risk_preference": "balanced"
    }
)

# 检索用户画像
profile = store.get(namespace=["users", user_id], key="profile")
```

### 能否替代三层存储？

#### ❌ **不能完全替代，但可以互补**

**原因分析**：

| 维度 | 三层存储架构 | Store API |
|------|-------------|-----------|
| **设计目标** | 对话历史的分层管理和压缩 | 跨会话的结构化数据持久化 |
| **数据类型** | 对话消息流（时序数据） | 键值对（结构化数据） |
| **压缩机制** | 智能压缩对话历史（3000 tokens触发） | 无压缩机制 |
| **时效性** | 热数据（Redis 1小时TTL）<br>温数据（PostgreSQL）<br>冷数据（S3归档） | 持久化存储，无自动过期 |
| **检索方式** | 按时间顺序检索最近N条消息 | 按namespace和key检索 |
| **适用场景** | 对话上下文管理 | 用户画像、配置、知识库 |

**具体对比**：

**1. 对话历史管理**
- **三层存储**：✅ 专门设计用于管理对话消息流
  - 热数据层：最近10条消息（Redis，快速访问）
  - 温数据层：历史消息压缩（PostgreSQL，节省token）
  - 冷数据层：长期归档（S3，低成本）
  
- **Store API**：❌ 不适合对话历史管理
  - 没有时序数据的优化
  - 没有自动压缩机制
  - 没有分层存储策略

**2. 用户画像存储**
- **三层存储**：⚠️ 可以存储，但不是最优
  - 用户画像存储在PostgreSQL的`user_profiles`表
  - 需要手动管理数据库schema
  
- **Store API**：✅ 非常适合
  - 天然支持结构化数据存储
  - 命名空间隔离（`["users", user_id]`）
  - 跨会话持久化

**3. 压缩历史存储**
- **三层存储**：✅ 专门设计
  - `compressed_history`字段存储压缩后的对话摘要
  - 支持批次追加（每次压缩追加新批次）
  
- **Store API**：⚠️ 可以存储，但缺少压缩逻辑
  - 可以存储压缩后的文本
  - 但压缩逻辑仍需自己实现

### 推荐方案：混合使用

**最佳实践**：

```python
# 1. 使用三层存储管理对话历史
hot_layer = HotDataLayer(redis_client, session_id)
warm_layer = WarmDataLayer(db_session, session_id)

# 2. 使用Store API管理用户画像和配置
store = InMemoryStore()

# 存储用户画像（跨会话）
store.put(
    namespace=["users", user_id],
    key="profile",
    value={
        "age": 30,
        "income_range": "100k-200k",
        "family_structure": "married_with_children",
        "risk_preference": "balanced"
    }
)

# 存储系统配置（跨会话）
store.put(
    namespace=["config"],
    key="compression_threshold",
    value=3000
)

# 3. 在Agent中组合使用
async def advisor_agent(state: AdvisorInput) -> dict:
    # 从Store API获取用户画像
    user_profile = store.get(
        namespace=["users", state["user_id"]],
        key="profile"
    )
    
    # 从三层存储获取对话上下文
    hot_messages = await hot_layer.get_hot_messages()
    full_context = await warm_layer.get_full_context_for_agent(
        hot_messages,
        target_agent="RecommendationAgent"
    )
    
    # 生成推荐
    recommendations = generate_recommendations(user_profile, full_context)
    
    return {"recommendation_results": recommendations}
```

**优势**：
- ✅ Store API管理结构化数据（用户画像、配置）
- ✅ 三层存储管理对话历史（时序数据、压缩）
- ✅ 各司其职，发挥各自优势

---

## 2. 语义检索 vs 手动压缩

### 语义检索是什么？

LangGraph 1.x支持**语义检索**（Semantic Search），可以基于向量相似度检索相关的历史对话。

**核心特性**：
- 将对话消息向量化（embedding）
- 基于语义相似度检索相关消息
- 无需手动压缩，自动筛选相关内容

**典型用例**：
```python
from langgraph.store import InMemoryStore
from langchain_openai import OpenAIEmbeddings

# 创建带embedding的store
store = InMemoryStore(index={"embed": OpenAIEmbeddings()})

# 存储对话消息（自动向量化）
store.put(
    namespace=["conversations", session_id],
    key=f"message_{i}",
    value={"role": "user", "content": "我想了解重疾险"},
    index=["embed"]  # 自动向量化
)

# 语义检索相关消息
current_query = "推荐适合我的保险产品"
relevant_messages = store.search(
    namespace_prefix=["conversations", session_id],
    query=current_query,
    limit=10
)
```

### 能否替代手动压缩？

#### ⚠️ **部分替代，但各有优劣**

**对比分析**：

| 维度 | 手动压缩 | 语义检索 |
|------|---------|---------|
| **核心思想** | 将历史对话压缩成摘要 | 检索语义相关的历史消息 |
| **Token消耗** | 极低（压缩比90%） | 中等（检索到的原始消息） |
| **信息完整性** | 可能丢失细节 | 保留原始消息 |
| **实现复杂度** | 高（需要LLM压缩） | 低（向量检索） |
| **响应速度** | 快（读取压缩文本） | 快（向量检索） |
| **成本** | 压缩时消耗LLM token | 向量化和存储成本 |
| **适用场景** | 长对话历史（100+轮） | 中短对话（<50轮） |

**详细对比**：

**1. Token消耗**
- **手动压缩**：✅ 极低
  - 3000 tokens → 300 tokens（压缩比90%）
  - 100轮对话：~30,000 tokens → ~3,000 tokens
  
- **语义检索**：⚠️ 中等
  - 检索Top-10相关消息：~3,000 tokens
  - 但无法处理100轮对话（检索不到所有信息）

**2. 信息完整性**
- **手动压缩**：⚠️ 可能丢失细节
  - 压缩过程可能丢失非关键信息
  - 但保留关键槽位（age, income等）
  
- **语义检索**：✅ 保留原始消息
  - 检索到的消息是原始内容
  - 但可能遗漏不相关但重要的信息

**3. 长对话处理**
- **手动压缩**：✅ 适合长对话
  - 100轮对话压缩后仍可管理
  - 压缩历史累积缓慢（每5轮+300 tokens）
  
- **语义检索**：❌ 不适合长对话
  - 检索Top-K无法覆盖所有历史
  - 向量数据库存储成本随对话增长

**4. 实时性**
- **手动压缩**：⚠️ 异步压缩
  - 压缩需要调用LLM（1-2秒）
  - 但异步执行，不阻塞主流程
  
- **语义检索**：✅ 实时检索
  - 向量检索速度快（<100ms）
  - 无需等待压缩完成

### 推荐方案：混合使用

**最佳实践**：

```python
# 1. 短期对话（<20轮）：使用语义检索
if turn_count < 20:
    # 语义检索相关消息
    relevant_messages = store.search(
        namespace_prefix=["conversations", session_id],
        query=current_user_message,
        limit=10
    )
    
    context = format_messages(relevant_messages)

# 2. 长期对话（≥20轮）：使用手动压缩
else:
    # 获取压缩历史 + 最近消息
    hot_messages = await hot_layer.get_hot_messages()
    full_context = await warm_layer.get_full_context_for_agent(
        hot_messages,
        target_agent="RecommendationAgent"
    )
    
    context = full_context

# 3. 混合策略：语义检索 + 压缩历史
# 对于特定场景（如用户询问历史信息）
if user_intent == "recall_history":
    # 语义检索历史中的相关片段
    relevant_history = store.search(
        namespace_prefix=["conversations", session_id],
        query=current_user_message,
        limit=5
    )
    
    # 组合压缩历史和检索结果
    context = f"""
[压缩历史摘要]
{compressed_history}

[相关历史片段]
{format_messages(relevant_history)}

[最近对话]
{format_messages(hot_messages)}
"""
```

**使用场景建议**：

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 短对话（<20轮） | 语义检索 | 简单高效，无需压缩 |
| 长对话（≥20轮） | 手动压缩 | Token消耗低，信息完整 |
| 历史回溯查询 | 语义检索 | 精准定位相关片段 |
| 用户画像收集 | 手动压缩 | 保留关键槽位 |
| 实时推荐 | 语义检索 | 快速检索相关信息 |

---

## 3. 子图Schema vs 上下文隔离

### 子图Schema是什么？

LangGraph 1.x支持**子图**（Subgraph），可以将复杂的Agent系统拆分为多个独立的子图，每个子图有自己的State Schema。

**核心特性**：
- 每个子图定义自己的State类型
- 子图之间通过明确的接口通信
- 父图和子图的State可以不同

**典型用例**：
```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# 子图1：Profile Collection Subgraph
class ProfileState(TypedDict):
    user_input: str
    user_profile: dict
    slots: dict

def create_profile_subgraph():
    builder = StateGraph(ProfileState)
    builder.add_node("extract_slots", extract_slots_node)
    builder.add_node("validate_profile", validate_profile_node)
    builder.add_edge(START, "extract_slots")
    builder.add_edge("extract_slots", "validate_profile")
    builder.add_edge("validate_profile", END)
    return builder.compile()

# 子图2：Recommendation Subgraph
class RecommendationState(TypedDict):
    user_profile: dict  # 只接收user_profile，不接收对话历史
    recommendations: list
    explanations: list

def create_recommendation_subgraph():
    builder = StateGraph(RecommendationState)
    builder.add_node("match_products", match_products_node)
    builder.add_node("generate_explanations", generate_explanations_node)
    builder.add_edge(START, "match_products")
    builder.add_edge("match_products", "generate_explanations")
    builder.add_edge("generate_explanations", END)
    return builder.compile()

# 父图：Main Graph
class MainState(TypedDict):
    conversation_history: list
    user_profile: dict
    recommendations: list

def create_main_graph():
    builder = StateGraph(MainState)
    
    # 添加子图作为节点
    profile_subgraph = create_profile_subgraph()
    recommendation_subgraph = create_recommendation_subgraph()
    
    builder.add_node("profile_collection", profile_subgraph)
    builder.add_node("recommendation", recommendation_subgraph)
    
    builder.add_edge(START, "profile_collection")
    builder.add_edge("profile_collection", "recommendation")
    builder.add_edge("recommendation", END)
    
    return builder.compile()
```

### 能否替代上下文隔离？

#### ✅ **可以替代，且更优雅**

**对比分析**：

| 维度 | 上下文隔离（Context Isolation） | 子图Schema |
|------|-------------------------------|-----------|
| **核心思想** | 过滤消息，只传递相关对话 | 子图定义独立State，结构上隔离 |
| **隔离层面** | 消息层面（运行时过滤） | 数据结构层面（编译时隔离） |
| **实现方式** | `AgentContextScope.filter_messages()` | 子图State定义 |
| **类型安全** | ⚠️ 运行时检查 | ✅ 编译时类型检查 |
| **可维护性** | ⚠️ 需要维护过滤规则 | ✅ State定义即文档 |
| **性能** | ⚠️ 运行时过滤开销 | ✅ 无运行时开销 |

**详细对比**：

**1. 类型安全**
- **上下文隔离**：⚠️ 运行时过滤
  ```python
  # 运行时过滤，类型检查弱
  filtered_messages = AgentContextScope.filter_messages(
      messages,
      target_agent="RecommendationAgent"
  )
  # 如果过滤规则错误，只能在运行时发现
  ```

- **子图Schema**：✅ 编译时类型检查
  ```python
  # RecommendationState不包含conversation_history
  class RecommendationState(TypedDict):
      user_profile: dict
      recommendations: list
  
  # 如果尝试访问conversation_history，IDE会报错
  def recommendation_node(state: RecommendationState):
      # state["conversation_history"]  # 类型错误！
      user_profile = state["user_profile"]  # ✅ 正确
  ```

**2. 可维护性**
- **上下文隔离**：⚠️ 需要维护过滤规则
  ```python
  # 需要在单独的配置中维护
  AGENT_VISIBILITY = {
      "RecommendationAgent": {
          "visible_agents": ["ProfileCollectionAgent", "RecommendationAgent"],
          "visible_intents": [IntentType.CONSULT_COVERAGE, ...],
          "exclude_intents": [IntentType.CHITCHAT],
      }
  }
  # 规则和Agent实现分离，容易不一致
  ```

- **子图Schema**：✅ State定义即文档
  ```python
  # State定义清晰表达了数据依赖
  class RecommendationState(TypedDict):
      """
      Recommendation Subgraph State
      
      只需要：
      - user_profile: 用户画像
      - recommendations: 推荐结果
      
      不需要：
      - conversation_history: 对话历史（已在Profile阶段提取）
      """
      user_profile: dict
      recommendations: list
  ```

**3. 性能**
- **上下文隔离**：⚠️ 运行时过滤开销
  ```python
  # 每次调用都需要过滤
  filtered_messages = AgentContextScope.filter_messages(
      messages,  # 可能有100+条消息
      target_agent="RecommendationAgent"
  )
  # 时间复杂度：O(n)，n为消息数量
  ```

- **子图Schema**：✅ 无运行时开销
  ```python
  # 子图只接收定义的字段，无需过滤
  def recommendation_subgraph(state: RecommendationState):
      # state中只有user_profile和recommendations
      # 没有conversation_history，无需过滤
      pass
  ```

**4. 灵活性**
- **上下文隔离**：✅ 灵活
  - 可以动态调整过滤规则
  - 支持复杂的过滤逻辑（intent、agent_name等）

- **子图Schema**：⚠️ 静态
  - State定义是静态的
  - 但可以通过父图传递不同的数据实现灵活性

### 推荐方案：使用子图Schema

**最佳实践**：

```python
# 1. 定义子图State（替代上下文隔离）

# Profile Collection Subgraph
class ProfileState(TypedDict):
    """
    Profile Collection只需要：
    - conversation_history: 对话历史（用于提取槽位）
    - user_profile: 用户画像（输出）
    """
    conversation_history: Annotated[list, add_messages]
    user_profile: Optional[dict]
    slots: dict

# Recommendation Subgraph
class RecommendationState(TypedDict):
    """
    Recommendation只需要：
    - user_profile: 用户画像（输入，从Profile阶段传递）
    - recommendations: 推荐结果（输出）
    
    注意：不需要conversation_history！
    """
    user_profile: dict
    risk_assessment: dict
    coverage_gap: dict
    recommendations: list
    explanations: list

# Compliance Subgraph
class ComplianceState(TypedDict):
    """
    Compliance只需要：
    - user_profile: 用户画像
    - recommendations: 待验证的推荐
    - compliance_checks: 合规检查结果（输出）
    """
    user_profile: dict
    recommendations: list
    compliance_checks: list
    disclosure_info: str

# 2. 创建子图

def create_profile_subgraph():
    builder = StateGraph(ProfileState)
    builder.add_node("extract_slots", extract_slots_node)
    builder.add_node("build_profile", build_profile_node)
    builder.add_edge(START, "extract_slots")
    builder.add_edge("extract_slots", "build_profile")
    builder.add_edge("build_profile", END)
    return builder.compile()

def create_recommendation_subgraph():
    builder = StateGraph(RecommendationState)
    builder.add_node("match_products", match_products_node)
    builder.add_node("analyze_gap", analyze_gap_node)
    builder.add_node("generate_explanations", generate_explanations_node)
    builder.add_edge(START, "match_products")
    builder.add_edge("match_products", "analyze_gap")
    builder.add_edge("analyze_gap", "generate_explanations")
    builder.add_edge("generate_explanations", END)
    return builder.compile()

def create_compliance_subgraph():
    builder = StateGraph(ComplianceState)
    builder.add_node("check_eligibility", check_eligibility_node)
    builder.add_node("generate_disclosure", generate_disclosure_node)
    builder.add_edge(START, "check_eligibility")
    builder.add_edge("check_eligibility", "generate_disclosure")
    builder.add_edge("generate_disclosure", END)
    return builder.compile()

# 3. 创建主图（组合子图）

class MainState(TypedDict):
    """
    Main State包含所有数据
    但子图只能访问自己State定义的字段
    """
    conversation_history: Annotated[list, add_messages]
    user_profile: Optional[dict]
    recommendations: list
    compliance_checks: list
    session_id: str

def create_main_graph():
    builder = StateGraph(MainState)
    
    # 添加子图
    builder.add_node("profile", create_profile_subgraph())
    builder.add_node("recommendation", create_recommendation_subgraph())
    builder.add_node("compliance", create_compliance_subgraph())
    
    # 定义流程
    builder.add_edge(START, "profile")
    builder.add_edge("profile", "recommendation")
    builder.add_edge("recommendation", "compliance")
    builder.add_edge("compliance", END)
    
    return builder.compile()

# 4. 使用（自动隔离）

graph = create_main_graph()

initial_state = {
    "conversation_history": [
        Message(role="user", content="我想了解重疾险")
    ],
    "user_profile": None,
    "recommendations": [],
    "compliance_checks": [],
    "session_id": "session_123"
}

# 执行graph
result = await graph.ainvoke(initial_state)

# Profile子图只看到conversation_history
# Recommendation子图只看到user_profile（看不到conversation_history）
# Compliance子图只看到user_profile和recommendations
```

**优势**：
- ✅ **类型安全**：编译时检查，IDE支持
- ✅ **清晰的数据流**：State定义即文档
- ✅ **无运行时开销**：结构上隔离，无需过滤
- ✅ **易于测试**：每个子图可以独立测试
- ✅ **易于维护**：修改子图State不影响其他子图

---

## 总结对比

| 特性 | 当前设计 | LangGraph 1.x新特性 | 推荐方案 |
|------|---------|-------------------|---------|
| **对话历史管理** | 三层存储（Hot/Warm/Cold） | Store API | **保留三层存储**<br>Store API用于结构化数据 |
| **历史压缩** | 手动压缩（LLM） | 语义检索 | **混合使用**<br>短对话用语义检索<br>长对话用手动压缩 |
| **上下文隔离** | Context Isolation（运行时过滤） | 子图Schema | **使用子图Schema**<br>更优雅、类型安全 |

---

## 最终推荐架构

```python
# 1. 使用子图Schema实现上下文隔离（替代Context Isolation）
class ProfileState(TypedDict):
    conversation_history: Annotated[list, add_messages]
    user_profile: Optional[dict]

class RecommendationState(TypedDict):
    user_profile: dict  # 只接收user_profile，不接收conversation_history
    recommendations: list

# 2. 使用Store API管理结构化数据（补充三层存储）
store = InMemoryStore()
store.put(namespace=["users", user_id], key="profile", value=user_profile)

# 3. 保留三层存储管理对话历史（Store API无法替代）
hot_layer = HotDataLayer(redis_client, session_id)
warm_layer = WarmDataLayer(db_session, session_id)

# 4. 混合使用手动压缩和语义检索
if turn_count < 20:
    # 短对话：语义检索
    relevant_messages = store.search(query=current_message, limit=10)
else:
    # 长对话：手动压缩
    full_context = await warm_layer.get_full_context_for_agent(hot_messages)
```

**核心结论**：
- ✅ **子图Schema** → 完全替代上下文隔离（更优）
- ⚠️ **语义检索** → 部分替代手动压缩（混合使用）
- ❌ **Store API** → 不能替代三层存储（互补使用）

---

## 实施建议

### 优先级1：使用子图Schema替代上下文隔离

**原因**：
- 类型安全
- 无运行时开销
- 易于维护

**实施步骤**：
1. 定义子图State（ProfileState, RecommendationState, ComplianceState）
2. 创建子图（create_profile_subgraph, create_recommendation_subgraph等）
3. 在主图中组合子图
4. 删除Context Isolation相关代码

### 优先级2：引入Store API管理结构化数据

**原因**：
- 简化用户画像管理
- 跨会话持久化
- 与LangGraph集成

**实施步骤**：
1. 创建Store实例
2. 迁移用户画像存储到Store API
3. 保留三层存储用于对话历史

### 优先级3：评估语义检索的适用场景

**原因**：
- 短对话场景可以简化
- 长对话仍需手动压缩

**实施步骤**：
1. 在短对话场景（<20轮）试用语义检索
2. 对比token消耗和响应质量
3. 根据结果决定是否全面采用

---

## 参考资料

- [LangGraph Store API文档](https://langchain-ai.github.io/langgraph/concepts/persistence/#store)
- [LangGraph子图文档](https://langchain-ai.github.io/langgraph/how-tos/subgraph/)
- [LangGraph语义检索示例](https://langchain-ai.github.io/langgraph/how-tos/semantic-search/)

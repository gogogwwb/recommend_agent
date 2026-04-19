# Design Document: 保险智能推荐Agent系统

## Overview

保险智能推荐Agent系统是一个基于多Agent架构的智能对话系统，通过自然语言交互理解C端用户的保险需求，并提供个性化的保险产品推荐。系统采用**LangGraph 1.0.0**实现多Agent协作，使用**子图(Subgraph)架构**实现Agent隔离，使用**Store API**管理用户画像，使用FAISS向量数据库进行RAG（检索增强生成），使用PostgreSQL存储结构化数据，通过FastAPI + SSE提供实时流式响应。

### 核心目标

1. **智能对话交互**：通过多轮对话自然地收集用户信息，避免冗长表单填写
2. **个性化推荐**：基于用户画像、风险偏好、已有保障生成精准推荐
3. **可解释性**：为每个推荐提供清晰的理由和依据
4. **合规性**：满足保险行业监管要求，确保信息披露完整
5. **实时响应**：通过SSE流式返回，提升用户体验

### 技术栈

- **多Agent框架**：LangGraph 1.0.0 + LangChain 1.0.0
- **State管理**：子图Schema + Store API (PostgresStore) + PostgresSaver (Checkpointer)
- **向量数据库**：FAISS（用于产品知识库检索）
- **关系数据库**：PostgreSQL（用于结构化数据存储 + Store API + Checkpointer）
- **后端框架**：FastAPI + SSE
- **Python环境管理**：uv
- **LLM**：支持OpenAI API兼容接口
- **Embedding模型**：用于向量化产品知识和用户查询

## Architecture

### 系统架构图

```mermaid
graph TB
    Client[客户端] -->|HTTP/SSE| API[FastAPI API Layer]
    API --> MainGraph[Main Graph - Orchestrator]
    
    MainGraph --> ProfileSub[Profile Subgraph]
    MainGraph --> RecommendSub[Recommendation Subgraph]
    MainGraph --> ComplianceSub[Compliance Subgraph]
    
    ProfileSub -->|ProfileState| StateTransform[State Transformation]
    RecommendSub -->|RecommendationState| StateTransform
    ComplianceSub -->|ComplianceState| StateTransform
    
    StateTransform --> Store[Store API - PostgresStore]
    Store -->|User Profile| ProfileSub
    Store -->|User Profile| RecommendSub
    
    RecommendSub --> RAG[RAG Module]
    RAG --> FAISS[(FAISS Vector DB)]
    RAG --> Embedding[Embedding Model]
    
    RecommendSub --> Matcher[Product Matcher]
    Matcher --> PG[(PostgreSQL)]
    
    ComplianceSub --> Rules[Compliance Rules Engine]
    Rules --> PG
    
    MainGraph --> Checkpointer[PostgresSaver - Checkpointer]
    Checkpointer --> PG
```

### 核心架构变更（LangGraph 1.0.0）

#### 1. 子图架构替代Context Isolation

**旧方案（Context Isolation）**：
- 运行时过滤消息，只传递相关对话
- 需要维护复杂的过滤规则
- 运行时开销

**新方案（Subgraph Schema）**：
- 每个Agent是独立子图，拥有自己的State Schema
- 结构上隔离，无需运行时过滤
- 类型安全，编译时检查

```python
# Profile Subgraph State - 需要对话历史
class ProfileState(TypedDict):
    messages: Annotated[list, add_messages]  # 对话历史
    user_profile: Optional[dict]  # 输出：用户画像
    slots: dict  # 提取的槽位

# Recommendation Subgraph State - 只需要结构化数据
class RecommendationState(TypedDict):
    user_profile: dict  # 输入：从Store API获取
    recommendations: list  # 输出：推荐结果
    explanations: list
    # 注意：没有messages字段！

# Compliance Subgraph State - 只需要验证数据
class ComplianceState(TypedDict):
    user_profile: dict
    recommendations: list
    compliance_checks: list  # 输出
```

**优势**：
- ✅ 类型安全：编译时检查，IDE支持
- ✅ 清晰的数据流：State定义即文档
- ✅ 无运行时开销：结构上隔离
- ✅ 易于测试：每个子图可独立测试

#### 2. Store API管理用户画像

**用途**：跨会话持久化用户画像和关键槽位

```python
from langgraph.store.postgres import PostgresStore

# 初始化Store（使用现有PostgreSQL）
store = PostgresStore.from_conn_string(
    "postgresql://localhost/insurance_db"
)

# 存储用户画像
store.put(
    namespace=("users", user_id),
    key="profile",
    value={
        "age": 30,
        "income_range": "100k-200k",
        "family_structure": "married_with_children",
        "risk_preference": "balanced",
        "existing_coverage": [...]
    }
)

# 检索用户画像
profile = store.get(namespace=("users", user_id), key="profile")
```

**关键槽位**（从对话中提取并存储）：
- `age`
- `income_range`
- `family_structure`
- `occupation`
- `risk_preference`
- `existing_coverage`
- `health_status`

**数据流**：
1. Profile Agent从对话中提取槽位
2. 槽位立即存储到Store API
3. 对话历史存储到三层存储
4. Recommendation Agent从Store API读取画像（不需要对话历史）

#### 3. PostgresSaver管理会话状态

**用途**：会话内状态持久化和恢复

```python
from langgraph.checkpoint.postgres import PostgresSaver

# 初始化Checkpointer（使用现有PostgreSQL）
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://localhost/insurance_db"
)
checkpointer.setup()  # 创建必要的表

# 编译图时配置checkpointer
graph = create_main_graph(store)
app = graph.compile(checkpointer=checkpointer)

# 调用时指定thread_id
config = {
    "configurable": {
        "thread_id": session_id  # PostgresSaver自动管理状态
    }
}

result = await app.ainvoke(input_state, config)

# 恢复会话
state = await app.aget_state(config)
```

**PostgresSaver提供的功能**：
- ✅ 会话内消息持久化（自动管理messages字段）
- ✅ 状态快照和恢复
- ✅ 时间旅行调试
- ✅ 会话回滚
- ✅ 并发控制

**关键决策**：使用PostgresSaver替代HotDataLayer和WarmDataLayer

**原因**：
1. **功能重叠**：PostgresSaver已提供消息持久化和会话恢复
2. **简化架构**：避免手写压缩逻辑，保持上下文连贯性
3. **原生集成**：PostgresSaver与LangGraph深度集成，无需额外代码
4. **调试友好**：支持时间旅行调试，便于问题追溯

**Token优化策略**（替代手写压缩）：
- 利用现代LLM的长上下文窗口（128k+ tokens）
- 在节点中控制消息数量（保留最近N条）
- 可选：超长对话时使用语义检索（FAISS）
    
    ComplianceAgent --> Rules[Compliance Rules Engine]
    Rules --> PG
```

### 三Agent子图架构设计

基于LangGraph 1.0.0的子图设计，系统包含3个专门化Agent子图：

#### 1. Profile Collection Subgraph（画像收集子图）

**State Schema**：
```python
class ProfileState(TypedDict):
    """Profile Collection只需要对话历史和槽位"""
    messages: Annotated[list, add_messages]  # 对话历史
    user_id: str
    session_id: str
    user_profile: Optional[dict]  # 输出
    slots: dict  # 提取的槽位
```

**职责**：
- 引导用户提供个人信息（家庭结构、年龄、职业、收入）
- 评估用户风险偏好
- 收集已有保障信息
- 识别用户意图和提取槽位信息
- 管理多轮对话流程
- **处理闲聊和偏离主题的对话**
- **将提取的槽位存储到Store API**

**输入**：用户消息、当前对话上下文
**输出**：结构化的用户画像、风险偏好评估、已有保障分析

**关键能力**：
- 意图识别（8种以上意图类型 + 闲聊识别）
- 槽位填充和验证
- 信息补全和澄清
- 对话状态管理
- **闲聊检测与引导**
- **Store API集成**

#### 2. Recommendation Subgraph（推荐子图）

**State Schema**：
```python
class RecommendationState(TypedDict):
    """Recommendation只需要结构化数据，不需要对话历史"""
    user_id: str
    session_id: str
    user_profile: dict  # 从Store API读取
    recommendations: list  # 输出
    explanations: list
```

**职责**：
- **从Store API读取用户画像**（不需要对话历史）
- 基于用户画像匹配保险产品
- 生成个性化推荐列表（3-5个产品）
- 为每个推荐生成可解释的理由
- 分析保障缺口
- 提供产品对比功能
- 确保推荐多样性

**输入**：完整的用户画像（从Store API）、风险偏好、已有保障
**输出**：推荐产品列表、推荐理由、保障缺口分析

**关键能力**：
- RAG检索（从FAISS向量库检索相关产品）
- 特征匹配和评分
- 推荐解释生成
- 多样性控制
- **Store API读取**

#### 3. Compliance Subgraph（合规子图）

**State Schema**：
```python
class ComplianceState(TypedDict):
    """Compliance只需要验证数据"""
    user_id: str
    session_id: str
    user_profile: dict
    recommendations: list
    compliance_checks: list  # 输出
    disclosure_info: str
```

**职责**：
- 验证用户是否符合产品投保条件
- 检查年龄、健康状况、职业限制
- 生成必要的信息披露内容
- 记录合规检查结果
- 过滤不可用产品

**输入**：用户画像、候选推荐产品
**输出**：合规检查结果、披露信息、过滤后的推荐列表

**关键能力**：
- 规则引擎执行
- 投保条件验证
- 信息披露生成
- 审计日志记录

### LangGraph子图状态流程

```mermaid
stateDiagram-v2
    [*] --> Start
    Start --> ProfileSubgraph: 用户开始对话
    
    state ProfileSubgraph {
        [*] --> ExtractSlots
        ExtractSlots --> StoreToAPI: 提取槽位
        StoreToAPI --> ValidateProfile: 存储到Store API
        ValidateProfile --> [*]: 画像完整
        ValidateProfile --> ExtractSlots: 信息不完整
    }
    
    ProfileSubgraph --> RecommendationSubgraph: 画像收集完成
    
    state RecommendationSubgraph {
        [*] --> LoadProfile
        LoadProfile --> MatchProducts: 从Store API加载
        MatchProducts --> GenerateExplanations
        GenerateExplanations --> [*]
    }
    
    RecommendationSubgraph --> ComplianceSubgraph: 生成候选推荐
    
    state ComplianceSubgraph {
        [*] --> CheckEligibility
        CheckEligibility --> FilterProducts
        FilterProducts --> GenerateDisclosure
        GenerateDisclosure --> [*]
    }
    
    ComplianceSubgraph --> StreamResponse: 合规检查完成
    
    StreamResponse --> UserFeedback: 流式返回推荐结果
    
    UserFeedback --> ProductComparison: 用户请求对比
    UserFeedback --> ModifyProfile: 用户修改信息
    UserFeedback --> [*]: 用户确认或结束
    
    ProductComparison --> StreamResponse: 返回对比结果
    ModifyProfile --> ProfileSubgraph: 重新收集信息
```

### 主图与子图集成

```python
# 主图State - 包含所有数据
class MainState(TypedDict):
    """Main Graph State - 包含所有数据"""
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    user_profile: Optional[dict]
    recommendations: list
    compliance_checks: list

# 创建主图
def create_main_graph(store):
    """创建主图，集成子图"""
    
    # 创建子图
    profile_subgraph = create_profile_subgraph(store)
    recommendation_subgraph = create_recommendation_subgraph(store)
    compliance_subgraph = create_compliance_subgraph(store)
    
    # 包装子图为节点（转换State）
    async def profile_node(state: MainState):
        """Profile子图节点 - State转换"""
        # 转换MainState → ProfileState
        profile_input = {
            "messages": state["messages"],
            "user_id": state["user_id"],
            "session_id": state["session_id"],
            "user_profile": state.get("user_profile"),
            "slots": {}
        }
        
        # 调用子图
        result = await profile_subgraph.ainvoke(profile_input)
        
        # 转换ProfileState → MainState
        return {
            "user_profile": result["user_profile"]
        }
    
    async def recommendation_node(state: MainState):
        """Recommendation子图节点 - State转换"""
        # 转换MainState → RecommendationState
        rec_input = {
            "user_id": state["user_id"],
            "session_id": state["session_id"],
            "user_profile": state["user_profile"],
            "recommendations": [],
            "explanations": []
        }
        
        # 调用子图
        result = await recommendation_subgraph.ainvoke(rec_input)
        
        # 转换RecommendationState → MainState
        return {
            "recommendations": result["recommendations"]
        }
    
    async def compliance_node(state: MainState):
        """Compliance子图节点 - State转换"""
        # 转换MainState → ComplianceState
        compliance_input = {
            "user_id": state["user_id"],
            "session_id": state["session_id"],
            "user_profile": state["user_profile"],
            "recommendations": state["recommendations"],
            "compliance_checks": [],
            "disclosure_info": ""
        }
        
        # 调用子图
        result = await compliance_subgraph.ainvoke(compliance_input)
        
        # 转换ComplianceState → MainState
        return {
            "compliance_checks": result["compliance_checks"]
        }
    
    # 构建主图
    builder = StateGraph(MainState)
    builder.add_node("profile", profile_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("compliance", compliance_node)
    
    builder.add_edge(START, "profile")
    builder.add_edge("profile", "recommendation")
    builder.add_edge("recommendation", "compliance")
    builder.add_edge("compliance", END)
    
    return builder.compile()
```

### Agent协作机制

#### 架构模式：主子架构（Supervisor Pattern）

系统采用**主子架构**，由Orchestrator Agent作为主控节点（Supervisor），三个专门化Agent作为子节点（Workers）。

**主控节点（Orchestrator Agent）职责**：
- 接收用户输入并路由到合适的子Agent
- 维护全局对话状态和流程控制
- 监控子Agent执行状态和性能
- 处理子Agent之间的冲突
- 决策下一步执行哪个Agent或结束对话

**子节点（Worker Agents）职责**：
- 专注于各自领域的任务执行
- 读取State中的输入数据，更新输出数据
- 向Orchestrator报告执行状态（成功/失败/需要人工介入）
- 不直接与其他子Agent通信，所有协调通过Orchestrator

**为什么选择主子架构而非平等架构**：
1. **清晰的控制流**：避免Agent之间的循环依赖和死锁
2. **集中式监控**：便于追踪对话流程和诊断问题
3. **冲突解决**：由Orchestrator统一处理Agent之间的矛盾
4. **扩展性**：添加新Agent只需修改Orchestrator路由逻辑

#### 任务分发机制

**分发依据**：
```python
class TaskRouter:
    def route_next_agent(self, state: AgentState) -> str:
        """基于状态和规则决定下一个Agent"""
        
        # 1. 检查是否有错误需要处理
        if state.error:
            return self._handle_error_recovery(state)
        
        # 2. 检查用户意图，可能需要跳转流程
        if state.current_intent == "modify_info":
            return "ProfileCollectionAgent"
        elif state.current_intent == "compare_products":
            return "RecommendationAgent"  # 直接跳到对比功能
        
        # 3. 按标准流程顺序执行
        if not state.profile_complete:
            return "ProfileCollectionAgent"
        elif not state.recommendation_generated:
            return "RecommendationAgent"
        elif not state.compliance_checked:
            return "ComplianceAgent"
        else:
            # 4. 检查是否需要重新推荐
            if state.user_feedback == "negative":
                state.recommendation_generated = False
                return "RecommendationAgent"
            return "END"
    
    def _handle_error_recovery(self, state: AgentState) -> str:
        """错误恢复策略"""
        if state.error.agent == "RecommendationAgent":
            # 推荐失败，尝试放宽条件
            state.recommendation_constraints.relax()
            return "RecommendationAgent"
        elif state.error.agent == "ComplianceAgent":
            # 合规检查失败，返回用户说明
            return "END"
        else:
            return "END"
```

**分发策略**：
1. **顺序执行**：默认按 Profile → Recommendation → Compliance 顺序
2. **意图驱动跳转**：根据用户意图动态调整流程（如用户要求修改信息，跳回Profile Agent）
3. **错误驱动重试**：子Agent失败时，Orchestrator决定是否重试或降级
4. **反馈驱动迭代**：用户不满意推荐时，重新执行推荐流程

#### 监控方式

**1. 执行状态监控**
```python
class AgentMonitor:
    def track_agent_execution(self, agent_name: str, state: AgentState):
        """记录Agent执行指标"""
        metrics = {
            "agent_name": agent_name,
            "session_id": state.session_id,
            "start_time": time.time(),
            "input_state_size": len(str(state)),
            "status": "running"
        }
        
        # 存储到监控系统
        self.metrics_store.record(metrics)
    
    def track_agent_completion(self, agent_name: str, duration: float, success: bool):
        """记录Agent完成状态"""
        self.metrics_store.update({
            "agent_name": agent_name,
            "duration_ms": duration * 1000,
            "status": "success" if success else "failed",
            "end_time": time.time()
        })
```

**监控指标**：
- **执行时间**：每个Agent的响应时间（P50、P95、P99）
- **成功率**：每个Agent的成功/失败比例
- **状态转换**：记录State在每个Agent前后的变化
- **Token使用**：每个Agent调用LLM的token消耗
- **错误率**：各类错误的发生频率

**告警规则**：
- Agent执行时间超过阈值（Profile: 2s, Recommendation: 5s, Compliance: 1s）
- Agent连续失败3次
- 单次对话总token数超过8000
- 对话轮数超过15轮仍未完成

**2. 质量监控**
```python
class QualityMonitor:
    def evaluate_agent_output(self, agent_name: str, state: AgentState):
        """评估Agent输出质量"""
        if agent_name == "ProfileCollectionAgent":
            # 检查是否成功提取槽位
            slot_fill_rate = len(state.slots) / len(REQUIRED_SLOTS)
            self.record_metric("slot_fill_rate", slot_fill_rate)
        
        elif agent_name == "RecommendationAgent":
            # 检查推荐结果质量
            if state.recommendation_results:
                avg_confidence = sum(r.match_score for r in state.recommendation_results) / len(state.recommendation_results)
                self.record_metric("recommendation_confidence", avg_confidence)
        
        elif agent_name == "ComplianceAgent":
            # 检查合规通过率
            pass_rate = sum(1 for c in state.compliance_checks if c.check_result == "passed") / len(state.compliance_checks)
            self.record_metric("compliance_pass_rate", pass_rate)
```

#### 冲突处理方案

**冲突类型及处理策略**：

**1. 数据冲突**
- **场景**：用户在对话中修改之前提供的信息（如先说30岁，后说35岁）
- **检测**：Profile Agent检测到槽位值变化
- **处理**：
  ```python
  if state.slots["age"] != previous_state.slots["age"]:
      # 标记需要重新评估
      state.profile_complete = False
      state.recommendation_generated = False
      state.compliance_checked = False
      # 记录变更历史
      state.profile_change_history.append({
          "field": "age",
          "old_value": previous_state.slots["age"],
          "new_value": state.slots["age"],
          "timestamp": datetime.now()
      })
  ```

**2. 推荐与合规冲突**
- **场景**：Recommendation Agent推荐的产品未通过Compliance Agent的合规检查
- **检测**：Compliance Agent返回compliance_passed=False
- **处理**：
  ```python
  if not state.compliance_passed:
      # 过滤不合规产品
      valid_recommendations = [
          r for r in state.recommendation_results 
          if r.compliance_passed
      ]
      
      if len(valid_recommendations) < 3:
          # 合规产品不足，重新推荐
          state.recommendation_generated = False
          state.recommendation_constraints.exclude_products(failed_products)
          return "RecommendationAgent"
      else:
          # 使用合规产品
          state.recommendation_results = valid_recommendations
          return "END"
  ```

**3. 意图冲突**
- **场景**：用户在推荐阶段突然要求修改个人信息
- **检测**：Orchestrator识别到intent="modify_info"
- **处理**：
  ```python
  if state.current_intent == "modify_info" and state.current_agent != "ProfileCollectionAgent":
      # 保存当前进度
      state.saved_progress = {
          "agent": state.current_agent,
          "recommendations": state.recommendation_results
      }
      # 跳转到Profile Agent
      return "ProfileCollectionAgent"
  ```

**4. 超时冲突**
- **场景**：某个Agent执行时间过长
- **检测**：Orchestrator设置超时监控
- **处理**：
  ```python
  @timeout(seconds=10)
  def execute_agent(agent, state):
      return agent.run(state)
  
  try:
      result = execute_agent(agent, state)
  except TimeoutError:
      # 降级处理
      if agent_name == "RecommendationAgent":
          # 使用基于规则的推荐
          result = fallback_rule_based_recommendation(state)
      else:
          # 记录错误，返回友好提示
          state.error = AgentError(agent=agent_name, type="timeout")
          return "END"
  ```

**5. 资源冲突**
- **场景**：多个并发会话竞争LLM API配额
- **检测**：API返回429 Rate Limit错误
- **处理**：
  ```python
  class RateLimiter:
      def __init__(self, max_concurrent=10):
          self.semaphore = asyncio.Semaphore(max_concurrent)
      
      async def execute_with_limit(self, agent, state):
          async with self.semaphore:
              return await agent.run(state)
  ```

**冲突优先级**：
1. **数据一致性优先**：用户修改信息时，立即重置后续状态
2. **合规性优先**：合规检查失败的产品必须过滤，不能推荐给用户
3. **用户意图优先**：用户明确要求时，允许跳转流程
4. **系统稳定性优先**：超时或资源冲突时，使用降级策略保证服务可用

**状态共享**：
- 所有Agent共享同一个LangGraph State对象
- State包含：用户画像、对话历史、当前槽位、推荐结果、合规状态等
- 每个Agent读取State中的相关字段，更新自己负责的字段
- Orchestrator负责State的版本管理和冲突解决

### 架构变更总结

#### LangGraph 1.0.0核心变更

| 维度 | 旧方案 | 新方案（LangGraph 1.0.0） | 优势 |
|------|--------|--------------------------|------|
| **Agent隔离** | Context Isolation（运行时过滤） | Subgraph Schema（结构隔离） | ✅ 类型安全<br>✅ 无运行时开销<br>✅ 清晰的数据流 |
| **用户画像** | PostgreSQL user_profiles表 | Store API (PostgresStore) | ✅ 跨会话持久化<br>✅ 命名空间隔离<br>✅ 与LangGraph集成 |
| **会话状态** | HotDataLayer + WarmDataLayer | PostgresSaver (Checkpointer) | ✅ 原生集成<br>✅ 无需手写压缩<br>✅ 时间旅行调试 |
| **上下文构建** | get_full_context_for_agent(target_agent) | PostgresSaver自动管理 | ✅ 无需手动管理<br>✅ 保持上下文连贯性 |

#### 数据流变更

**旧数据流**：
```
用户消息 → Profile Agent → 提取槽位 → 存储到PostgreSQL user_profiles表
                         → 对话历史 → 三层存储（Hot/Warm/Cold）
Recommendation Agent → 从三层存储读取对话历史 → 生成推荐
```

**新数据流**：
```
用户消息 → Profile Subgraph → 提取槽位 → Store API (namespace: users/{user_id})
                            → 对话历史 → PostgresSaver自动管理
Recommendation Subgraph → 从Store API读取画像 → 生成推荐
                       → PostgresSaver提供会话上下文
```

#### 实施优先级

1. **Phase 1: 子图架构重构**（高优先级）
   - 定义子图State Schema
   - 创建Profile/Recommendation/Compliance子图
   - 创建主图并集成子图
   - 实现State转换逻辑

2. **Phase 2: Store API集成**（高优先级）
   - 初始化PostgresStore
   - 修改Profile子图，集成槽位存储
   - 修改Recommendation子图，从Store读取画像

3. **Phase 3: PostgresSaver集成**（高优先级）
   - 初始化PostgresSaver
   - 配置主图checkpointer
   - 实现会话恢复逻辑
   - 移除HotDataLayer和WarmDataLayer代码

4. **Phase 4: 测试验证**（中优先级）
   - 单元测试各子图
   - 集成测试主图
   - 验证Store API读写
   - 验证PostgresSaver会话管理

## Skills and MCP Integration

### Skills架构

Skills是可复用的能力模块，封装特定领域的专业知识和工具。在保险推荐系统中，我们可以定义以下Skills：

#### 1. Insurance Domain Skill

**职责**：保险领域知识和术语理解

**能力**：
- 保险术语解释（重疾险、医疗险、意外险、寿险）
- 保险条款解读
- 理赔流程说明
- 保险产品对比维度

**实现方式**：
```python
# skills/insurance_domain.py
class InsuranceDomainSkill:
    """保险领域知识技能"""
    
    def __init__(self):
        self.terminology = self._load_terminology()
        self.product_types = self._load_product_types()
    
    def explain_term(self, term: str) -> str:
        """解释保险术语"""
        return self.terminology.get(term, "未找到该术语的解释")
    
    def compare_products(self, product_type1: str, product_type2: str) -> Dict:
        """对比不同类型的保险产品"""
        return {
            "differences": self._get_differences(product_type1, product_type2),
            "suitable_scenarios": self._get_suitable_scenarios(product_type1, product_type2)
        }
    
    def explain_claim_process(self, product_type: str) -> List[str]:
        """解释理赔流程"""
        return self._get_claim_steps(product_type)
```

**集成方式**：
```python
# 在Profile Collection Agent中使用
class ProfileCollectionAgent:
    def __init__(self):
        self.insurance_skill = InsuranceDomainSkill()
    
    async def handle_user_question(self, question: str) -> str:
        """处理用户关于保险的问题"""
        if "什么是" in question or "解释" in question:
            # 提取术语
            term = self._extract_term(question)
            return self.insurance_skill.explain_term(term)
        # ... 其他处理
```

#### 2. Risk Assessment Skill

**职责**：风险评估和风险偏好分析

**能力**：
- 风险承受能力评估
- 风险偏好分类（保守型、稳健型、进取型）
- 风险问卷设计和评分
- 风险矛盾检测

**实现方式**：
```python
# skills/risk_assessment.py
class RiskAssessmentSkill:
    """风险评估技能"""
    
    def __init__(self):
        self.questionnaire = self._load_questionnaire()
        self.scoring_rules = self._load_scoring_rules()
    
    def assess_risk_preference(self, answers: Dict[str, Any]) -> RiskPreference:
        """评估风险偏好"""
        score = self._calculate_score(answers)
        
        if score < 30:
            return RiskPreference.CONSERVATIVE
        elif score < 70:
            return RiskPreference.BALANCED
        else:
            return RiskPreference.AGGRESSIVE
    
    def detect_contradictions(self, answers: Dict[str, Any]) -> List[str]:
        """检测回答中的矛盾"""
        contradictions = []
        
        # 检查逻辑矛盾
        if answers.get("risk_tolerance") == "low" and answers.get("investment_preference") == "high_risk":
            contradictions.append("您表示风险承受能力较低，但偏好高风险投资，这两者存在矛盾")
        
        return contradictions
    
    def generate_clarification_questions(self, contradictions: List[str]) -> List[str]:
        """生成澄清问题"""
        questions = []
        for contradiction in contradictions:
            questions.append(f"关于{contradiction}，您能进一步说明吗？")
        return questions
```

#### 3. Product Matching Skill

**职责**：产品匹配和推荐逻辑

**能力**：
- 基于规则的产品匹配
- 保障缺口分析
- 产品组合优化
- 推荐多样性控制

**实现方式**：
```python
# skills/product_matching.py
class ProductMatchingSkill:
    """产品匹配技能"""
    
    def __init__(self):
        self.matching_rules = self._load_matching_rules()
    
    def calculate_match_score(self, profile: UserProfile, product: Product) -> float:
        """计算匹配分数"""
        score = 0.0
        
        # 年龄匹配
        if product.age_min <= profile.age <= product.age_max:
            score += 30
        
        # 收入匹配
        if self._is_premium_affordable(profile.income_range, product.premium_range):
            score += 25
        
        # 风险偏好匹配
        if self._matches_risk_preference(profile.risk_preference, product.product_type):
            score += 20
        
        # 家庭结构匹配
        if self._matches_family_structure(profile, product):
            score += 15
        
        # 已有保障互补性
        if self._is_complementary(profile.existing_coverage, product):
            score += 10
        
        return score
    
    def analyze_coverage_gap(self, profile: UserProfile, existing: List[Product]) -> CoverageGap:
        """分析保障缺口"""
        # 计算各维度的保障充足性
        critical_illness_coverage = self._calculate_coverage(existing, "critical_illness")
        medical_coverage = self._calculate_coverage(existing, "medical")
        accident_coverage = self._calculate_coverage(existing, "accident")
        life_coverage = self._calculate_coverage(existing, "life")
        
        # 计算推荐保额
        recommended_critical_illness = profile.annual_income * 5  # 5倍年收入
        recommended_medical = 500000  # 50万医疗
        recommended_accident = profile.annual_income * 10  # 10倍年收入
        recommended_life = profile.annual_income * 10 if profile.has_dependents else 0
        
        return CoverageGap(
            critical_illness_gap=max(0, recommended_critical_illness - critical_illness_coverage),
            medical_gap=max(0, recommended_medical - medical_coverage),
            accident_gap=max(0, recommended_accident - accident_coverage),
            life_insurance_gap=max(0, recommended_life - life_coverage)
        )
```

#### 4. Compliance Checking Skill

**职责**：合规性检查和信息披露

**能力**：
- 投保条件验证
- 年龄/职业/健康限制检查
- 信息披露生成
- 合规审计日志

**实现方式**：
```python
# skills/compliance_checking.py
class ComplianceCheckingSkill:
    """合规检查技能"""
    
    def __init__(self):
        self.compliance_rules = self._load_compliance_rules()
    
    def check_eligibility(self, profile: UserProfile, product: Product) -> ComplianceResult:
        """检查投保资格"""
        checks = []
        
        # 年龄检查
        age_check = self._check_age(profile.age, product.age_min, product.age_max)
        checks.append(age_check)
        
        # 职业检查
        occupation_check = self._check_occupation(profile.occupation, product.occupation_restrictions)
        checks.append(occupation_check)
        
        # 健康检查
        health_check = self._check_health(profile.health_status, product.health_requirements)
        checks.append(health_check)
        
        # 综合判断
        all_passed = all(check.passed for check in checks)
        
        return ComplianceResult(
            eligible=all_passed,
            checks=checks,
            reasons=[check.reason for check in checks if not check.passed]
        )
    
    def generate_disclosure(self, product: Product) -> DisclosureInfo:
        """生成信息披露"""
        return DisclosureInfo(
            product_id=product.product_id,
            insurance_liability=self._format_liability(product.coverage_scope),
            liability_exclusions=self._format_exclusions(product.exclusions),
            cooling_off_period="15天犹豫期",
            fee_description=self._format_fees(product)
        )
```

### 内部工具模块（Tools）

系统采用内部工具模块替代MCP服务器，实现单进程内的直接调用，避免进程间通信开销。

**架构决策**：使用内部工具模块而非MCP的原因：
- 单项目内部调用，无需跨进程通信
- 直接函数调用，零序列化开销
- 编译时类型检查，IDE友好
- 单进程调试，日志集中管理
- 标准 Python 异常处理

#### 1. ProductDatabaseTool - 产品数据库工具

**功能**：产品查询、详情获取、可用性检查

**实现方式**：
```python
# tools/product_database.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from models.product import Product

class ProductDatabaseTool:
    """产品数据库工具 - 内部模块"""
    
    def __init__(self, db_session: Session, faiss_index):
        self.db = db_session
        self.faiss_index = faiss_index
    
    async def search_products(
        self,
        product_type: Optional[str] = None,
        age_range: Optional[Dict] = None,
        premium_range: Optional[Dict] = None,
        limit: int = 20
    ) -> List[Product]:
        """搜索产品 - 直接数据库查询"""
        query = self.db.query(Product).filter(Product.is_available == True)
        
        if product_type:
            query = query.filter(Product.product_type == product_type)
        
        if age_range:
            query = query.filter(
                Product.age_range.min_age <= age_range.get("min", 0),
                Product.age_range.max_age >= age_range.get("max", 120)
            )
        
        if premium_range:
            query = query.filter(
                Product.premium_range.min_premium <= premium_range.get("max", float('inf')),
                Product.premium_range.max_premium >= premium_range.get("min", 0)
            )
        
        return query.limit(limit).all()
    
    async def get_product_details(self, product_id: str) -> Optional[Product]:
        """获取产品详情 - 直接查询"""
        return self.db.query(Product).filter(
            Product.product_id == product_id
        ).first()
    
    async def check_availability(self, product_id: str) -> bool:
        """检查产品可用性 - 直接查询"""
        product = self.db.query(Product).filter(
            Product.product_id == product_id
        ).first()
        return product.is_available if product else False
    
    async def search_by_vector(self, query_embedding: List[float], k: int = 10) -> List[Product]:
        """向量检索 - FAISS搜索"""
        distances, indices = self.faiss_index.search(
            np.array([query_embedding]), k
        )
        product_ids = [self.index_to_product_id[idx] for idx in indices[0]]
        return self.db.query(Product).filter(
            Product.product_id.in_(product_ids)
        ).all()
```

**在Recommendation Agent中使用**：
```python
class RecommendationAgent:
    def __init__(self, db_session: Session, faiss_index):
        self.product_tool = ProductDatabaseTool(db_session, faiss_index)
        self.matching_skill = ProductMatchingSkill()
    
    async def generate_recommendations(self, profile: UserProfile) -> List[RecommendationResult]:
        """生成推荐 - 直接调用工具"""
        # 1. 直接调用工具搜索产品
        candidate_products = await self.product_tool.search_products(
            product_type=self._infer_product_types(profile),
            age_range={"min": profile.age - 5, "max": profile.age + 5},
            premium_range=self._calculate_affordable_range(profile.income_range)
        )
        
        # 2. 使用Skill计算匹配分数
        scored_products = [
            (product, self.matching_skill.calculate_match_score(profile, product))
            for product in candidate_products
        ]
        
        # 3. 排序并返回Top-K
        scored_products.sort(key=lambda x: x[1], reverse=True)
        top_products = scored_products[:5]
        
        # 4. 生成推荐结果
        recommendations = []
        for product, score in top_products:
            recommendations.append(RecommendationResult(
                product=product,
                match_score=score,
                explanation=self._generate_explanation(profile, product, score)
            ))
        
        return recommendations
```

#### 2. UserProfileTool - 用户画像工具

**功能**：用户画像CRUD操作、历史会话查询

**实现方式**：
```python
# tools/user_profile.py
from typing import Optional, List, Dict, Any
from langgraph.store.postgres import PostgresStore
from models.user import UserProfile

class UserProfileTool:
    """用户画像工具 - 内部模块"""
    
    def __init__(self, store: PostgresStore):
        self.store = store
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像 - 从Store API读取"""
        result = self.store.get(
            namespace=("users", user_id),
            key="profile"
        )
        if result:
            return UserProfile(**result.value)
        return None
    
    async def update_user_profile(
        self, 
        user_id: str, 
        profile_data: Dict[str, Any]
    ) -> UserProfile:
        """更新用户画像 - 存储到Store API"""
        existing = await self.get_user_profile(user_id)
        
        if existing:
            # 合并更新
            updated_data = existing.model_dump()
            updated_data.update(profile_data)
            updated_profile = UserProfile(**updated_data)
        else:
            updated_profile = UserProfile(**profile_data)
        
        self.store.put(
            namespace=("users", user_id),
            key="profile",
            value=updated_profile.model_dump()
        )
        
        return updated_profile
    
    async def get_user_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户历史会话"""
        result = self.store.get(
            namespace=("users", user_id),
            key="session_history"
        )
        if result:
            return result.value[:limit]
        return []
```

#### 3. ComplianceTool - 合规检查工具

**功能**：投保资格检查、信息披露生成、合规日志记录

**实现方式**：
```python
# tools/compliance.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.user import UserProfile
from models.product import Product
from models.compliance import ComplianceCheck, DisclosureInfo

class ComplianceTool:
    """合规检查工具 - 内部模块"""
    
    def __init__(self, db_session: Session, rules_config: Dict):
        self.db = db_session
        self.rules = rules_config
    
    async def check_eligibility(
        self, 
        user_profile: UserProfile, 
        product: Product
    ) -> List[ComplianceCheck]:
        """检查投保资格 - 直接规则执行"""
        checks = []
        
        # 年龄检查
        age_check = ComplianceCheck(
            check_type="age_check",
            check_result="passed" if product.age_range.min_age <= user_profile.age <= product.age_range.max_age else "failed",
            check_description=f"年龄检查：{user_profile.age}岁",
            checked_value=str(user_profile.age),
            expected_value=f"{product.age_range.min_age}-{product.age_range.max_age}"
        )
        checks.append(age_check)
        
        # 职业检查
        occupation_allowed = user_profile.occupation not in product.occupation_restrictions
        occupation_check = ComplianceCheck(
            check_type="occupation_check",
            check_result="passed" if occupation_allowed else "failed",
            check_description=f"职业检查：{user_profile.occupation}",
            checked_value=user_profile.occupation,
            expected_value="非限制职业"
        )
        checks.append(occupation_check)
        
        # 健康检查
        health_eligible = self._check_health_eligibility(user_profile, product)
        health_check = ComplianceCheck(
            check_type="health_check",
            check_result="passed" if health_eligible else "failed",
            check_description="健康状况检查",
            checked_value=user_profile.health_status.value if user_profile.health_status else "unknown"
        )
        checks.append(health_check)
        
        return checks
    
    async def generate_disclosure(self, product: Product) -> DisclosureInfo:
        """生成信息披露"""
        return DisclosureInfo(
            product_id=product.product_id,
            insurance_liability=self._format_liability(product.coverage_scope),
            liability_exclusions=self._format_exclusions(product.exclusions),
            cooling_off_period="15天犹豫期",
            fee_description=self._format_fees(product)
        )
    
    async def log_compliance_check(
        self, 
        session_id: str, 
        check_result: Dict[str, Any]
    ) -> None:
        """记录合规检查日志"""
        # 直接写入数据库
        log_entry = ComplianceLog(
            session_id=session_id,
            check_result=check_result,
            created_at=datetime.now()
        )
        self.db.add(log_entry)
        self.db.commit()
```

#### 4. FinancialCalculatorTool - 金融计算工具

**功能**：可承受保费计算、保障需求计算

**实现方式**：
```python
# tools/financial_calculator.py
from typing import Dict, Any
from models.user import UserProfile

class FinancialCalculatorTool:
    """金融计算工具 - 内部模块"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def calculate_affordable_premium(
        self, 
        annual_income: float, 
        family_size: int
    ) -> float:
        """计算可承受保费
        
        规则：建议保费不超过年收入的10%-15%
        """
        # 基础比例
        base_ratio = 0.10
        
        # 家庭人数调整（人数越多，比例越低）
        family_adjustment = max(0, 0.02 * (family_size - 1))
        adjusted_ratio = base_ratio - family_adjustment
        adjusted_ratio = max(0.05, adjusted_ratio)  # 最低5%
        
        return annual_income * adjusted_ratio
    
    def calculate_coverage_need(self, user_profile: UserProfile) -> Dict[str, float]:
        """计算保障需求
        
        返回各类型保险的推荐保额
        """
        annual_income = user_profile.annual_income or 100000
        
        # 重疾险：5倍年收入
        critical_illness = annual_income * 5
        
        # 医疗险：固定50万
        medical = 500000
        
        # 意外险：10倍年收入
        accident = annual_income * 10
        
        # 寿险：有被抚养人时，10倍年收入
        life = annual_income * 10 if user_profile.has_dependents else 0
        
        return {
            "critical_illness": critical_illness,
            "medical": medical,
            "accident": accident,
            "life": life
        }
    
    def calculate_premium_to_income_ratio(
        self, 
        total_premium: float, 
        annual_income: float
    ) -> float:
        """计算保费收入比"""
        if annual_income == 0:
            return 0
        return total_premium / annual_income
```

### Skills + Tools 协同架构

```mermaid
graph TB
    User[用户] --> Orchestrator[Orchestrator Agent]
    
    Orchestrator --> ProfileAgent[Profile Collection Agent]
    Orchestrator --> RecommendAgent[Recommendation Agent]
    Orchestrator --> ComplianceAgent[Compliance Agent]
    
    ProfileAgent --> InsuranceSkill[Insurance Domain Skill]
    ProfileAgent --> RiskSkill[Risk Assessment Skill]
    ProfileAgent --> ProfileTool[User Profile Tool]
    
    RecommendAgent --> MatchingSkill[Product Matching Skill]
    RecommendAgent --> ProductTool[Product Database Tool]
    RecommendAgent --> FinancialTool[Financial Calculator Tool]
    
    ComplianceAgent --> ComplianceSkill[Compliance Checking Skill]
    ComplianceAgent --> ComplianceTool[Compliance Tool]
    
    subgraph Skills Layer
        InsuranceSkill
        RiskSkill
        MatchingSkill
        ComplianceSkill
    end
    
    subgraph Tools Layer
        ProfileTool
        ProductTool
        FinancialTool
        ComplianceTool
    end
    
    subgraph Data Layer
        PG[(PostgreSQL)]
        FAISS[(FAISS)]
        Store[Store API]
    end
    
    ProductTool --> PG
    ProductTool --> FAISS
    ProfileTool --> Store
    ComplianceTool --> PG
```

### Skills vs Tools 使用原则

**使用Skills的场景**：
- 领域知识封装（保险术语、风险评估）
- 业务逻辑复用（产品匹配、保障缺口分析）
- 无需外部依赖的计算（评分、分类）
- 需要快速响应的操作

**使用Tools的场景**：
- 数据库访问（产品查询、用户画像存储）
- 外部服务调用（如未来需要对接第三方API）
- 需要事务支持的操作
- 可复用的基础设施功能

**协同使用示例**：
```python
class RecommendationAgent:
    def __init__(self, db_session, faiss_index, store):
        # Skills - 本地业务逻辑
        self.matching_skill = ProductMatchingSkill()
        self.insurance_skill = InsuranceDomainSkill()
        
        # Tools - 数据访问
        self.product_tool = ProductDatabaseTool(db_session, faiss_index)
        self.financial_tool = FinancialCalculatorTool(config)
        self.profile_tool = UserProfileTool(store)
    
    async def generate_recommendations(self, profile: UserProfile) -> List[RecommendationResult]:
        """生成推荐 - Skills + Tools协同"""
        
        # 1. 使用Tool获取数据
        affordable_premium = self.financial_tool.calculate_affordable_premium(
            annual_income=profile.annual_income,
            family_size=profile.family_size
        )
        
        candidate_products = await self.product_tool.search_products(
            premium_range={"max": affordable_premium}
        )
        
        # 2. 使用Skill进行本地计算
        coverage_gap = self.matching_skill.analyze_coverage_gap(
            profile, 
            profile.existing_coverage
        )
        
        scored_products = [
            (product, self.matching_skill.calculate_match_score(profile, product))
            for product in candidate_products
        ]
        
        # 3. 使用Skill生成解释
        recommendations = []
        for product, score in sorted(scored_products, key=lambda x: x[1], reverse=True)[:5]:
            explanation = self.insurance_skill.generate_recommendation_explanation(
                profile, product, score, coverage_gap
            )
            
            recommendations.append(RecommendationResult(
                product=product,
                match_score=score,
                explanation=explanation
            ))
        
        return recommendations
```

### 配置文件

**Skills配置** (`skills/config.yaml`):
```yaml
skills:
  insurance_domain:
    enabled: true
    terminology_file: "data/insurance_terminology.json"
    
  risk_assessment:
    enabled: true
    questionnaire_file: "data/risk_questionnaire.json"
    scoring_rules_file: "data/risk_scoring_rules.json"
    
  product_matching:
    enabled: true
    matching_rules_file: "data/product_matching_rules.json"
    
  compliance_checking:
    enabled: true
    compliance_rules_file: "data/compliance_rules.json"
```

### 优势总结

**Skills的优势**：
- ✅ 快速响应（本地计算）
- ✅ 可复用（跨Agent共享）
- ✅ 易测试（单元测试）
- ✅ 版本控制（代码管理）

**MCP的优势**：
- ✅ 解耦（独立服务）
- ✅ 可扩展（添加新工具）
- ✅ 实时更新（外部数据源）
- ✅ 跨语言（MCP协议标准）

**协同优势**：
- ✅ Skills处理业务逻辑，MCP处理数据访问
- ✅ Skills保证性能，MCP保证灵活性
- ✅ Skills易于测试，MCP易于集成
- ✅ 清晰的职责划分，降低系统复杂度

## Store API Integration

### Store API概述

Store API是LangGraph 1.0.0提供的持久化键值存储，用于跨会话共享和检索信息。在本系统中，Store API用于管理用户画像和关键槽位。

### PostgresStore配置

```python
from langgraph.store.postgres import PostgresStore

# 初始化Store（使用现有PostgreSQL数据库）
store = PostgresStore.from_conn_string(
    "postgresql://user:password@localhost:5432/insurance_db"
)

# 设置Store schema
store.setup()
```

### Namespace设计

```python
# 用户画像namespace
namespace = ("users", user_id)
key = "profile"

# 示例：
# namespace = ("users", "user_123")
# key = "profile"
# value = {"age": 30, "income_range": "100k-200k", ...}

# 会话元数据namespace（可选）
namespace = ("sessions", session_id)
key = "metadata"
```

### 用户画像存储

```python
class StoreManager:
    """Store API管理器"""
    
    def __init__(self, store: PostgresStore):
        self.store = store
    
    def put_user_profile(self, user_id: str, profile: dict):
        """存储用户画像"""
        self.store.put(
            namespace=("users", user_id),
            key="profile",
            value=profile
        )
    
    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """获取用户画像"""
        item = self.store.get(namespace=("users", user_id), key="profile")
        return item.value if item else None
    
    def update_user_profile(self, user_id: str, updates: dict):
        """更新用户画像"""
        # 获取现有画像
        profile = self.get_user_profile(user_id) or {}
        
        # 合并更新
        profile.update(updates)
        
        # 存储
        self.put_user_profile(user_id, profile)
```

### Profile Subgraph集成

```python
async def extract_slots_node(state: ProfileState, store: PostgresStore):
    """提取槽位并存储到Store API"""
    messages = state["messages"]
    user_id = state["user_id"]
    
    # 1. 从对话中提取槽位
    slots = await extract_slots_from_messages(messages)
    
    # 2. 存储到Store API
    if slots:
        store.put(
            namespace=("users", user_id),
            key="profile",
            value=slots
        )
    
    return {"slots": slots, "user_profile": slots}
```

### Recommendation Subgraph集成

```python
async def load_profile_node(state: RecommendationState, store: PostgresStore):
    """从Store API加载用户画像"""
    user_id = state["user_id"]
    
    # 从Store API读取
    profile_item = store.get(namespace=("users", user_id), key="profile")
    profile = profile_item.value if profile_item else {}
    
    return {"user_profile": profile}
```

### Store API vs 三层存储

| 维度 | Store API | 三层存储 |
|------|-----------|---------|
| **用途** | 结构化数据（用户画像、槽位） | 对话历史（时序数据） |
| **数据类型** | 键值对 | 消息流 |
| **访问模式** | 按namespace+key检索 | 按时间顺序检索 |
| **持久化** | 永久 | 分层（Hot 1h, Warm 7d, Cold 1y） |
| **压缩** | 无 | 智能压缩 |
| **适用场景** | 跨会话的用户数据 | 会话内的对话上下文 |

**协同使用**：
- Store API：存储用户画像、风险偏好、已有保障等结构化数据
- 三层存储：存储对话历史、消息流、会话上下文

## Components and Interfaces

### 1. FastAPI API Layer

#### 核心接口

**POST /api/v1/chat/stream**
- 功能：接收用户消息，返回SSE流式响应
- 输入：
  ```json
  {
    "session_id": "string",
    "message": "string",
    "user_id": "string (optional)"
  }
  ```
- 输出：SSE流
  ```
  event: agent_thinking
  data: {"agent": "profile_collection", "status": "processing"}

  event: message_chunk
  data: {"content": "我理解您想了解重疾险", "delta": "重疾险"}

  event: recommendation
  data: {"products": [...], "explanations": [...]}

  event: done
  data: {"session_id": "xxx", "turn_count": 5}
  ```

**GET /api/v1/session/{session_id}**
- 功能：恢复历史会话
- 输出：会话上下文和对话历史

**POST /api/v1/session/{session_id}/feedback**
- 功能：提交用户反馈
- 输入：
  ```json
  {
    "satisfaction": "positive|negative|neutral",
    "reason": "string (optional)",
    "recommendation_id": "string"
  }
  ```

**GET /api/v1/products/compare**
- 功能：对比产品
- 输入：`product_ids=id1,id2,id3`
- 输出：产品对比表

### 2. LangGraph State Manager

**State Schema**：
```python
class AgentState(TypedDict):
    # 对话管理
    session_id: str
    user_id: Optional[str]
    messages: List[Message]
    turn_count: int
    
    # 用户画像
    profile: UserProfile
    profile_complete: bool
    risk_preference: RiskPreference
    existing_coverage: List[ExistingProduct]
    
    # 推荐相关
    recommendation_candidates: List[Product]
    recommendation_results: List[RecommendationResult]
    recommendation_generated: bool
    
    # 合规相关
    compliance_checks: List[ComplianceCheck]
    compliance_passed: bool
    disclosure_info: List[DisclosureItem]
    
    # 意图和槽位
    current_intent: str
    slots: Dict[str, Any]
    missing_slots: List[str]
    
    # 控制流
    next_agent: str
    error: Optional[str]
```

**State Transitions**：
- 每个Agent作为一个节点，接收State，返回更新后的State
- Orchestrator根据State中的标志位决定下一个节点

### 3. Memory System（记忆系统）

#### 架构简化

记忆系统采用**PostgresSaver + Store API**的简化架构，利用LangGraph原生能力管理会话状态。

```
┌─────────────────────────────────────────┐
│         Orchestrator Agent              │
├─────────────────────────────────────────┤
│  Profile Agent │ Recommend │ Compliance │
├─────────────────────────────────────────┤
│         Data Layer                       │
│  ┌──────────────┬──────────────────┐   │
│  │ PostgresSaver│  Store API       │   │
│  │ (Checkpointer)│ (User Profile)  │   │
│  └──────────────┴──────────────────┘   │
├─────────────────────────────────────────┤
│  PostgreSQL Database                     │
└─────────────────────────────────────────┘
```

#### PostgresSaver（会话状态管理）

**职责**：管理会话内的状态持久化和恢复

**核心功能**：
- ✅ 自动持久化messages字段
- ✅ 状态快照和恢复
- ✅ 时间旅行调试
- ✅ 会话回滚
- ✅ 并发控制

**配置方式**：
```python
from langgraph.checkpoint.postgres import PostgresSaver

# 初始化Checkpointer
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:password@localhost:5432/insurance_db"
)
checkpointer.setup()  # 创建必要的表

# 编译图时配置checkpointer
graph = create_main_graph(store)
app = graph.compile(checkpointer=checkpointer)

# 调用时指定thread_id
config = {
    "configurable": {
        "thread_id": session_id
    }
}

# 执行
result = await app.ainvoke(input_state, config)

# 恢复会话
state = await app.aget_state(config)
messages = state.values.get("messages", [])

# 时间旅行（获取历史状态）
history = [state async for state in app.aget_state_history(config)]
```

**会话恢复示例**：
```python
async def restore_session(session_id: str) -> AgentState:
    """恢复历史会话"""
    config = {"configurable": {"thread_id": session_id}}
    
    # 获取当前状态
    state = await app.aget_state(config)
    
    if not state.values:
        # 新会话
        return create_initial_state(session_id)
    
    # 恢复会话
    return AgentState(**state.values)
```

**优势**：
- ✅ 无需手写消息持久化逻辑
- ✅ 无需手写压缩逻辑（保持上下文连贯性）
- ✅ 支持时间旅行调试
- ✅ 与LangGraph深度集成

#### Store API（跨会话数据管理）

**职责**：管理跨会话的用户画像和关键槽位

**核心功能**：
- ✅ 跨会话持久化用户画像
- ✅ 命名空间隔离
- ✅ 键值对存储

**配置方式**：
```python
from langgraph.store.postgres import PostgresStore

# 初始化Store
store = PostgresStore.from_conn_string(
    "postgresql://user:password@localhost:5432/insurance_db"
)
store.setup()

# 存储用户画像
store.put(
    namespace=("users", user_id),
    key="profile",
    value={
        "age": 30,
        "income_range": "100k-200k",
        "family_structure": "married_with_children",
        "risk_preference": "balanced"
    }
)

# 读取用户画像
profile_item = store.get(namespace=("users", user_id), key="profile")
profile = profile_item.value if profile_item else {}
```

#### 为什么移除HotDataLayer和WarmDataLayer？

**问题分析**：

1. **功能重叠**：
   - PostgresSaver已提供消息持久化和会话恢复
   - HotDataLayer的Redis缓存与PostgresSaver功能重叠
   - WarmDataLayer的手写压缩容易破坏上下文连贯性

2. **架构复杂度**：
   - 三层存储需要维护降温、压缩、归档逻辑
   - 手写LLM压缩可能丢失关键上下文
   - 多Agent场景下压缩逻辑难以维护

3. **LangGraph原生能力**：
   - PostgresSaver提供完整的会话管理
   - 支持时间旅行调试
   - 与LangGraph深度集成，无需额外代码

**简化后的优势**：
- ✅ 减少代码复杂度（移除~1000行代码）
- ✅ 保持上下文连贯性（无压缩损失）
- ✅ 利用LangGraph原生能力
- ✅ 易于调试和维护

#### Token优化策略

**方案1：利用LLM长上下文窗口**
```python
# 现代LLM支持128k+ tokens
# 大多数对话场景不需要压缩
# 只在超长对话时考虑优化
```

**方案2：节点内消息控制**
```python
async def profile_node(state: MainState):
    """Profile子图节点 - 控制消息数量"""
    # 只保留最近20条消息
    recent_messages = state["messages"][-20:]
    
    # 调用子图
    result = await profile_subgraph.ainvoke({
        **state,
        "messages": recent_messages
    })
    
    return result
```

**方案3：语义检索（可选，用于超长对话）**
```python
# 只在对话超过100轮时启用
# 使用FAISS向量检索相关历史
# 而不是线性压缩
```

#### 冷数据层（可选）

**用途**：
- 归档超过30天的会话
- 用于分析和审计
- 不影响运行时性能

**实现**：
```python
async def archive_old_sessions():
    """定期归档任务"""
    # 1. 查询30天前的会话
    # 2. 从PostgresSaver导出到S3
    # 3. 建立向量索引（可选）
    # 4. 从PostgresSaver删除
```

#### 数据流对比

**旧架构（三层存储）**：
```
用户消息 → HotDataLayer (Redis) → 5轮后降温 → WarmDataLayer (PG)
       → WarmDataLayer累积 → 2轮后压缩 → 压缩历史
       → 会话结束 → ColdDataLayer (FAISS + S3)
```

**新架构（PostgresSaver + Store API）**：
```
用户消息 → PostgresSaver (自动持久化) → 会话恢复
       → Store API (用户画像) → 跨会话共享
       → 可选：定期归档 → ColdDataLayer
```tModel).filter(
            InsuranceProductModel.product_id.in_(product_ids)
        ).all()
        
        # 统计类型频率
        type_counts = {}
        for p in products:
            type_counts[p.product_type] = type_counts.get(p.product_type, 0) + 1
        
        # 返回按频率排序的类型
        return sorted(type_counts.keys(), key=lambda t: type_counts[t], reverse=True)
    
    def _analyze_price_sensitivity(self, feedbacks: List) -> str:
        """分析价格敏感度"""
        # 简化实现：基于反馈的产品价格区间
        # 实际可以更复杂的分析
        return "medium"  # low, medium, high
    
    async def _count_user_sessions(self, user_id: str) -> int:
        """统计用户历史会话数"""
        return await self.db.query(ArchivedSessionModel).filter_by(user_id=user_id).count()
```

**PostgreSQL Schema - 归档表**：

```sql
-- 归档会话表
CREATE TABLE archived_sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    
    -- 会话摘要（用于快速查看）
    session_summary TEXT NOT NULL,
    
    -- 压缩的历史对话
    compressed_history TEXT,
    
    -- 最终状态快照
    final_state_snapshot JSONB,
    
    -- FAISS向量ID
    vector_id BIGINT,
    
    -- 归档时间
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 会话统计
    total_turns INT,
    completion_status VARCHAR(20), -- completed, abandoned
    user_satisfaction VARCHAR(20)  -- positive, negative, neutral
);

CREATE INDEX idx_archived_sessions_user_id ON archived_sessions(user_id);
CREATE INDEX idx_archived_sessions_vector_id ON archived_sessions(vector_id);
CREATE INDEX idx_archived_sessions_archived_at ON archived_sessions(archived_at);
```

**FAISS索引管理**：

```python
class FAISSColdStorage:
    """FAISS冷数据存储管理"""
    
    def __init__(self, dimension: int = 768, index_path: str = "faiss_cold_index.bin"):
        self.dimension = dimension
        self.index_path = index_path
        self.index = self._load_or_create_index()
        self.index_to_session_map: Dict[int, str] = {}  # vector_id -> session_id
        self.session_to_index_map: Dict[str, int] = {}  # session_id -> vector_id
    
    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        if os.path.exists(self.index_path):
            return faiss.read_index(self.index_path)
        else:
            # 创建新索引（使用IVF索引，适合大规模数据）
            quantizer = faiss.IndexFlatIP(self.dimension)
            index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)  # 100个聚类中心
            return index
    
    async def add_vector(self, embedding: np.ndarray) -> int:
        """添加向量到索引"""
        # 训练索引（如果尚未训练）
        if not self.index.is_trained:
            # 需要至少100个向量才能训练
            if self.index.ntotal >= 100:
                self.index.train(self._get_training_data())
        
        # 添加向量
        vector_id = self.index.ntotal
        self.index.add(embedding.reshape(1, -1))
        
        # 定期保存索引
        if self.index.ntotal % 100 == 0:
            self.save_index()
        
        return vector_id
    
    async def search(self, query_embedding: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """搜索相似向量"""
        distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)
        return distances, indices
    
    def save_index(self) -> None:
        """保存索引到磁盘"""
        faiss.write_index(self.index, self.index_path)
        logger.info(f"Saved FAISS index with {self.index.ntotal} vectors")
    
    def _get_training_data(self) -> np.ndarray:
        """获取训练数据"""
        # 从索引中提取所有向量用于训练
        # 实际实现需要从数据库或文件中加载
        pass
```

**生命周期**：
- 会话结束：从温数据层归档到冷数据层
- 向量化：会话摘要向量化并索引到FAISS
- 保留时间：
  - 用户画像：永久保存
  - 推荐历史：保留1年
  - 会话归档：保留1年（可配置）
  - FAISS向量：永久保存（定期优化）

**访问模式**：
- **主动检索**：用户开始新会话时，检索相似历史场景
- **被动学习**：分析历史数据，优化推荐算法
- **数据分析**：统计用户行为，生成报表

#### 长期记忆（Long-term Memory）

**定义**：跨会话的持久化记忆，整合冷数据层的各类数据

**说明**：长期记忆不是独立的存储层，而是冷数据层的逻辑视图，提供统一的访问接口。

```python
class LongTermMemory:
    """长期记忆 - 冷数据层的统一访问接口"""
    
    def __init__(self, db_session, faiss_index):
        self.cold_layer = ColdDataLayer(db_session, faiss_index)
    
    # 委托给冷数据层
    async def save_user_profile(self, user_id: str, profile: UserProfile) -> None:
        await self.cold_layer._update_user_profile(user_id, profile)
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return await self.cold_layer.get_user_profile(user_id)
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        return await self.cold_layer.get_user_preferences(user_id)
    
    async def search_similar_conversations(self, query: str, user_profile: UserProfile, top_k: int = 5) -> List[Dict]:
        return await self.cold_layer.search_similar_sessions(query, user_profile, top_k)
```

#### 三层记忆的交互逻辑

**1. 会话开始时**

```python
async def initialize_session(user_id: str, session_id: str) -> AgentState:
    """初始化会话 - 从冷数据层加载用户画像"""
    # 1. 从冷数据层加载用户画像和偏好
    cold_layer = ColdDataLayer(db_session, faiss_index)
    user_profile = await cold_layer.get_user_profile(user_id)
    user_preferences = await cold_layer.get_user_preferences(user_id)
    
    # 2. 初始化热数据层
    hot_layer = HotDataLayer(redis_client, session_id)
    if user_profile:
        await hot_layer.update_slots(user_profile.dict())
    
    # 3. 构建初始State
    initial_state = AgentState(
        session_id=session_id,
        user_id=user_id,
        profile=user_profile,
        user_preferences=user_preferences,
        messages=[],
        turn_count=0
    )
    
    return initial_state
```

**2. 对话进行中**

```python
async def process_user_message(session_id: str, message: str) -> AgentState:
    """处理用户消息 - 使用热数据层"""
    # 1. 从热数据层获取上下文（最近5轮）
    hot_layer = HotDataLayer(redis_client, session_id)
    hot_context = await hot_layer.get_hot_context()
    
    # 2. 如果需要更多上下文，从温数据层获取压缩历史
    warm_layer = WarmDataLayer(db_session, session_id)
    warm_context = await warm_layer.get_warm_context()
    
    # 3. 构建完整上下文（压缩历史 + 热数据）
    full_context = await warm_layer.get_full_context_for_agent(
        hot_context["hot_messages"]
    )
    
    # 4. Agent处理
    state = AgentState(**hot_context)
    state.messages.append(Message(role="user", content=message))
    state.full_context_prompt = full_context  # 用于LLM调用
    
    result_state = await orchestrator.run(state)
    
    # 5. 更新热数据层
    await hot_layer.add_message(result_state.messages[-1])
    await hot_layer.update_slots(result_state.slots)
    
    # 6. 热数据超过5轮，自动降温到温数据层（在add_message中处理）
    
    return result_state
```

**3. 会话结束时**

```python
async def finalize_session(session_id: str, user_id: str, final_state: AgentState) -> None:
    """会话结束 - 归档到冷数据层"""
    # 1. 归档到冷数据层
    cold_layer = ColdDataLayer(db_session, faiss_index)
    await cold_layer.archive_session(session_id, final_state)
    
    # 2. 清除热数据层
    hot_layer = HotDataLayer(redis_client, session_id)
    await hot_layer.clear()
    
    # 3. 温数据层保留7天（由数据库TTL管理）
    
    logger.info(f"Session {session_id} finalized and archived")
```

**4. 会话恢复时**

```python
async def resume_session(session_id: str) -> AgentState:
    """恢复会话"""
    # 1. 尝试从热数据层恢复（如果会话仍活跃）
    hot_layer = HotDataLayer(redis_client, session_id)
    hot_context = await hot_layer.get_hot_context()
    
    if hot_context["hot_messages"]:
        # 热数据命中，直接恢复
        logger.info(f"Resumed session {session_id} from hot layer")
        return AgentState(**hot_context)
    
    # 2. 从温数据层恢复（会话在7天内）
    warm_layer = WarmDataLayer(db_session, session_id)
    warm_context = await warm_layer.get_warm_context()
    
    if warm_context["compressed_history"] or warm_context["warm_messages"]:
        # 温数据命中，恢复到热数据层
        logger.info(f"Resumed session {session_id} from warm layer")
        
        # 重建热数据层
        # 注意：只恢复最近的消息，压缩历史保留在温数据层
        if warm_context["warm_messages"]:
            for msg_dict in warm_context["warm_messages"][-10:]:  # 最近5轮
                msg = Message(**msg_dict)
                await hot_layer.add_message(msg)
        
        return AgentState(
            session_id=session_id,
            messages=[Message(**m) for m in warm_context["warm_messages"]],
            compressed_history=warm_context["compressed_history"]
        )
    
    # 3. 从冷数据层恢复（会话已归档）
    cold_layer = ColdDataLayer(db_session, faiss_index)
    archived = await db_session.query(ArchivedSessionModel).filter_by(
        session_id=session_id
    ).first()
    
    if archived:
        logger.info(f"Resumed session {session_id} from cold layer (archived)")
        # 归档会话只读，不能继续对话
        return AgentState(**archived.final_state_snapshot)
    
    raise SessionNotFoundError(f"Session {session_id} not found in any layer")
```

**5. 相似场景检索（利用冷数据层）**

```python
async def find_similar_scenarios(user_profile: UserProfile, current_query: str) -> List[Dict]:
    """检索相似历史场景，辅助推荐"""
    cold_layer = ColdDataLayer(db_session, faiss_index)
    
    # 从FAISS检索相似会话
    similar_sessions = await cold_layer.search_similar_sessions(
        query=current_query,
        user_profile=user_profile,
        top_k=3
    )
    
    # 提取相似场景的推荐结果，作为参考
    reference_recommendations = []
    for session in similar_sessions:
        archived = await db_session.query(ArchivedSessionModel).filter_by(
            session_id=session["session_id"]
        ).first()
        
        if archived and archived.final_state_snapshot.get("recommendation_results"):
            reference_recommendations.append({
                "session_id": session["session_id"],
                "similarity": session["similarity_score"],
                "recommendations": archived.final_state_snapshot["recommendation_results"]
            })
    
    return reference_recommendations
```

#### 数据流转路径

```
[用户输入]
    ↓
[Orchestrator] ← 读取热数据层（最近5轮）
    ↓
[需要更多上下文？] → 读取温数据层（压缩历史）
    ↓
[Agent处理]
    ↓
[更新热数据层]
    ↓
[超过5轮？] → 自动降温到温数据层
    ↓
[累积2轮？] → 压缩温数据
    ↓
[会话结束？] → 归档到冷数据层（FAISS + PostgreSQL）
    ↓
[下次会话] → 从冷数据层加载用户画像
```

#### 三层架构的优势

**1. 性能优化**
- 热数据层：<10ms延迟，满足实时对话需求
- 温数据层：<100ms延迟，按需加载历史
- 冷数据层：<500ms延迟，用于分析和检索

**2. 成本优化**
- 热数据：Redis内存成本高，只保留最近5轮
- 温数据：PostgreSQL存储成本中等，压缩后保留7天
- 冷数据：归档存储成本低，长期保留

**3. Token优化**
- 热数据：5轮对话 ≈ 2000 tokens
- 温数据：压缩历史 ≈ 300 tokens
- 总计：~2300 tokens（相比原来的10轮 5000 tokens，减少54%）

**4. 扩展性**
- 热数据：支持高并发读写
- 温数据：支持批量压缩和归档
- 冷数据：支持大规模向量检索

**5. 可靠性**
- 热数据：Redis持久化 + 温数据备份
- 温数据：PostgreSQL事务保证
- 冷数据：定期备份FAISS索引

#### 配置参数

```python
class MemoryConfig:
    """记忆系统配置"""
    
    # 热数据层
    HOT_MAX_TURNS = 5  # 最多保留5轮对话
    HOT_TTL_SECONDS = 3600  # 1小时过期
    
    # 温数据层
    WARM_COMPRESSION_THRESHOLD = 4  # 超过2轮（4条消息）开始压缩
    WARM_RETENTION_DAYS = 7  # 保留7天
    
    # 冷数据层
    COLD_RETENTION_DAYS = 365  # 保留1年
    FAISS_DIMENSION = 768  # 向量维度
    FAISS_NLIST = 100  # 聚类中心数量
    
    # 压缩配置
    COMPRESSION_MAX_TOKENS = 200  # 压缩后最多200 tokens
    COMPRESSION_TEMPERATURE = 0.3  # LLM温度（低温度保证稳定性）
```

**关键设计原则**：
1. **读写分离**：Agent主要读取短期记忆（快速），异步写入长期记忆（持久）
2. **分层缓存**：Redis（秒级） → PostgreSQL（分钟级） → 冷存储（天级）
3. **渐进式遗忘**：短期记忆保留最近10轮，长期记忆保留关键信息
4. **语义检索**：使用FAISS向量化历史对话，支持相似场景检索

#### Redis与PostgreSQL一致性保证

**问题分析**：

Redis作为短期记忆的缓存层，PostgreSQL作为长期记忆的持久化层，两者之间可能出现数据不一致：

1. **写入失败**：Redis写入成功，PostgreSQL写入失败
2. **延迟同步**：Redis已更新，PostgreSQL尚未同步
3. **缓存失效**：Redis数据过期，但PostgreSQL未更新
4. **并发冲突**：多个请求同时修改同一会话数据

**一致性策略**：

**1. Write-Through模式（写穿透）**

关键数据同时写入Redis和PostgreSQL，确保强一致性：

```python
class ConsistentMemoryWriter:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
    
    async def write_critical_data(self, session_id: str, data: Dict[str, Any]) -> None:
        """关键数据写穿透（同时写Redis和PostgreSQL）"""
        try:
            # 1. 开启数据库事务
            async with self.db.begin():
                # 2. 写入PostgreSQL
                await self._write_to_postgres(session_id, data)
                
                # 3. 写入Redis
                await self._write_to_redis(session_id, data)
                
                # 4. 提交事务
                await self.db.commit()
        
        except Exception as e:
            # 回滚事务
            await self.db.rollback()
            # 清除Redis中的脏数据
            await self.redis.delete(f"stm:{session_id}:*")
            raise ConsistencyError(f"Failed to write data consistently: {e}")
    
    async def _write_to_postgres(self, session_id: str, data: Dict):
        """写入PostgreSQL"""
        session = await self.db.query(ConversationSessionModel).filter_by(
            session_id=session_id
        ).first()
        
        if session:
            session.context_snapshot = data
            session.last_activity_at = datetime.now()
        else:
            session = ConversationSessionModel(
                session_id=session_id,
                context_snapshot=data
            )
            self.db.add(session)
    
    async def _write_to_redis(self, session_id: str, data: Dict):
        """写入Redis"""
        pipe = self.redis.pipeline()
        
        # 写入各个字段
        if "messages" in data:
            for msg in data["messages"]:
                pipe.lpush(f"stm:{session_id}:messages", msg.model_dump_json())
        
        if "slots" in data:
            pipe.hset(f"stm:{session_id}:slots", mapping=data["slots"])
        
        # 设置过期时间
        pipe.expire(f"stm:{session_id}:messages", 3600)
        pipe.expire(f"stm:{session_id}:slots", 3600)
        
        await pipe.execute()
```

**适用场景**：
- 用户画像更新（年龄、职业、收入等关键信息）
- 推荐结果生成
- 合规检查结果

**2. Write-Behind模式（异步写回）**

非关键数据先写Redis，异步批量写入PostgreSQL：

```python
class AsyncMemoryWriter:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
        self.write_queue = asyncio.Queue()
        self.batch_size = 10
        self.flush_interval = 30  # 30秒
    
    async def write_non_critical_data(self, session_id: str, data: Dict) -> None:
        """非关键数据异步写入"""
        # 1. 立即写入Redis
        await self._write_to_redis(session_id, data)
        
        # 2. 加入写回队列
        await self.write_queue.put({
            "session_id": session_id,
            "data": data,
            "timestamp": datetime.now()
        })
    
    async def background_flush_worker(self):
        """后台刷新worker"""
        batch = []
        last_flush = time.time()
        
        while True:
            try:
                # 等待新数据（带超时）
                item = await asyncio.wait_for(
                    self.write_queue.get(), 
                    timeout=self.flush_interval
                )
                batch.append(item)
                
                # 达到批量大小或超时，执行刷新
                if len(batch) >= self.batch_size or (time.time() - last_flush) >= self.flush_interval:
                    await self._flush_batch(batch)
                    batch = []
                    last_flush = time.time()
            
            except asyncio.TimeoutError:
                # 超时，刷新现有批次
                if batch:
                    await self._flush_batch(batch)
                    batch = []
                    last_flush = time.time()
    
    async def _flush_batch(self, batch: List[Dict]):
        """批量刷新到PostgreSQL"""
        try:
            async with self.db.begin():
                for item in batch:
                    await self._write_to_postgres(
                        item["session_id"], 
                        item["data"]
                    )
                await self.db.commit()
                logger.info(f"Flushed {len(batch)} items to PostgreSQL")
        
        except Exception as e:
            logger.error(f"Failed to flush batch: {e}")
            # 重新加入队列重试
            for item in batch:
                await self.write_queue.put(item)
```

**适用场景**：
- 对话消息（非关键）
- 临时计算结果
- 用户行为日志

**3. Cache-Aside模式（旁路缓存）**

读取时先查Redis，未命中则查PostgreSQL并回填：

```python
class CacheAsideReader:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
    
    async def read_with_cache(self, session_id: str) -> Optional[AgentState]:
        """带缓存的读取"""
        # 1. 尝试从Redis读取
        cached_data = await self._read_from_redis(session_id)
        
        if cached_data:
            logger.debug(f"Cache hit for session {session_id}")
            return AgentState(**cached_data)
        
        # 2. Redis未命中，从PostgreSQL读取
        logger.debug(f"Cache miss for session {session_id}")
        db_data = await self._read_from_postgres(session_id)
        
        if db_data:
            # 3. 回填Redis缓存
            await self._write_to_redis(session_id, db_data)
            return AgentState(**db_data)
        
        return None
    
    async def _read_from_redis(self, session_id: str) -> Optional[Dict]:
        """从Redis读取"""
        pipe = self.redis.pipeline()
        pipe.lrange(f"stm:{session_id}:messages", 0, -1)
        pipe.hgetall(f"stm:{session_id}:slots")
        pipe.get(f"stm:{session_id}:intent")
        
        results = await pipe.execute()
        
        if not any(results):
            return None
        
        return {
            "messages": [Message.model_validate_json(m) for m in results[0]],
            "slots": results[1],
            "current_intent": results[2]
        }
    
    async def _read_from_postgres(self, session_id: str) -> Optional[Dict]:
        """从PostgreSQL读取"""
        session = await self.db.query(ConversationSessionModel).filter_by(
            session_id=session_id
        ).first()
        
        if session:
            return session.context_snapshot
        
        return None
```

**4. 版本控制与冲突检测**

使用版本号检测并发冲突：

```python
class VersionedMemoryWriter:
    async def write_with_version_check(self, session_id: str, data: Dict, expected_version: int) -> None:
        """带版本检查的写入"""
        # 1. 读取当前版本
        current_version = await self.redis.get(f"stm:{session_id}:version")
        
        if current_version and int(current_version) != expected_version:
            # 版本冲突，需要重新读取并合并
            raise VersionConflictError(
                f"Version conflict: expected {expected_version}, got {current_version}"
            )
        
        # 2. 写入数据并递增版本
        pipe = self.redis.pipeline()
        await self._write_data(pipe, session_id, data)
        pipe.incr(f"stm:{session_id}:version")
        await pipe.execute()
        
        # 3. 异步同步到PostgreSQL
        await self.async_writer.write_non_critical_data(session_id, data)
```

**5. 定期同步任务**

后台任务定期同步Redis到PostgreSQL：

```python
class PeriodicSyncTask:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
    
    async def run_periodic_sync(self):
        """定期同步任务（每5分钟）"""
        while True:
            try:
                await asyncio.sleep(300)  # 5分钟
                await self._sync_all_sessions()
            except Exception as e:
                logger.error(f"Periodic sync failed: {e}")
    
    async def _sync_all_sessions(self):
        """同步所有活跃会话"""
        # 1. 获取所有活跃会话ID
        session_keys = await self.redis.keys("stm:*:messages")
        session_ids = [key.split(":")[1] for key in session_keys]
        
        logger.info(f"Syncing {len(session_ids)} active sessions")
        
        # 2. 批量同步
        for session_id in session_ids:
            try:
                # 读取Redis数据
                data = await self._read_from_redis(session_id)
                
                # 写入PostgreSQL
                await self._write_to_postgres(session_id, data)
            
            except Exception as e:
                logger.error(f"Failed to sync session {session_id}: {e}")
        
        await self.db.commit()
        logger.info(f"Sync completed for {len(session_ids)} sessions")
```

**6. 故障恢复策略**

```python
class FailureRecovery:
    async def recover_from_redis_failure(self, session_id: str) -> AgentState:
        """Redis故障恢复"""
        logger.warning(f"Redis unavailable, falling back to PostgreSQL")
        
        # 直接从PostgreSQL读取
        db_data = await self._read_from_postgres(session_id)
        
        if db_data:
            return AgentState(**db_data)
        
        raise SessionNotFoundError(f"Session {session_id} not found in any storage")
    
    async def recover_from_postgres_failure(self, session_id: str) -> AgentState:
        """PostgreSQL故障恢复"""
        logger.warning(f"PostgreSQL unavailable, using Redis data only")
        
        # 只使用Redis数据（可能不完整）
        redis_data = await self._read_from_redis(session_id)
        
        if redis_data:
            return AgentState(**redis_data)
        
        raise SessionNotFoundError(f"Session {session_id} not found in Redis")
```

**一致性保证总结**：

| 数据类型 | 一致性策略 | Redis | PostgreSQL | 延迟 |
|---------|-----------|-------|-----------|------|
| 用户画像 | Write-Through | 同步写 | 同步写 | <100ms |
| 推荐结果 | Write-Through | 同步写 | 同步写 | <100ms |
| 对话消息 | Write-Behind | 同步写 | 异步写 | <30s |
| 临时数据 | Cache-Aside | 同步写 | 不写入 | 0 |
| 会话快照 | Periodic Sync | 实时 | 5分钟 | <5min |

**一致性级别**：
- **强一致性**：关键数据（用户画像、推荐结果）- Write-Through
- **最终一致性**：非关键数据（对话消息、日志）- Write-Behind
- **弱一致性**：临时数据（中间计算结果）- Cache-Only

### 3. Context Manager

**职责**：
- 协调短期和长期记忆的交互
- 管理对话上下文的持久化和恢复
- 维护对话历史（最近N轮）
- 管理用户画像的增量更新
- 处理敏感信息的加密存储

**接口**：
```python
class ContextManager:
    def __init__(self, redis_client, db_session, faiss_index):
        self.stm_factory = lambda sid: ShortTermMemory(redis_client, sid)
        self.ltm = LongTermMemory(db_session, faiss_index)
    
    def save_context(self, session_id: str, state: AgentState) -> None
    def load_context(self, session_id: str) -> Optional[AgentState]
    def update_profile(self, user_id: str, profile: UserProfile) -> None
    def get_conversation_history(self, session_id: str, last_n: int) -> List[Message]
    def clear_session(self, session_id: str) -> None
    def sync_to_long_term(self, session_id: str) -> None  # 短期→长期同步
```

### 4. RAG Module

**组件**：
- **Embedding Model**：将产品描述和用户查询向量化
- **FAISS Index**：存储产品向量，支持快速相似度检索
- **Retriever**：封装检索逻辑

**工作流程**：
1. 用户画像和需求 → 生成查询向量
2. FAISS检索 → 返回Top-K相关产品
3. 重排序 → 基于用户画像精细化排序
4. 返回候选产品列表

**接口**：
```python
class RAGModule:
    def index_products(self, products: List[Product]) -> None
    def retrieve(self, query: str, user_profile: UserProfile, top_k: int) -> List[Product]
    def update_index(self, product_id: str, product: Product) -> None
```

### 5. Product Matcher

**职责**：
- 基于规则和特征匹配产品
- 计算用户画像与产品的匹配分数
- 分析保障缺口
- 确保推荐多样性

**匹配维度**：
- 年龄适配性
- 收入与保费匹配
- 风险偏好与产品类型
- 家庭结构与保障需求
- 已有保障的互补性

**接口**：
```python
class ProductMatcher:
    def calculate_match_score(self, profile: UserProfile, product: Product) -> float
    def analyze_coverage_gap(self, profile: UserProfile, existing: List[Product]) -> CoverageGap
    def ensure_diversity(self, candidates: List[Product], top_k: int) -> List[Product]
```

### 6. Compliance Rules Engine

**职责**：
- 执行投保条件检查
- 验证年龄、职业、健康状况限制
- 生成信息披露内容
- 记录审计日志

**规则类型**：
- 年龄限制规则
- 职业限制规则
- 健康告知规则
- 地域限制规则

**接口**：
```python
class ComplianceEngine:
    def check_eligibility(self, profile: UserProfile, product: Product) -> ComplianceResult
    def generate_disclosure(self, product: Product) -> DisclosureInfo
    def log_compliance_check(self, check: ComplianceCheck) -> None
```

### 7. Session Manager（会话管理器）

**职责**：
- 管理多个并发会话的生命周期
- 确保会话之间的数据隔离
- 支持会话切换和后台运行
- 提供完整的历史消息查询

#### 会话隔离架构

```mermaid
graph TB
    User1[用户1] --> SM[Session Manager]
    User2[用户2] --> SM
    User3[用户3] --> SM
    
    SM --> Session1[Session 1<br/>session_id: xxx-001]
    SM --> Session2[Session 2<br/>session_id: xxx-002]
    SM --> Session3[Session 3<br/>session_id: xxx-003]
    
    Session1 --> Hot1[Hot Data: hot:xxx-001:*]
    Session2 --> Hot2[Hot Data: hot:xxx-002:*]
    Session3 --> Hot3[Hot Data: hot:xxx-003:*]
    
    Session1 --> Warm1[Warm Data: session_id=xxx-001]
    Session2 --> Warm2[Warm Data: session_id=xxx-002]
    Session3 --> Warm3[Warm Data: session_id=xxx-003]
    
    Hot1 --> Redis[(Redis)]
    Hot2 --> Redis
    Hot3 --> Redis
    
    Warm1 --> PG[(PostgreSQL)]
    Warm2 --> PG
    Warm3 --> PG
```

#### 核心实现

```python
class SessionManager:
    """会话管理器 - 管理多个并发会话"""
    
    def __init__(self, redis_client, db_session, faiss_index):
        self.redis = redis_client
        self.db = db_session
        self.faiss = faiss_index
        
        # 活跃会话缓存 {session_id: SessionContext}
        self.active_sessions: Dict[str, SessionContext] = {}
        
        # 会话锁（防止并发冲突）
        self.session_locks: Dict[str, asyncio.Lock] = {}
        
        # 后台任务管理
        self.background_tasks: Dict[str, asyncio.Task] = {}
    
    async def create_session(self, user_id: str, session_id: Optional[str] = None) -> str:
        """创建新会话"""
        # 1. 生成会话ID
        if not session_id:
            session_id = f"{user_id}-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        
        # 2. 检查会话是否已存在
        if session_id in self.active_sessions:
            raise SessionAlreadyExistsError(f"Session {session_id} already exists")
        
        # 3. 从冷数据层加载用户画像
        cold_layer = ColdDataLayer(self.db, self.faiss)
        user_profile = await cold_layer.get_user_profile(user_id)
        user_preferences = await cold_layer.get_user_preferences(user_id)
        
        # 4. 初始化会话上下文
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            state=AgentState(
                session_id=session_id,
                user_id=user_id,
                profile=user_profile,
                user_preferences=user_preferences,
                messages=[],
                turn_count=0,
                status="active"
            ),
            created_at=datetime.now(),
            last_activity_at=datetime.now()
        )
        
        # 5. 初始化热数据层
        hot_layer = HotDataLayer(self.redis, session_id)
        if user_profile:
            await hot_layer.update_slots(user_profile.dict())
        
        # 6. 注册会话
        self.active_sessions[session_id] = session_context
        self.session_locks[session_id] = asyncio.Lock()
        
        # 7. 持久化到数据库
        db_session = ConversationSessionModel(
            session_id=session_id,
            user_id=user_id,
            status="active",
            started_at=datetime.now(),
            last_activity_at=datetime.now()
        )
        self.db.add(db_session)
        await self.db.commit()
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> SessionContext:
        """获取会话上下文（支持自动恢复）"""
        # 1. 检查活跃会话缓存
        if session_id in self.active_sessions:
            # 更新最后活跃时间
            self.active_sessions[session_id].last_activity_at = datetime.now()
            return self.active_sessions[session_id]
        
        # 2. 从存储层恢复会话
        logger.info(f"Session {session_id} not in cache, restoring from storage")
        restored_context = await self._restore_session(session_id)
        
        # 3. 加入活跃会话缓存
        self.active_sessions[session_id] = restored_context
        self.session_locks[session_id] = asyncio.Lock()
        
        return restored_context
    
    async def _restore_session(self, session_id: str) -> SessionContext:
        """从存储层恢复会话"""
        # 1. 尝试从热数据层恢复
        hot_layer = HotDataLayer(self.redis, session_id)
        hot_context = await hot_layer.get_hot_context()
        
        if hot_context["hot_messages"]:
            # 热数据命中
            logger.info(f"Restored session {session_id} from hot layer")
            return SessionContext(
                session_id=session_id,
                user_id=hot_context.get("user_id"),
                state=AgentState(**hot_context),
                created_at=datetime.now(),  # 从DB获取
                last_activity_at=datetime.now()
            )
        
        # 2. 从温数据层恢复
        warm_layer = WarmDataLayer(self.db, session_id)
        warm_context = await warm_layer.get_warm_context()
        
        db_session = await self.db.query(ConversationSessionModel).filter_by(
            session_id=session_id
        ).first()
        
        if db_session and db_session.status == "active":
            # 温数据命中，重建热数据层
            logger.info(f"Restored session {session_id} from warm layer")
            
            # 恢复最近的消息到热数据层
            if warm_context["warm_messages"]:
                for msg_dict in warm_context["warm_messages"][-10:]:
                    msg = Message(**msg_dict)
                    await hot_layer.add_message(msg)
            
            return SessionContext(
                session_id=session_id,
                user_id=db_session.user_id,
                state=AgentState(
                    session_id=session_id,
                    user_id=db_session.user_id,
                    messages=[Message(**m) for m in warm_context["warm_messages"]],
                    compressed_history=warm_context["compressed_history"]
                ),
                created_at=db_session.started_at,
                last_activity_at=db_session.last_activity_at
            )
        
        # 3. 会话不存在或已归档
        raise SessionNotFoundError(f"Session {session_id} not found or archived")
    
    async def switch_session(self, from_session_id: str, to_session_id: str) -> SessionContext:
        """切换会话（不中断后台运行）"""
        logger.info(f"Switching from session {from_session_id} to {to_session_id}")
        
        # 1. 当前会话继续后台运行（不中断）
        if from_session_id in self.active_sessions:
            # 标记为后台运行
            self.active_sessions[from_session_id].state.background_mode = True
            logger.info(f"Session {from_session_id} moved to background")
        
        # 2. 获取目标会话（自动恢复）
        target_session = await self.get_session(to_session_id)
        
        # 3. 标记为前台运行
        target_session.state.background_mode = False
        
        return target_session
    
    async def process_message(self, session_id: str, message: str) -> AgentState:
        """处理消息（带会话隔离）"""
        # 1. 获取会话锁（防止并发冲突）
        async with self.session_locks[session_id]:
            # 2. 获取会话上下文
            session_context = await self.get_session(session_id)
            
            # 3. 处理消息
            result_state = await self._process_message_internal(
                session_context.state, 
                message
            )
            
            # 4. 更新会话上下文
            session_context.state = result_state
            session_context.last_activity_at = datetime.now()
            
            # 5. 更新数据库
            await self._update_session_activity(session_id)
            
            return result_state
    
    async def _process_message_internal(self, state: AgentState, message: str) -> AgentState:
        """内部消息处理逻辑"""
        # 1. 从热数据层获取上下文
        hot_layer = HotDataLayer(self.redis, state.session_id)
        hot_context = await hot_layer.get_hot_context()
        
        # 2. 如果需要更多上下文，从温数据层获取
        warm_layer = WarmDataLayer(self.db, state.session_id)
        warm_context = await warm_layer.get_warm_context()
        
        # 3. 构建完整上下文
        full_context = await warm_layer.get_full_context_for_agent(
            hot_context["hot_messages"]
        )
        
        # 4. 更新State
        state.messages.append(Message(role="user", content=message))
        state.full_context_prompt = full_context
        state.turn_count += 1
        
        # 5. Agent处理
        orchestrator = Orchestrator()
        result_state = await orchestrator.run(state)
        
        # 6. 更新热数据层
        await hot_layer.add_message(result_state.messages[-1])
        await hot_layer.update_slots(result_state.slots)
        
        return result_state
    
    async def get_all_messages(self, session_id: str) -> List[Message]:
        """获取会话的所有历史消息（热+温+冷）"""
        all_messages = []
        
        # 1. 从热数据层获取最近5轮
        hot_layer = HotDataLayer(self.redis, session_id)
        hot_messages = await hot_layer.get_hot_messages()
        
        # 2. 从温数据层获取5轮之前的消息
        warm_layer = WarmDataLayer(self.db, session_id)
        warm_context = await warm_layer.get_warm_context()
        
        if warm_context["warm_messages"]:
            warm_messages = [Message(**m) for m in warm_context["warm_messages"]]
            all_messages.extend(warm_messages)
        
        # 3. 添加热数据消息
        all_messages.extend(hot_messages)
        
        # 4. 按时间戳排序
        all_messages.sort(key=lambda m: m.timestamp)
        
        return all_messages
    
    async def list_user_sessions(self, user_id: str, status: Optional[str] = None) -> List[Dict]:
        """列出用户的所有会话"""
        query = self.db.query(ConversationSessionModel).filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        sessions = await query.order_by(
            ConversationSessionModel.last_activity_at.desc()
        ).all()
        
        return [
            {
                "session_id": s.session_id,
                "status": s.status,
                "started_at": s.started_at,
                "last_activity_at": s.last_activity_at,
                "turn_count": s.turn_count,
                "is_active": s.session_id in self.active_sessions
            }
            for s in sessions
        ]
    
    async def close_session(self, session_id: str) -> None:
        """关闭会话（归档到冷数据层）"""
        logger.info(f"Closing session {session_id}")
        
        # 1. 获取会话上下文
        if session_id in self.active_sessions:
            session_context = self.active_sessions[session_id]
            final_state = session_context.state
        else:
            # 从存储恢复
            session_context = await self._restore_session(session_id)
            final_state = session_context.state
        
        # 2. 归档到冷数据层
        cold_layer = ColdDataLayer(self.db, self.faiss)
        await cold_layer.archive_session(session_id, final_state)
        
        # 3. 更新数据库状态
        db_session = await self.db.query(ConversationSessionModel).filter_by(
            session_id=session_id
        ).first()
        
        if db_session:
            db_session.status = "completed"
            db_session.completed_at = datetime.now()
            await self.db.commit()
        
        # 4. 清除热数据层
        hot_layer = HotDataLayer(self.redis, session_id)
        await hot_layer.clear()
        
        # 5. 从活跃会话中移除
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        if session_id in self.session_locks:
            del self.session_locks[session_id]
        
        logger.info(f"Session {session_id} closed and archived")
    
    async def _update_session_activity(self, session_id: str) -> None:
        """更新会话活跃时间"""
        db_session = await self.db.query(ConversationSessionModel).filter_by(
            session_id=session_id
        ).first()
        
        if db_session:
            db_session.last_activity_at = datetime.now()
            db_session.turn_count = (db_session.turn_count or 0) + 1
            await self.db.commit()
    
    async def cleanup_inactive_sessions(self, inactive_threshold_minutes: int = 30) -> None:
        """清理不活跃的会话（后台任务）"""
        threshold_time = datetime.now() - timedelta(minutes=inactive_threshold_minutes)
        
        inactive_sessions = [
            session_id 
            for session_id, context in self.active_sessions.items()
            if context.last_activity_at < threshold_time
        ]
        
        for session_id in inactive_sessions:
            logger.info(f"Cleaning up inactive session {session_id}")
            
            # 持久化到温数据层
            session_context = self.active_sessions[session_id]
            warm_layer = WarmDataLayer(self.db, session_id)
            
            # 保存当前状态
            for message in session_context.state.messages:
                await warm_layer.append_message(message)
            
            # 从活跃会话中移除
            del self.active_sessions[session_id]
            if session_id in self.session_locks:
                del self.session_locks[session_id]
        
        logger.info(f"Cleaned up {len(inactive_sessions)} inactive sessions")
```

#### 会话隔离保证

**1. 数据隔离**

```python
class SessionIsolation:
    """会话隔离机制"""
    
    @staticmethod
    def get_redis_key(session_id: str, key_type: str) -> str:
        """生成会话隔离的Redis key"""
        return f"hot:{session_id}:{key_type}"
    
    @staticmethod
    def get_db_filter(session_id: str) -> Dict:
        """生成数据库查询过滤条件"""
        return {"session_id": session_id}
    
    @staticmethod
    async def verify_isolation(session_id1: str, session_id2: str, redis_client) -> bool:
        """验证两个会话的数据隔离"""
        # 检查Redis key是否隔离
        keys1 = await redis_client.keys(f"hot:{session_id1}:*")
        keys2 = await redis_client.keys(f"hot:{session_id2}:*")
        
        # 不应该有交集
        return len(set(keys1) & set(keys2)) == 0
```

**2. 并发控制**

```python
class ConcurrencyControl:
    """并发控制 - 防止同一会话的并发冲突"""
    
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def acquire_session_lock(self, session_id: str) -> asyncio.Lock:
        """获取会话锁"""
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        return self.locks[session_id]
    
    async def with_session_lock(self, session_id: str, func, *args, **kwargs):
        """在会话锁保护下执行函数"""
        lock = await self.acquire_session_lock(session_id)
        async with lock:
            return await func(*args, **kwargs)
```

**3. 后台运行支持**

```python
class BackgroundSessionManager:
    """后台会话管理 - 支持会话切换时不中断"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.background_tasks: Dict[str, asyncio.Task] = {}
    
    async def run_in_background(self, session_id: str, task_func, *args, **kwargs):
        """在后台运行会话任务"""
        # 创建后台任务
        task = asyncio.create_task(task_func(*args, **kwargs))
        self.background_tasks[session_id] = task
        
        # 标记会话为后台模式
        session_context = await self.session_manager.get_session(session_id)
        session_context.state.background_mode = True
        
        logger.info(f"Session {session_id} running in background")
        
        return task
    
    async def bring_to_foreground(self, session_id: str):
        """将会话带回前台"""
        session_context = await self.session_manager.get_session(session_id)
        session_context.state.background_mode = False
        
        logger.info(f"Session {session_id} brought to foreground")
    
    async def cancel_background_task(self, session_id: str):
        """取消后台任务"""
        if session_id in self.background_tasks:
            task = self.background_tasks[session_id]
            task.cancel()
            del self.background_tasks[session_id]
            logger.info(f"Cancelled background task for session {session_id}")
```

#### API接口

```python
# FastAPI路由
@app.post("/api/v1/sessions/create")
async def create_session(user_id: str):
    """创建新会话"""
    session_id = await session_manager.create_session(user_id)
    return {"session_id": session_id}

@app.get("/api/v1/sessions/{session_id}/messages")
async def get_all_messages(session_id: str):
    """获取会话的所有历史消息"""
    messages = await session_manager.get_all_messages(session_id)
    return {"messages": [m.dict() for m in messages]}

@app.get("/api/v1/users/{user_id}/sessions")
async def list_user_sessions(user_id: str, status: Optional[str] = None):
    """列出用户的所有会话"""
    sessions = await session_manager.list_user_sessions(user_id, status)
    return {"sessions": sessions}

@app.post("/api/v1/sessions/switch")
async def switch_session(from_session_id: str, to_session_id: str):
    """切换会话"""
    target_session = await session_manager.switch_session(from_session_id, to_session_id)
    return {
        "session_id": target_session.session_id,
        "status": "switched",
        "background_session": from_session_id
    }

@app.post("/api/v1/sessions/{session_id}/close")
async def close_session(session_id: str):
    """关闭会话"""
    await session_manager.close_session(session_id)
    return {"status": "closed"}

@app.post("/api/v1/sessions/{session_id}/chat")
async def chat(session_id: str, message: str):
    """发送消息（会话隔离）"""
    result_state = await session_manager.process_message(session_id, message)
    return {
        "session_id": session_id,
        "response": result_state.messages[-1].content,
        "turn_count": result_state.turn_count
    }
```

#### 会话生命周期

```
创建会话 → 活跃状态 → 后台运行 → 不活跃 → 归档
   ↓          ↓          ↓          ↓        ↓
 热数据    热+温数据   热+温数据   温数据   冷数据
```

#### 隔离验证测试

```python
async def test_session_isolation():
    """测试会话隔离"""
    # 创建两个会话
    session1 = await session_manager.create_session("user1")
    session2 = await session_manager.create_session("user2")
    
    # 发送消息到session1
    await session_manager.process_message(session1, "我30岁")
    
    # 发送消息到session2
    await session_manager.process_message(session2, "我40岁")
    
    # 验证隔离
    messages1 = await session_manager.get_all_messages(session1)
    messages2 = await session_manager.get_all_messages(session2)
    
    # session1应该只包含"我30岁"
    assert any("30岁" in m.content for m in messages1)
    assert not any("40岁" in m.content for m in messages1)
    
    # session2应该只包含"我40岁"
    assert any("40岁" in m.content for m in messages2)
    assert not any("30岁" in m.content for m in messages2)
    
    logger.info("Session isolation test passed")

async def test_session_switch():
    """测试会话切换"""
    session1 = await session_manager.create_session("user1")
    session2 = await session_manager.create_session("user1")
    
    # 在session1中对话
    await session_manager.process_message(session1, "我想买保险")
    
    # 切换到session2
    await session_manager.switch_session(session1, session2)
    
    # 在session2中对话
    await session_manager.process_message(session2, "我想了解重疾险")
    
    # 验证session1仍然存在且数据完整
    messages1 = await session_manager.get_all_messages(session1)
    assert any("买保险" in m.content for m in messages1)
    
    # 验证session2的数据独立
    messages2 = await session_manager.get_all_messages(session2)
    assert any("重疾险" in m.content for m in messages2)
    assert not any("买保险" in m.content for m in messages2)
    
    logger.info("Session switch test passed")
```

### 8. Prompt Template Manager

**职责**：
- 管理各Agent的提示词模板
- 支持动态变量替换
- 版本管理和A/B测试

**模板类型**：
- Profile Collection Prompts（引导问题、澄清问题）
- Recommendation Prompts（推荐生成、解释生成）
- Compliance Prompts（合规检查、披露生成）

**接口**：
```python
class PromptManager:
    def get_prompt(self, agent: str, task: str, variables: Dict) -> str
    def update_prompt(self, agent: str, task: str, template: str) -> None
```

## Data Models

### PostgreSQL Schema

#### 1. users表
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. user_profiles表
```sql
CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    
    -- 基本信息
    age INT,
    gender VARCHAR(10),
    marital_status VARCHAR(20),
    children_count INT,
    dependents_count INT,
    
    -- 职业和收入（加密存储）
    occupation VARCHAR(100),
    income_level VARCHAR(20), -- encrypted
    income_range VARCHAR(50),
    
    -- 风险偏好
    risk_preference VARCHAR(20), -- conservative, balanced, aggressive
    risk_score DECIMAL(5,2),
    
    -- 健康状况（加密存储）
    health_status TEXT, -- encrypted
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
```

#### 3. conversation_sessions表
```sql
CREATE TABLE conversation_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    
    -- 会话状态
    status VARCHAR(20), -- active, completed, abandoned
    turn_count INT DEFAULT 0,
    
    -- 上下文快照（JSONB）
    context_snapshot JSONB,
    
    -- 时间戳
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX idx_sessions_status ON conversation_sessions(status);
CREATE INDEX idx_sessions_last_activity ON conversation_sessions(last_activity_at);
```

#### 4. conversation_messages表
```sql
CREATE TABLE conversation_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(session_id),
    
    -- 消息内容
    role VARCHAR(20), -- user, assistant, system
    content TEXT,
    
    -- 元数据
    intent VARCHAR(50),
    slots JSONB,
    agent_name VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_session_id ON conversation_messages(session_id);
CREATE INDEX idx_messages_created_at ON conversation_messages(created_at);
```

#### 5. insurance_products表
```sql
CREATE TABLE insurance_products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    product_name VARCHAR(200) NOT NULL,
    product_type VARCHAR(50) NOT NULL, -- critical_illness, medical, accident, life
    provider VARCHAR(100) NOT NULL,
    
    -- 产品特征
    coverage_amount_min DECIMAL(15,2),
    coverage_amount_max DECIMAL(15,2),
    premium_range VARCHAR(50),
    
    -- 投保规则
    age_min INT,
    age_max INT,
    occupation_restrictions TEXT[],
    health_requirements TEXT,
    
    -- 产品详情
    coverage_scope TEXT[],
    exclusions TEXT[],
    waiting_period INT, -- days
    deductible DECIMAL(15,2),
    
    -- 条款和披露
    terms_summary TEXT,
    disclosure_items JSONB,
    
    -- 状态
    status VARCHAR(20), -- active, inactive, suspended
    
    -- 向量化特征（用于FAISS）
    feature_vector_id VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INT DEFAULT 1
);

CREATE INDEX idx_products_type ON insurance_products(product_type);
CREATE INDEX idx_products_status ON insurance_products(status);
CREATE INDEX idx_products_provider ON insurance_products(provider);
```

#### 6. existing_coverage表
```sql
CREATE TABLE existing_coverage (
    coverage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    
    -- 产品信息
    product_type VARCHAR(50),
    product_name VARCHAR(200),
    provider VARCHAR(100),
    
    -- 保障详情
    coverage_amount DECIMAL(15,2),
    premium DECIMAL(15,2),
    coverage_scope TEXT[],
    
    -- 有效期
    start_date DATE,
    end_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_coverage_user_id ON existing_coverage(user_id);
```

#### 7. recommendations表
```sql
CREATE TABLE recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(session_id),
    user_id UUID REFERENCES users(user_id),
    
    -- 推荐产品
    product_id UUID REFERENCES insurance_products(product_id),
    rank INT, -- 推荐排序
    
    -- 匹配信息
    match_score DECIMAL(5,2),
    match_features JSONB, -- 匹配的特征权重
    
    -- 解释
    explanation TEXT,
    recommendation_reason TEXT,
    
    -- 合规检查
    compliance_passed BOOLEAN,
    compliance_details JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_product FOREIGN KEY (product_id) REFERENCES insurance_products(product_id) ON DELETE CASCADE
);

CREATE INDEX idx_recommendations_session_id ON recommendations(session_id);
CREATE INDEX idx_recommendations_user_id ON recommendations(user_id);
```

#### 8. user_feedback表
```sql
CREATE TABLE user_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(session_id),
    recommendation_id UUID REFERENCES recommendations(recommendation_id),
    
    -- 反馈内容
    satisfaction VARCHAR(20), -- positive, negative, neutral
    feedback_reason TEXT,
    
    -- 元数据
    feedback_type VARCHAR(50), -- recommendation_quality, explanation_clarity, etc.
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_recommendation FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
);

CREATE INDEX idx_feedback_session_id ON user_feedback(session_id);
CREATE INDEX idx_feedback_recommendation_id ON user_feedback(recommendation_id);
```

#### 9. compliance_logs表
```sql
CREATE TABLE compliance_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(session_id),
    product_id UUID REFERENCES insurance_products(product_id),
    user_id UUID REFERENCES users(user_id),
    
    -- 检查结果
    check_type VARCHAR(50), -- age_check, occupation_check, health_check
    check_result VARCHAR(20), -- passed, failed
    check_details JSONB,
    
    -- 审计信息
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_product FOREIGN KEY (product_id) REFERENCES insurance_products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_logs_session_id ON compliance_logs(session_id);
CREATE INDEX idx_compliance_logs_checked_at ON compliance_logs(checked_at);
```

#### 10. quality_metrics表
```sql
CREATE TABLE quality_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(session_id),
    
    -- 质量指标
    intent_recognition_accuracy DECIMAL(5,2),
    slot_filling_completeness DECIMAL(5,2),
    conversation_completion_rate DECIMAL(5,2),
    user_satisfaction_score DECIMAL(5,2),
    
    -- 对话统计
    total_turns INT,
    avg_response_time DECIMAL(10,2), -- milliseconds
    
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_quality_metrics_session_id ON quality_metrics(session_id);
```

### Python Data Models

#### 核心数据类

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RiskPreference(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"

class UserProfile(BaseModel):
    user_id: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    children_count: Optional[int] = 0
    dependents_count: Optional[int] = 0
    occupation: Optional[str] = None
    income_level: Optional[str] = None
    income_range: Optional[str] = None
    risk_preference: Optional[RiskPreference] = None
    risk_score: Optional[float] = None
    health_status: Optional[str] = None

class ExistingProduct(BaseModel):
    product_type: str
    product_name: str
    provider: str
    coverage_amount: float
    premium: float
    coverage_scope: List[str]
    start_date: datetime
    end_date: datetime

class Product(BaseModel):
    product_id: str
    product_name: str
    product_type: str
    provider: str
    coverage_amount_min: float
    coverage_amount_max: float
    premium_range: str
    age_min: int
    age_max: int
    occupation_restrictions: List[str]
    coverage_scope: List[str]
    exclusions: List[str]
    waiting_period: int
    deductible: float
    terms_summary: str
    disclosure_items: Dict[str, Any]
    status: str

class RecommendationResult(BaseModel):
    product: Product
    rank: int
    match_score: float
    match_features: Dict[str, float]
    explanation: str
    recommendation_reason: str
    compliance_passed: bool

class Message(BaseModel):
    role: str  # user, assistant, system
    content: str
    intent: Optional[str] = None
    slots: Optional[Dict[str, Any]] = None
    agent_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class CoverageGap(BaseModel):
    critical_illness_gap: float
    medical_gap: float
    accident_gap: float
    life_insurance_gap: float
    recommendations: List[str]

class ComplianceCheck(BaseModel):
    check_type: str
    check_result: str  # passed, failed
    check_details: Dict[str, Any]
    checked_at: datetime = Field(default_factory=datetime.now)

class DisclosureInfo(BaseModel):
    product_id: str
    insurance_liability: str
    liability_exclusions: str
    cooling_off_period: str
    fee_description: str
```

### FAISS向量库结构

**索引结构**：
- **Index Type**: IndexFlatIP（内积索引，适合余弦相似度）
- **Dimension**: 768（假设使用text-embedding-ada-002或类似模型）
- **Metadata Store**: 使用单独的映射表存储product_id到向量索引的映射

**向量化内容**：
```python
# 产品向量化内容组合
product_text = f"""
产品名称: {product.product_name}
产品类型: {product.product_type}
保障范围: {', '.join(product.coverage_scope)}
适用人群: 年龄{product.age_min}-{product.age_max}岁
产品特点: {product.terms_summary}
"""

# 用户查询向量化
user_query = f"""
用户画像: {profile.age}岁, {profile.occupation}, {profile.marital_status}
风险偏好: {profile.risk_preference}
保障需求: {coverage_gap.recommendations}
"""
```

**索引管理**：
```python
class FAISSIndexManager:
    def __init__(self, dimension: int = 768):
        self.index = faiss.IndexFlatIP(dimension)
        self.product_id_map: Dict[int, str] = {}  # index_id -> product_id
        
    def add_product(self, product_id: str, embedding: np.ndarray) -> None:
        index_id = self.index.ntotal
        self.index.add(embedding.reshape(1, -1))
        self.product_id_map[index_id] = product_id
        
    def search(self, query_embedding: np.ndarray, top_k: int) -> List[str]:
        distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)
        return [self.product_id_map[idx] for idx in indices[0]]
```

## Correctness Properties

本节定义系统的正确性属性。属性是一种特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。

### Property 1: 用户画像序列化往返一致性

*For any* 有效的UserProfile对象，序列化到JSON后再反序列化，应该产生等价的UserProfile对象

**Validates: Requirements 1.5**

### Property 2: 产品数据序列化往返一致性

*For any* 有效的Insurance_Product对象，序列化到数据库后再读取，应该产生等价的Product对象

**Validates: Requirements 6.5**

### Property 3: 配置文件序列化往返一致性

*For any* 有效的对话配置对象，序列化到配置文件后再解析，应该产生等价的配置对象

**Validates: Requirements 16.5**

### Property 4: 会话上下文持久化往返一致性

*For any* Conversation_Session，保存到数据库后再恢复，应该产生等价的会话上下文（包含所有对话历史和用户画像）

**Validates: Requirements 4.3, 12.1, 12.2**

### Property 5: 用户信息收集完整性

*For any* 初始对话状态，Profile Collection Agent生成的引导问题应该覆盖所有必要的用户画像字段（家庭结构、年龄、职业、收入、风险偏好）

**Validates: Requirements 1.1, 1.2**

### Property 6: 信息提取正确性

*For any* 包含用户信息的消息，系统提取的结构化User_Profile字段应该与消息内容一致

**Validates: Requirements 1.3**

### Property 7: 缺失字段识别

*For any* 不完整的User_Profile，系统应该能够识别出所有缺失的必填字段

**Validates: Requirements 1.4**

### Property 8: 风险偏好分类有效性

*For any* 风险评估输入，系统输出的Risk_Preference必须是{conservative, balanced, aggressive}三个枚举值之一

**Validates: Requirements 2.2**

### Property 9: 风险评估完整性

*For any* 风险评估结果，应该包含评估依据和风险得分字段

**Validates: Requirements 2.4**

### Property 10: 保障缺口分析完整性

*For any* User_Profile和Existing_Coverage组合，系统生成的CoverageGap应该包含重疾、医疗、意外、寿险四个维度的分析

**Validates: Requirements 3.2, 3.3**

### Property 11: 无已有保障时的推荐非空性

*For any* 没有Existing_Coverage的User_Profile，系统应该生成至少一个基础保障推荐

**Validates: Requirements 3.4**

### Property 12: 意图识别有效性

*For any* 用户消息，系统识别的Intent应该在预定义的有效Intent集合内（至少8种类型）

**Validates: Requirements 4.1, 5.1, 5.2**

### Property 13: 槽位提取正确性

*For any* 包含槽位信息的用户消息，系统提取的Slot值应该与消息内容匹配

**Validates: Requirements 4.2**

### Property 14: 上下文更新一致性

*For any* 包含信息修改的对话序列，更新后的Conversation_Context应该反映最新的用户信息，且历史消息保持完整

**Validates: Requirements 4.4**

### Property 15: 产品数据模型完整性

*For any* Insurance_Product对象，应该包含所有必要字段：产品类型、保障范围、费率表、投保规则、条款摘要

**Validates: Requirements 6.1**

### Property 16: 产品检索结果正确性

*For any* 产品检索条件（类型、保障范围、适用人群、价格区间），返回的所有产品应该满足检索条件

**Validates: Requirements 6.2**

### Property 17: 产品版本递增性

*For any* Insurance_Product更新操作，更新后的版本号应该大于更新前的版本号

**Validates: Requirements 6.3**

### Property 18: 产品向量化维度一致性

*For any* Insurance_Product，向量化后的embedding维度应该等于配置的embedding_dimension（如768）

**Validates: Requirements 6.4**

### Property 19: 推荐生成非空性

*For any* 包含完整User_Profile、Risk_Preference和Existing_Coverage的Conversation_Context，Recommendation_Engine应该生成至少一个推荐结果

**Validates: Requirements 7.1**

### Property 20: 推荐结果数量约束

*For any* Recommendation_Result，推荐的Insurance_Product数量应该大于0且小于等于5

**Validates: Requirements 7.3, 15.4**

### Property 21: 推荐结果排序性

*For any* Recommendation_Result，推荐产品应该按照match_score降序排列

**Validates: Requirements 7.3**

### Property 22: 推荐解释完整性

*For any* Recommendation_Result中的每个推荐产品，应该包含非空的explanation和recommendation_reason字段

**Validates: Requirements 7.4, 8.1**

### Property 23: 推荐解释内容完整性

*For any* 推荐解释，应该包含推荐理由、产品优势、适用场景三个组成部分

**Validates: Requirements 8.2**

### Property 24: 推荐响应性

*For any* 两个不同的User_Profile（年龄或收入不同），生成的Recommendation_Result应该不同

**Validates: Requirements 7.5**

### Property 25: 保障覆盖度不变量

*For any* 有效的User_Profile，推荐后的保障覆盖度应该大于等于推荐前的保障覆盖度

**Validates: Requirements 7.6**

### Property 26: 产品对比维度完整性

*For any* 产品对比请求，返回的对比结果应该包含保障范围、保费、免赔额、等待期、理赔条件等所有必要维度

**Validates: Requirements 9.2**

### Property 27: 合规检查执行性

*For any* User_Profile和Insurance_Product组合，系统应该返回合规检查结果（包含check_type、check_result、check_details）

**Validates: Requirements 10.1, 10.2**

### Property 28: 不合规产品过滤性

*For any* 不符合投保条件的Insurance_Product，该产品不应该出现在最终的Recommendation_Result中

**Validates: Requirements 10.3**

### Property 29: 合规审计日志完整性

*For any* 合规检查操作，应该生成包含session_id、product_id、check_result、checked_at的审计日志记录

**Validates: Requirements 10.4**

### Property 30: 信息披露完整性

*For any* 展示的Insurance_Product，应该包含Disclosure_Information，且披露信息包含保险责任、责任免除、犹豫期、费用说明四个必要字段

**Validates: Requirements 11.1, 11.2**

### Property 31: 披露确认记录完整性

*For any* 用户确认披露信息的操作，应该生成包含确认时间和确认内容的记录

**Validates: Requirements 11.4**

### Property 32: 反馈记录完整性

*For any* 用户反馈操作，应该生成包含session_id、recommendation_id、satisfaction、feedback_reason的反馈记录

**Validates: Requirements 13.4**

### Property 33: 敏感信息加密性

*For any* 包含敏感信息（income_level、health_status）的User_Profile，存储到数据库后，敏感字段应该是加密状态

**Validates: Requirements 14.1**

### Property 34: 敏感信息访问审计

*For any* 敏感信息访问操作，应该生成包含访问时间、访问用户、访问字段的审计日志

**Validates: Requirements 14.4**

### Property 35: 推荐置信度完整性

*For any* Recommendation_Result，每个推荐应该包含置信度分数（confidence_score）字段

**Validates: Requirements 15.1**

### Property 36: 低置信度标记

*For any* 置信度分数低于阈值的推荐，应该被标记为需要人工审核（needs_review=true）

**Validates: Requirements 15.2**

### Property 37: 推荐元数据完整性

*For any* Recommendation_Result，应该包含match_features（特征权重）和match_score（匹配分数）字段

**Validates: Requirements 15.3**

### Property 38: 配置文件验证

*For any* 无效的配置文件（语法错误或缺少必填字段），系统应该拒绝加载并返回验证错误

**Validates: Requirements 16.4**

### Property 39: 无效输入处理

*For any* 无法识别Intent的用户输入，系统应该返回澄清问题或示例引导

**Validates: Requirements 17.1**

### Property 40: 槽位格式验证

*For any* 不符合格式要求的Slot值，系统应该返回格式说明并请求重新输入

**Validates: Requirements 17.2**

### Property 41: 友好错误提示

*For any* 系统内部错误，返回给用户的错误消息应该是友好提示而不是技术堆栈信息

**Validates: Requirements 17.4**

### Property 42: 推荐多样性 - 价格维度

*For any* Recommendation_Result，应该包含至少2种不同价格区间的Insurance_Product

**Validates: Requirements 18.2**

### Property 43: 推荐多样性 - 产品类型维度

*For any* 未明确指定产品类型的推荐请求，Recommendation_Result应该包含至少2种不同类型的Insurance_Product

**Validates: Requirements 18.3**

### Property 44: 下架产品过滤

*For any* 状态为inactive或suspended的Insurance_Product，不应该出现在Recommendation_Result中

**Validates: Requirements 19.1, 19.2**

### Property 45: 质量指标记录完整性

*For any* 完成的Conversation_Session，应该生成包含对话轮数、完成率、用户满意度的质量指标记录

**Validates: Requirements 20.1**

### Property 46: 质量指标计算正确性

*For any* Conversation_Session，计算的Intent识别准确率应该等于（正确识别的Intent数量 / 总Intent数量）

**Validates: Requirements 20.2**

### Property 47: 质量告警触发

*For any* 质量指标低于配置阈值的会话，应该生成告警记录

**Validates: Requirements 20.3**

<function_calls>
<invoke name="prework">
<parameter name="featureName">insurance-recommendation-agent


## Performance Optimization

### Token膨胀控制

#### 问题分析

在多轮对话中，token数量会随着对话历史的增长而膨胀，导致：
1. LLM API调用成本增加
2. 推理速度下降
3. 可能超出模型的上下文窗口限制（如8k、16k）

#### 优化策略

**1. 对话历史截断（Conversation Truncation）**

只保留最近N轮对话，丢弃更早的历史：

```python
class ConversationTruncator:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
    
    def truncate_messages(self, messages: List[Message]) -> List[Message]:
        """保留最近N轮对话（2N条消息）"""
        if len(messages) <= self.max_turns * 2:
            return messages
        
        # 保留系统消息 + 最近N轮
        system_messages = [m for m in messages if m.role == "system"]
        recent_messages = messages[-(self.max_turns * 2):]
        
        return system_messages + recent_messages
```

**配置**：
- Profile Collection Agent：保留最近5轮（主要收集信息，不需要太长历史）
- Recommendation Agent：保留最近8轮（需要理解用户偏好变化）
- Compliance Agent：保留最近3轮（主要执行规则检查）

**2. 上下文压缩（Context Compression）**

使用LLM总结历史对话，用摘要替换原始消息：

```python
class ContextCompressor:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def compress_history(self, messages: List[Message]) -> str:
        """将历史对话压缩为摘要"""
        if len(messages) < 10:
            return None  # 对话太短，不需要压缩
        
        # 构建压缩提示词
        conversation_text = "\n".join([
            f"{m.role}: {m.content}" for m in messages[:-6]  # 压缩除最近3轮外的历史
        ])
        
        prompt = f"""请将以下对话历史总结为简洁的要点（不超过200字）：

{conversation_text}

总结要点：
- 用户基本信息（年龄、职业、家庭状况）
- 用户已有保障
- 用户关注的重点
- 已讨论的产品类型
"""
        
        summary = await self.llm.generate(prompt, max_tokens=300)
        return summary
    
    def apply_compression(self, messages: List[Message]) -> List[Message]:
        """应用压缩：摘要 + 最近N轮"""
        if len(messages) < 10:
            return messages
        
        # 生成摘要
        summary = self.compress_history(messages[:-6])
        
        # 构建压缩后的消息列表
        compressed = [
            Message(role="system", content=f"对话历史摘要：{summary}"),
            *messages[-6:]  # 最近3轮对话
        ]
        
        return compressed
```

**触发条件**：
- 对话轮数超过10轮时，自动压缩
- 预估token数超过6000时，强制压缩

**3. 槽位提取与结构化（Slot Extraction）**

将对话中提取的结构化信息（槽位）从对话历史中移除，只保留在State中：

```python
class SlotBasedCompression:
    def remove_redundant_info(self, messages: List[Message], slots: Dict[str, Any]) -> List[Message]:
        """移除已提取为槽位的冗余信息"""
        compressed_messages = []
        
        for message in messages:
            # 检查消息是否只包含已提取的槽位信息
            if self._is_redundant(message.content, slots):
                # 用简短的占位符替换
                compressed_messages.append(
                    Message(role=message.role, content="[用户信息已记录]")
                )
            else:
                compressed_messages.append(message)
        
        return compressed_messages
    
    def _is_redundant(self, content: str, slots: Dict) -> bool:
        """判断消息是否冗余（信息已在槽位中）"""
        # 简单实现：检查消息是否只包含槽位值
        slot_values = [str(v) for v in slots.values()]
        return all(val in content for val in slot_values if val)
```

**4. 提示词模板优化（Prompt Template Optimization）**

精简提示词，移除冗余说明：

```python
# ❌ 冗长的提示词（~500 tokens）
verbose_prompt = """
你是一个专业的保险推荐助手。你的任务是帮助用户找到最适合他们的保险产品。
在推荐时，你需要考虑用户的年龄、职业、收入、家庭状况、风险偏好等多个因素。
你应该提供3-5个推荐产品，并为每个产品提供详细的推荐理由。
推荐理由应该包括为什么这个产品适合用户、产品的主要优势、以及适用场景。
你还需要确保推荐的产品符合用户的投保条件，包括年龄限制、职业限制等。
...（更多说明）
"""

# ✅ 精简的提示词（~150 tokens）
concise_prompt = """
角色：保险推荐专家
任务：基于用户画像推荐3-5个保险产品
要求：
- 匹配年龄、职业、收入、风险偏好
- 提供推荐理由（匹配维度、产品优势、适用场景）
- 确保符合投保条件
"""
```

**5. 分层提示词（Layered Prompts）**

根据Agent的不同阶段，使用不同详细程度的提示词：

```python
class LayeredPromptManager:
    def get_prompt(self, agent: str, phase: str) -> str:
        """根据阶段返回不同详细程度的提示词"""
        if phase == "initial":
            # 初始阶段：详细提示词（帮助模型理解任务）
            return self.detailed_prompts[agent]
        elif phase == "ongoing":
            # 进行中：精简提示词（模型已理解上下文）
            return self.concise_prompts[agent]
        else:
            # 最终阶段：最小提示词（只需执行特定任务）
            return self.minimal_prompts[agent]
```

### KV Cache优化

#### 什么是KV Cache

KV Cache是Transformer模型中的优化技术，缓存已计算的Key和Value矩阵，避免重复计算。

#### 在本系统中的应用

**1. 会话级KV Cache复用**

对于同一会话的多轮对话，复用之前轮次的KV Cache：

```python
class KVCacheManager:
    def __init__(self):
        self.cache_store = {}  # session_id -> cache_data
    
    def get_cache(self, session_id: str) -> Optional[bytes]:
        """获取会话的KV Cache"""
        return self.cache_store.get(session_id)
    
    def save_cache(self, session_id: str, cache_data: bytes) -> None:
        """保存会话的KV Cache"""
        self.cache_store[session_id] = cache_data
        # 设置过期时间（30分钟）
        self.schedule_expiry(session_id, 1800)
    
    def append_to_cache(self, session_id: str, new_tokens: List[int]) -> bytes:
        """追加新token到现有cache"""
        existing_cache = self.get_cache(session_id)
        # 调用LLM API的cache append功能
        updated_cache = self.llm_client.append_cache(existing_cache, new_tokens)
        self.save_cache(session_id, updated_cache)
        return updated_cache
```

**注意**：KV Cache复用依赖于LLM服务提供商的支持（如OpenAI的Prompt Caching、Anthropic的Prompt Caching）

**2. 系统提示词缓存**

将不变的系统提示词缓存，避免每次重新计算：

```python
# 使用OpenAI的Prompt Caching（假设API支持）
system_prompt = """
角色：保险推荐专家
任务：基于用户画像推荐保险产品
...（详细说明）
"""

# 标记为可缓存
messages = [
    {"role": "system", "content": system_prompt, "cache_control": {"type": "ephemeral"}},
    {"role": "user", "content": user_message}
]
```

**预期效果**：
- 系统提示词（~500 tokens）只需计算一次
- 后续请求直接复用，节省50-70%的计算时间

### 推理速度提升

#### 1. 并行化Agent执行（部分场景）

某些Agent可以并行执行（如果没有依赖关系）：

```python
async def parallel_agent_execution(state: AgentState):
    """并行执行独立的Agent任务"""
    # 例如：推荐生成和合规检查可以部分并行
    
    # 先生成候选推荐
    recommendations = await recommendation_agent.generate_candidates(state)
    
    # 并行执行：生成解释 + 合规检查
    explanation_task = asyncio.create_task(
        recommendation_agent.generate_explanations(recommendations)
    )
    compliance_task = asyncio.create_task(
        compliance_agent.check_all(state.profile, recommendations)
    )
    
    # 等待两个任务完成
    explanations, compliance_results = await asyncio.gather(
        explanation_task, compliance_task
    )
    
    return merge_results(recommendations, explanations, compliance_results)
```

**适用场景**：
- 推荐解释生成 + 合规检查（可并行）
- 多个产品的合规检查（可并行）

**不适用场景**：
- Profile Collection → Recommendation（有依赖，必须顺序执行）

#### 2. 流式生成（Streaming）

使用SSE流式返回，提升用户感知速度：

```python
async def stream_recommendation(state: AgentState):
    """流式生成推荐结果"""
    async for chunk in recommendation_agent.generate_stream(state):
        if chunk.type == "product":
            yield {
                "event": "recommendation",
                "data": chunk.product.model_dump_json()
            }
        elif chunk.type == "explanation":
            yield {
                "event": "explanation_chunk",
                "data": {"content": chunk.text}
            }
```

**效果**：
- 用户在1-2秒内看到第一个推荐产品
- 完整推荐在5秒内逐步展示
- 感知速度提升50%以上

#### 3. 预计算和缓存

**产品特征向量预计算**：
```python
# 在产品入库时预计算向量，而不是查询时计算
def index_product(product: Product):
    # 预计算embedding
    product_text = format_product_for_embedding(product)
    embedding = embedding_model.encode(product_text)
    
    # 存储到FAISS
    faiss_index.add_product(product.product_id, embedding)
    
    # 缓存到Redis（用于快速访问）
    redis.setex(
        f"product:embedding:{product.product_id}",
        86400,  # 24小时
        embedding.tobytes()
    )
```

**推荐结果缓存**：
```python
def get_recommendations_with_cache(user_profile: UserProfile):
    # 生成缓存key（基于用户画像的hash）
    cache_key = f"rec:{hash_profile(user_profile)}"
    
    # 尝试从缓存获取
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 缓存未命中，生成推荐
    recommendations = recommendation_engine.generate(user_profile)
    
    # 缓存结果（5分钟）
    redis.setex(cache_key, 300, json.dumps(recommendations))
    
    return recommendations
```

#### 4. 模型选择优化

根据任务复杂度选择不同的模型：

```python
class AdaptiveModelSelector:
    def select_model(self, task: str, complexity: str) -> str:
        """根据任务选择合适的模型"""
        if task == "intent_recognition":
            # 意图识别：使用快速小模型
            return "gpt-3.5-turbo"  # ~500ms
        elif task == "slot_extraction":
            # 槽位提取：使用快速小模型
            return "gpt-3.5-turbo"
        elif task == "recommendation_generation":
            if complexity == "simple":
                # 简单推荐：使用中等模型
                return "gpt-4o-mini"  # ~1s
            else:
                # 复杂推荐：使用强大模型
                return "gpt-4o"  # ~2-3s
        elif task == "explanation_generation":
            # 解释生成：使用强大模型（需要高质量输出）
            return "gpt-4o"
```

**预期效果**：
- 意图识别：500ms → 200ms（使用小模型）
- 整体推理速度提升30-40%

#### 5. 批处理优化

对于可批处理的任务，合并请求：

```python
async def batch_compliance_check(profiles: List[UserProfile], products: List[Product]):
    """批量合规检查"""
    # 构建批量请求
    batch_requests = [
        {
            "profile": p.model_dump(),
            "product": prod.model_dump()
        }
        for p in profiles
        for prod in products
    ]
    
    # 单次LLM调用处理多个检查
    prompt = f"""
    批量检查以下用户-产品组合的合规性：
    {json.dumps(batch_requests)}
    
    返回JSON数组，每个元素包含：
    - profile_id
    - product_id
    - eligible: true/false
    - reason: string
    """
    
    results = await llm_client.generate(prompt)
    return parse_batch_results(results)
```

### 性能监控指标

```python
class PerformanceMonitor:
    def track_metrics(self, session_id: str):
        return {
            # Token使用
            "total_tokens": self.get_total_tokens(session_id),
            "prompt_tokens": self.get_prompt_tokens(session_id),
            "completion_tokens": self.get_completion_tokens(session_id),
            
            # 推理速度
            "avg_response_time_ms": self.get_avg_response_time(session_id),
            "p95_response_time_ms": self.get_p95_response_time(session_id),
            
            # 缓存命中率
            "kv_cache_hit_rate": self.get_cache_hit_rate(session_id),
            "recommendation_cache_hit_rate": self.get_rec_cache_hit_rate(session_id),
            
            # 压缩效果
            "compression_ratio": self.get_compression_ratio(session_id),
            "avg_context_length": self.get_avg_context_length(session_id)
        }
```

### 优化效果预期

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 平均token数/会话 | 12,000 | 6,000 | 50% ↓ |
| 平均响应时间 | 3.5s | 1.8s | 48% ↓ |
| P95响应时间 | 6s | 3s | 50% ↓ |
| API成本/会话 | $0.15 | $0.08 | 47% ↓ |
| 并发支持 | 50 QPS | 100 QPS | 100% ↑ |

## Error Handling

### 错误分类

系统错误分为以下几类：

#### 1. 用户输入错误
- **无效Intent**：用户输入无法识别为任何已知意图
- **槽位格式错误**：用户提供的信息不符合预期格式（如年龄为负数）
- **信息矛盾**：用户在不同轮次提供的信息相互矛盾
- **连续无效输入**：用户连续3次提供无效输入

**处理策略**：
- 返回友好的澄清问题或示例引导
- 说明正确格式并请求重新输入
- 识别矛盾并请求用户澄清
- 提供人工客服转接选项

#### 2. 数据验证错误
- **用户画像不完整**：缺少必填字段
- **产品数据缺失**：产品信息不完整
- **配置文件无效**：配置语法错误或缺少必填项

**处理策略**：
- 识别缺失字段并通过追问补全
- 记录错误日志，跳过无效产品
- 拒绝加载配置并返回验证错误详情

#### 3. 业务逻辑错误
- **无推荐结果**：没有符合条件的产品
- **合规检查失败**：用户不符合任何产品的投保条件
- **保障缺口分析失败**：无法计算保障缺口

**处理策略**：
- 放宽推荐条件或推荐相近产品
- 说明不符合条件的原因，建议调整需求
- 使用默认值或跳过缺口分析

#### 4. 外部依赖错误
- **LLM API调用失败**：超时、限流、服务不可用
- **数据库连接失败**：PostgreSQL连接中断
- **FAISS索引错误**：向量检索失败

**处理策略**：
- 实现重试机制（指数退避）
- 使用降级策略（如基于规则的推荐）
- 返回友好错误提示，记录详细日志

#### 5. 系统内部错误
- **状态转换错误**：LangGraph状态机异常
- **数据序列化错误**：JSON编码/解码失败
- **内存溢出**：对话历史过长

**处理策略**：
- 捕获异常，重置到安全状态
- 记录详细错误日志，返回通用错误提示
- 限制对话历史长度，定期清理

### 错误处理流程

```python
class ErrorHandler:
    def handle_error(self, error: Exception, context: Dict) -> ErrorResponse:
        """统一错误处理入口"""
        if isinstance(error, UserInputError):
            return self._handle_user_input_error(error, context)
        elif isinstance(error, ValidationError):
            return self._handle_validation_error(error, context)
        elif isinstance(error, BusinessLogicError):
            return self._handle_business_logic_error(error, context)
        elif isinstance(error, ExternalDependencyError):
            return self._handle_external_dependency_error(error, context)
        else:
            return self._handle_internal_error(error, context)
    
    def _handle_user_input_error(self, error, context):
        # 返回友好提示，不记录为系统错误
        return ErrorResponse(
            user_message="抱歉，我没有理解您的意思。您可以这样说：...",
            should_retry=True,
            log_level="INFO"
        )
    
    def _handle_external_dependency_error(self, error, context):
        # 实现重试和降级
        if context.get("retry_count", 0) < 3:
            return ErrorResponse(
                user_message="系统正在处理中，请稍候...",
                should_retry=True,
                retry_delay=2 ** context.get("retry_count", 0)
            )
        else:
            return ErrorResponse(
                user_message="抱歉，系统暂时无法处理您的请求，请稍后再试",
                should_retry=False,
                log_level="ERROR"
            )
```

### 错误日志记录

所有错误都应该记录到日志系统，包含以下信息：
- **错误类型**：用户输入错误、验证错误、业务逻辑错误等
- **错误详情**：异常堆栈、错误消息
- **上下文信息**：session_id、user_id、当前状态
- **时间戳**：错误发生时间
- **严重级别**：INFO、WARNING、ERROR、CRITICAL

### 降级策略

当关键依赖不可用时，系统应该提供降级服务：

1. **LLM不可用**：使用基于规则的意图识别和槽位提取
2. **FAISS不可用**：使用PostgreSQL全文搜索或基于规则的产品匹配
3. **数据库不可用**：使用内存缓存提供只读服务
4. **Embedding模型不可用**：使用预计算的产品向量

## Testing Strategy

### 测试方法论

系统采用**双重测试策略**：
- **单元测试**：验证具体示例、边界条件和错误处理
- **属性测试**：验证通用属性在所有输入下的正确性

两种测试方法互补，共同确保系统的全面覆盖。

### 属性测试（Property-Based Testing）

#### 测试框架选择

使用**Hypothesis**作为Python的属性测试框架。

#### 测试配置

- **最小迭代次数**：每个属性测试运行100次
- **随机种子**：可配置，确保可重现性
- **超时设置**：每个测试最多30秒

#### 属性测试标签格式

每个属性测试必须包含注释，引用设计文档中的属性：

```python
@given(user_profile=user_profile_strategy())
@settings(max_examples=100)
def test_user_profile_serialization_roundtrip(user_profile):
    """
    Feature: insurance-recommendation-agent, Property 1: 用户画像序列化往返一致性
    For any 有效的UserProfile对象，序列化到JSON后再反序列化，应该产生等价的UserProfile对象
    """
    # 序列化
    json_str = user_profile.model_dump_json()
    
    # 反序列化
    restored_profile = UserProfile.model_validate_json(json_str)
    
    # 验证等价性
    assert user_profile == restored_profile
```

#### 数据生成策略（Strategies）

为核心数据类型定义Hypothesis策略：

```python
from hypothesis import strategies as st
from hypothesis.strategies import composite

@composite
def user_profile_strategy(draw):
    """生成随机UserProfile"""
    return UserProfile(
        age=draw(st.integers(min_value=18, max_value=100)),
        gender=draw(st.sampled_from(["male", "female"])),
        marital_status=draw(st.sampled_from(["single", "married", "divorced"])),
        children_count=draw(st.integers(min_value=0, max_value=5)),
        dependents_count=draw(st.integers(min_value=0, max_value=5)),
        occupation=draw(st.text(min_size=1, max_size=50)),
        income_range=draw(st.sampled_from(["<5w", "5-10w", "10-20w", "20-50w", ">50w"])),
        risk_preference=draw(st.sampled_from(list(RiskPreference))),
        risk_score=draw(st.floats(min_value=0.0, max_value=100.0))
    )

@composite
def insurance_product_strategy(draw):
    """生成随机Insurance_Product"""
    product_type = draw(st.sampled_from(["critical_illness", "medical", "accident", "life"]))
    return Product(
        product_id=str(uuid.uuid4()),
        product_name=draw(st.text(min_size=5, max_size=100)),
        product_type=product_type,
        provider=draw(st.text(min_size=3, max_size=50)),
        coverage_amount_min=draw(st.floats(min_value=10000, max_value=100000)),
        coverage_amount_max=draw(st.floats(min_value=100000, max_value=5000000)),
        premium_range=draw(st.text(min_size=5, max_size=20)),
        age_min=draw(st.integers(min_value=0, max_value=18)),
        age_max=draw(st.integers(min_value=60, max_value=100)),
        occupation_restrictions=draw(st.lists(st.text(min_size=3, max_size=30), max_size=10)),
        coverage_scope=draw(st.lists(st.text(min_size=5, max_size=50), min_size=1, max_size=20)),
        exclusions=draw(st.lists(st.text(min_size=5, max_size=50), max_size=10)),
        waiting_period=draw(st.integers(min_value=0, max_value=180)),
        deductible=draw(st.floats(min_value=0, max_value=10000)),
        terms_summary=draw(st.text(min_size=10, max_size=500)),
        disclosure_items={},
        status="active"
    )

@composite
def conversation_message_strategy(draw):
    """生成随机对话消息"""
    return Message(
        role=draw(st.sampled_from(["user", "assistant", "system"])),
        content=draw(st.text(min_size=1, max_size=500)),
        intent=draw(st.sampled_from([
            "consult_coverage", "compare_products", "modify_info", 
            "confirm_recommendation", "ask_explanation", "provide_feedback",
            "ask_price", "ask_terms"
        ])),
        slots=draw(st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.text(), st.integers(), st.floats())
        ))
    )
```

#### 属性测试示例

**Property 1: 用户画像序列化往返一致性**
```python
@given(user_profile=user_profile_strategy())
@settings(max_examples=100)
def test_user_profile_serialization_roundtrip(user_profile):
    """Feature: insurance-recommendation-agent, Property 1"""
    json_str = user_profile.model_dump_json()
    restored = UserProfile.model_validate_json(json_str)
    assert user_profile == restored
```

**Property 20: 推荐结果数量约束**
```python
@given(
    user_profile=user_profile_strategy(),
    products=st.lists(insurance_product_strategy(), min_size=10, max_size=50)
)
@settings(max_examples=100)
def test_recommendation_count_constraint(user_profile, products):
    """Feature: insurance-recommendation-agent, Property 20"""
    recommendation_engine = RecommendationEngine()
    results = recommendation_engine.generate_recommendations(user_profile, products)
    
    assert len(results) > 0
    assert len(results) <= 5
```

**Property 25: 保障覆盖度不变量**
```python
@given(
    user_profile=user_profile_strategy(),
    existing_coverage=st.lists(existing_product_strategy(), max_size=5)
)
@settings(max_examples=100)
def test_coverage_improvement_invariant(user_profile, existing_coverage):
    """Feature: insurance-recommendation-agent, Property 25"""
    # 计算推荐前的覆盖度
    coverage_before = calculate_coverage(user_profile, existing_coverage)
    
    # 生成推荐
    recommendations = recommendation_engine.generate_recommendations(
        user_profile, existing_coverage
    )
    
    # 计算推荐后的覆盖度
    all_coverage = existing_coverage + [r.product for r in recommendations]
    coverage_after = calculate_coverage(user_profile, all_coverage)
    
    # 验证不变量
    assert coverage_after >= coverage_before
```

### 单元测试

#### 测试框架

使用**pytest**作为单元测试框架。

#### 测试覆盖范围

1. **Agent逻辑测试**
   - Profile Collection Agent的引导问题生成
   - Recommendation Agent的产品匹配逻辑
   - Compliance Agent的合规检查规则

2. **数据处理测试**
   - 意图识别准确性（使用标注数据集）
   - 槽位提取正确性
   - 信息矛盾检测

3. **边界条件测试**
   - 空输入处理
   - 极端值处理（年龄0岁、200岁）
   - 特殊字符处理

4. **错误处理测试**
   - 各类异常的捕获和处理
   - 降级策略的触发
   - 错误日志的记录

#### 单元测试示例

```python
def test_intent_recognition_with_labeled_data():
    """测试意图识别准确性"""
    intent_recognizer = IntentRecognizer()
    
    test_cases = [
        ("我想了解重疾险", "consult_coverage"),
        ("帮我对比这两个产品", "compare_products"),
        ("我的年龄填错了，应该是30岁", "modify_info"),
        ("这个推荐不错，我要这个", "confirm_recommendation"),
    ]
    
    for message, expected_intent in test_cases:
        result = intent_recognizer.recognize(message)
        assert result.intent == expected_intent

def test_chitchat_detection():
    """测试闲聊检测"""
    detector = ChitchatDetector(llm_client)
    
    # 明显的闲聊
    assert detector.is_chitchat("今天天气真好", AgentState()) == True
    assert detector.is_chitchat("你好", AgentState()) == True
    assert detector.is_chitchat("谢谢", AgentState()) == True
    
    # 保险相关（非闲聊）
    assert detector.is_chitchat("我想买重疾险", AgentState()) == False
    assert detector.is_chitchat("30岁，程序员", AgentState()) == False
    
    # 边界情况
    assert detector.is_chitchat("天气这么热，有没有中暑保险", AgentState()) == False  # 包含保险关键词

def test_missing_slot_identification():
    """测试缺失字段识别"""
    profile = UserProfile(age=30, gender="male")  # 缺少其他字段
    
    missing_slots = identify_missing_slots(profile)
    
    assert "marital_status" in missing_slots
    assert "occupation" in missing_slots
    assert "income_range" in missing_slots

def test_compliance_check_age_restriction():
    """测试年龄限制合规检查"""
    product = Product(
        product_id="test-001",
        age_min=18,
        age_max=60,
        # ... 其他字段
    )
    
    # 年龄符合
    profile_valid = UserProfile(age=30)
    assert compliance_engine.check_age(profile_valid, product).passed == True
    
    # 年龄过小
    profile_too_young = UserProfile(age=15)
    assert compliance_engine.check_age(profile_too_young, product).passed == False
    
    # 年龄过大
    profile_too_old = UserProfile(age=65)
    assert compliance_engine.check_age(profile_too_old, product).passed == False

def test_error_handling_llm_timeout():
    """测试LLM超时错误处理"""
    with patch('llm_client.call') as mock_call:
        mock_call.side_effect = TimeoutError("LLM request timeout")
        
        error_handler = ErrorHandler()
        response = error_handler.handle_error(
            TimeoutError("LLM request timeout"),
            {"retry_count": 0}
        )
        
        assert response.should_retry == True
        assert response.user_message == "系统正在处理中，请稍候..."

def test_redis_postgres_consistency():
    """测试Redis和PostgreSQL一致性"""
    writer = ConsistentMemoryWriter(redis_client, db_session)
    session_id = "test-session-001"
    
    # 写入数据
    data = {
        "slots": {"age": 30, "occupation": "engineer"},
        "messages": [Message(role="user", content="我30岁")]
    }
    
    await writer.write_critical_data(session_id, data)
    
    # 验证Redis
    redis_data = await redis_client.hgetall(f"stm:{session_id}:slots")
    assert redis_data["age"] == "30"
    
    # 验证PostgreSQL
    db_session_obj = db_session.query(ConversationSessionModel).filter_by(
        session_id=session_id
    ).first()
    assert db_session_obj.context_snapshot["slots"]["age"] == 30

def test_version_conflict_detection():
    """测试版本冲突检测"""
    writer = VersionedMemoryWriter(redis_client, db_session)
    session_id = "test-session-002"
    
    # 第一次写入（版本1）
    await writer.write_with_version_check(session_id, {"data": "v1"}, expected_version=0)
    
    # 并发写入（版本冲突）
    with pytest.raises(VersionConflictError):
        await writer.write_with_version_check(session_id, {"data": "v2"}, expected_version=0)
```

### 集成测试

#### 测试范围

1. **端到端对话流程**
   - 从用户开始对话到生成推荐的完整流程
   - 多轮对话的上下文维护
   - 会话恢复功能

2. **数据库集成**
   - PostgreSQL的CRUD操作
   - 事务一致性
   - 并发访问

3. **FAISS向量检索**
   - 产品索引构建
   - 相似度检索准确性
   - 索引更新

4. **SSE流式响应**
   - 流式消息推送
   - 连接断开重连
   - 并发连接处理

#### 集成测试示例

```python
@pytest.mark.integration
async def test_end_to_end_conversation_flow():
    """测试完整对话流程"""
    # 初始化系统
    app = create_app()
    client = TestClient(app)
    
    # 开始对话
    response1 = client.post("/api/v1/chat/stream", json={
        "message": "我想买保险",
        "session_id": "test-session-001"
    })
    
    # 验证引导问题
    assert "年龄" in response1.text or "职业" in response1.text
    
    # 提供用户信息
    response2 = client.post("/api/v1/chat/stream", json={
        "message": "我30岁，程序员，年收入20万",
        "session_id": "test-session-001"
    })
    
    # 继续对话直到生成推荐
    # ...
    
    # 验证推荐结果
    recommendations = extract_recommendations(response_final)
    assert len(recommendations) >= 3
    assert len(recommendations) <= 5

@pytest.mark.integration
def test_faiss_product_retrieval():
    """测试FAISS产品检索"""
    # 构建索引
    products = load_test_products()
    faiss_manager = FAISSIndexManager()
    for product in products:
        embedding = embed_product(product)
        faiss_manager.add_product(product.product_id, embedding)
    
    # 执行检索
    query = "30岁程序员，想要重疾险"
    query_embedding = embed_query(query)
    results = faiss_manager.search(query_embedding, top_k=10)
    
    # 验证结果
    assert len(results) == 10
    # 验证返回的产品类型相关
    product_types = [get_product(pid).product_type for pid in results]
    assert "critical_illness" in product_types
```

### 性能测试

#### 测试指标

1. **响应时间**
   - 意图识别：< 100ms
   - 产品检索：< 200ms
   - 推荐生成：< 500ms
   - 端到端对话：< 2s

2. **吞吐量**
   - 并发会话数：>= 100
   - QPS：>= 50

3. **资源使用**
   - 内存使用：< 2GB per instance
   - CPU使用：< 70% under normal load

#### 性能测试工具

使用**Locust**进行负载测试：

```python
from locust import HttpUser, task, between

class InsuranceAgentUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def chat_conversation(self):
        session_id = f"session-{self.user_id}"
        
        # 发送消息
        self.client.post("/api/v1/chat/stream", json={
            "message": "我想买保险",
            "session_id": session_id
        })
```

### 测试环境

1. **本地开发环境**
   - 使用Docker Compose启动PostgreSQL和FAISS
   - 使用mock LLM进行快速测试

2. **CI/CD环境**
   - GitHub Actions自动运行单元测试和属性测试
   - 测试覆盖率要求：>= 80%

3. **预生产环境**
   - 运行集成测试和性能测试
   - 使用真实LLM API

### 测试数据管理

1. **测试数据集**
   - 标注的意图识别数据集（1000+样本）
   - 测试用保险产品数据（100+产品）
   - 测试用用户画像数据（50+画像）

2. **数据生成**
   - 使用Hypothesis生成随机测试数据
   - 使用Faker生成真实感的测试数据

3. **数据隔离**
   - 测试数据与生产数据完全隔离
   - 每次测试后清理测试数据

### 持续测试

1. **自动化测试**
   - 每次代码提交触发单元测试
   - 每日运行完整测试套件（包括属性测试）
   - 每周运行性能测试

2. **测试报告**
   - 生成测试覆盖率报告
   - 生成性能测试报告
   - 记录失败的属性测试用例

3. **回归测试**
   - 保存失败的属性测试用例作为回归测试
   - 每次发布前运行完整回归测试套件

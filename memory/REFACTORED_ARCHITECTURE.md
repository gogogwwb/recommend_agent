# 重构架构设计：基于LangGraph 1.0.0

## 版本信息
- **LangGraph**: 1.0.0
- **LangChain**: 1.0.0
- **Python**: 3.11+

---

## 核心改造

### 1. 使用子图Schema替代Context Isolation

#### 当前问题
- Context Isolation通过运行时过滤消息实现隔离
- 需要维护复杂的过滤规则
- 运行时开销

#### 新方案：子图架构

**核心思想**：每个Agent是一个独立的子图，拥有自己的State Schema。

```python
# 子图1：Profile Collection Subgraph
class ProfileState(TypedDict):
    """Profile Agent的State - 需要对话历史"""
    messages: Annotated[list, add_messages]  # 对话历史
    user_profile: Optional[dict]  # 输出：用户画像
    slots: dict  # 提取的槽位

# 子图2：Recommendation Subgraph  
class RecommendationState(TypedDict):
    """Recommendation Agent的State - 只需要结构化数据"""
    user_profile: dict  # 输入：用户画像（从Store API获取）
    recommendations: list  # 输出：推荐结果
    explanations: list

# 子图3：Compliance Subgraph
class ComplianceState(TypedDict):
    """Compliance Agent的State - 只需要验证数据"""
    user_profile: dict
    recommendations: list
    compliance_checks: list
```

**优势**：
- ✅ 结构上隔离，无需运行时过滤
- ✅ 类型安全
- ✅ 清晰的数据依赖

---

### 2. 引入Store API管理用户画像

#### Store API的作用

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

---

### 3. 三层存储的细节问题

#### 问题1：对话历史与用户画像的分离

**当前问题**：
- 对话历史和用户画像混在一起
- 压缩时需要提取槽位

**新方案**：
```python
# 对话历史 → 三层存储（Hot/Warm/Cold）
hot_layer.add_message(message)  # 只存储消息

# 用户画像 → Store API
store.put(
    namespace=("users", user_id),
    key="profile",
    value=extracted_profile
)
```

**流程**：
1. Profile Agent从对话中提取槽位
2. 槽位立即存储到Store API
3. 对话历史存储到三层存储
4. Recommendation Agent从Store API读取画像（不需要对话历史）

#### 问题2：压缩机制的简化

**当前问题**：
- 压缩时需要保留关键槽位
- 槽位和压缩历史混在一起

**新方案**：
```python
# 压缩时不再需要保留槽位（槽位已在Store API中）
async def compress_messages(messages: List[Message]) -> str:
    """简化的压缩 - 只压缩对话内容"""
    # 1. 格式化对话
    conversation_text = format_messages(messages)
    
    # 2. LLM压缩（或规则压缩）
    summary = await llm_compress(conversation_text)
    
    # 3. 返回摘要（不需要附加槽位）
    return summary
```

**优势**：
- ✅ 压缩逻辑简化
- ✅ 槽位和对话历史解耦
- ✅ 更清晰的职责划分

#### 问题3：上下文构建的优化

**当前问题**：
```python
# 旧方案：需要过滤消息
context = await warm_layer.get_full_context_for_agent(
    hot_messages,
    target_agent="RecommendationAgent"  # 运行时过滤
)
```

**新方案**：
```python
# 方案1：Recommendation Agent不需要对话历史
# 直接从Store API获取用户画像
profile = store.get(namespace=("users", user_id), key="profile")

# 方案2：如果需要对话上下文（如生成解释）
# 获取压缩历史（无需过滤，因为子图已隔离）
context = await warm_layer.get_compressed_history()
```

---

## 新架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│ Main Graph (Orchestrator)                               │
│ - 协调子图执行                                           │
│ - 管理全局流程                                           │
└─────────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Profile      │ │ Recommend    │ │ Compliance   │
│ Subgraph     │ │ Subgraph     │ │ Subgraph     │
│              │ │              │ │              │
│ State:       │ │ State:       │ │ State:       │
│ - messages   │ │ - profile    │ │ - profile    │
│ - profile    │ │ - recommend  │ │ - recommend  │
│ - slots      │ │ - explain    │ │ - compliance │
└──────────────┘ └──────────────┘ └──────────────┘
        ↓               ↓               ↓
┌─────────────────────────────────────────────────────────┐
│ Data Layer                                               │
├─────────────────────────────────────────────────────────┤
│ Store API (PostgreSQL)                                   │
│ - 用户画像                                               │
│ - 关键槽位                                               │
├─────────────────────────────────────────────────────────┤
│ 三层存储                                                 │
│ - Hot Layer (Redis): 最近10条消息                        │
│ - Warm Layer (PostgreSQL): 压缩历史                      │
│ - Cold Layer (S3): 归档                                  │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
用户消息
    ↓
Profile Subgraph
    ├─→ 提取槽位 → Store API (用户画像)
    └─→ 对话历史 → 三层存储
    ↓
Recommendation Subgraph
    ├─→ 读取画像 ← Store API
    └─→ 生成推荐
    ↓
Compliance Subgraph
    ├─→ 读取画像 ← Store API
    └─→ 验证推荐
```

---

## 实现方案

### Phase 1: 子图架构重构

#### 1.1 定义子图State

```python
# models/subgraph_states.py

from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import add_messages

# Profile Subgraph State
class ProfileState(TypedDict):
    """Profile Collection Subgraph State"""
    messages: Annotated[list, add_messages]  # 对话历史
    user_id: str
    session_id: str
    user_profile: Optional[dict]  # 输出
    slots: dict  # 提取的槽位

# Recommendation Subgraph State
class RecommendationState(TypedDict):
    """Recommendation Subgraph State"""
    user_id: str
    session_id: str
    user_profile: dict  # 从Store API读取
    recommendations: list  # 输出
    explanations: list

# Compliance Subgraph State
class ComplianceState(TypedDict):
    """Compliance Subgraph State"""
    user_id: str
    session_id: str
    user_profile: dict
    recommendations: list
    compliance_checks: list  # 输出
    disclosure_info: str
```

#### 1.2 创建子图

```python
# agents/profile_subgraph.py

from langgraph.graph import StateGraph, START, END
from models.subgraph_states import ProfileState

def create_profile_subgraph(store):
    """创建Profile Collection子图"""
    
    async def extract_slots_node(state: ProfileState):
        """提取槽位"""
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
    
    async def validate_profile_node(state: ProfileState):
        """验证画像完整性"""
        profile = state["user_profile"]
        
        # 检查必填字段
        required_fields = ["age", "income_range", "family_structure"]
        missing = [f for f in required_fields if f not in profile]
        
        if missing:
            # 需要继续收集
            return {"user_profile": profile}
        
        return {"user_profile": profile}
    
    # 构建子图
    builder = StateGraph(ProfileState)
    builder.add_node("extract_slots", extract_slots_node)
    builder.add_node("validate_profile", validate_profile_node)
    
    builder.add_edge(START, "extract_slots")
    builder.add_edge("extract_slots", "validate_profile")
    builder.add_edge("validate_profile", END)
    
    return builder.compile()
```

```python
# agents/recommendation_subgraph.py

from langgraph.graph import StateGraph, START, END
from models.subgraph_states import RecommendationState

def create_recommendation_subgraph(store):
    """创建Recommendation子图"""
    
    async def load_profile_node(state: RecommendationState):
        """从Store API加载用户画像"""
        user_id = state["user_id"]
        
        # 从Store API读取
        profile_item = store.get(namespace=("users", user_id), key="profile")
        profile = profile_item.value if profile_item else {}
        
        return {"user_profile": profile}
    
    async def match_products_node(state: RecommendationState):
        """匹配产品"""
        profile = state["user_profile"]
        
        # 产品匹配逻辑（不需要对话历史）
        recommendations = await match_products(profile)
        
        return {"recommendations": recommendations}
    
    async def generate_explanations_node(state: RecommendationState):
        """生成解释"""
        profile = state["user_profile"]
        recommendations = state["recommendations"]
        
        # 生成解释
        explanations = [
            generate_explanation(profile, rec)
            for rec in recommendations
        ]
        
        return {"explanations": explanations}
    
    # 构建子图
    builder = StateGraph(RecommendationState)
    builder.add_node("load_profile", load_profile_node)
    builder.add_node("match_products", match_products_node)
    builder.add_node("generate_explanations", generate_explanations_node)
    
    builder.add_edge(START, "load_profile")
    builder.add_edge("load_profile", "match_products")
    builder.add_edge("match_products", "generate_explanations")
    builder.add_edge("generate_explanations", END)
    
    return builder.compile()
```

#### 1.3 创建主图

```python
# agents/main_graph.py

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

# 主图State
class MainState(TypedDict):
    """Main Graph State - 包含所有数据"""
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    user_profile: Optional[dict]
    recommendations: list
    compliance_checks: list

def create_main_graph(store):
    """创建主图"""
    
    # 创建子图
    profile_subgraph = create_profile_subgraph(store)
    recommendation_subgraph = create_recommendation_subgraph(store)
    compliance_subgraph = create_compliance_subgraph(store)
    
    # 包装子图为节点（转换State）
    async def profile_node(state: MainState):
        """Profile子图节点"""
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
        """Recommendation子图节点"""
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
        """Compliance子图节点"""
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

---

### Phase 2: Store API集成

#### 2.1 初始化Store

```python
# utils/store_manager.py

from langgraph.store.postgres import PostgresStore
from typing import Optional

class StoreManager:
    """Store API管理器"""
    
    def __init__(self, db_uri: str):
        self.store = PostgresStore.from_conn_string(db_uri)
        self.store.setup()
    
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

#### 2.2 槽位提取与存储

```python
# agents/slot_extraction.py

async def extract_and_store_slots(
    messages: list,
    user_id: str,
    store_manager: StoreManager
):
    """从对话中提取槽位并存储"""
    
    # 1. 提取槽位
    slots = {}
    for message in messages:
        if message.role == "user":
            # 使用LLM或规则提取
            extracted = await extract_slots_from_text(message.content)
            slots.update(extracted)
    
    # 2. 存储到Store API
    if slots:
        store_manager.update_user_profile(user_id, slots)
    
    return slots
```

---

### Phase 3: 三层存储优化

#### 3.1 简化压缩逻辑

```python
# memory/warm_data_layer.py (修改)

class ConversationCompressor:
    """简化的压缩器 - 不再需要保留槽位"""
    
    async def compress_messages(self, messages: List[Message]) -> str:
        """压缩消息（槽位已在Store API中）"""
        
        # 1. 格式化对话
        conversation_text = self._format_messages(messages)
        
        # 2. LLM压缩
        if self.llm_client:
            summary = await self._compress_with_llm(conversation_text)
        else:
            summary = self._compress_rule_based(messages)
        
        # 3. 返回摘要（不附加槽位）
        return summary
```

#### 3.2 移除Context Isolation

```python
# memory/warm_data_layer.py (修改)

async def get_full_context_for_agent(
    self,
    hot_messages: List[Message]
) -> str:
    """
    构建完整上下文（移除target_agent参数）
    
    子图架构已实现隔离，无需运行时过滤
    """
    warm_context = await self.get_warm_context()
    
    context_parts = []
    
    # 1. 压缩历史
    if warm_context["compressed_history"]:
        context_parts.append("[历史对话摘要]")
        context_parts.append(warm_context["compressed_history"])
        context_parts.append("")
    
    # 2. 未压缩温数据
    if warm_context["warm_messages"]:
        context_parts.append("[温数据层对话]")
        context_parts.append(
            self.compressor._format_recent_messages(
                warm_context["warm_messages"]
            )
        )
        context_parts.append("")
    
    # 3. 热数据
    if hot_messages:
        context_parts.append("[最近对话]")
        context_parts.append(
            self.compressor._format_recent_messages(hot_messages)
        )
    
    return "\n".join(context_parts)
```

---

## 迁移计划

### Step 1: 准备工作
1. ✅ 安装依赖
   ```bash
   pip install langgraph==1.0.0 langchain==1.0.0
   pip install langgraph-checkpoint-postgres
   ```

2. ✅ 初始化Store
   ```python
   from langgraph.store.postgres import PostgresStore
   
   store = PostgresStore.from_conn_string(DB_URI)
   store.setup()
   ```

### Step 2: 重构子图
1. 定义子图State（`models/subgraph_states.py`）
2. 创建Profile子图（`agents/profile_subgraph.py`）
3. 创建Recommendation子图（`agents/recommendation_subgraph.py`）
4. 创建Compliance子图（`agents/compliance_subgraph.py`）

### Step 3: 创建主图
1. 定义主图State（`models/main_state.py`）
2. 创建主图并集成子图（`agents/main_graph.py`）
3. 实现State转换逻辑

### Step 4: 集成Store API
1. 创建StoreManager（`utils/store_manager.py`）
2. 修改Profile子图，集成槽位存储
3. 修改Recommendation子图，从Store读取画像

### Step 5: 优化三层存储
1. 简化压缩逻辑（移除槽位保留）
2. 移除Context Isolation代码
3. 更新上下文构建方法

### Step 6: 测试验证
1. 单元测试各子图
2. 集成测试主图
3. 验证Store API读写
4. 验证三层存储

---

## 关键问题确认

### Q1: Store API的namespace设计
**建议**：
```python
# 用户画像
namespace = ("users", user_id)
key = "profile"

# 会话相关数据
namespace = ("sessions", session_id)
key = "metadata"
```

你同意这个设计吗？

### Q2: 三层存储的进一步优化
**当前问题**：
- 压缩历史仍然很长（100轮对话 → 5700 tokens）
- 是否需要引入语义检索？

**建议**：
- Phase 1: 先完成子图重构和Store API集成
- Phase 2: 再评估是否需要语义检索

你同意吗？

### Q3: 子图的checkpointer设置
**问题**：子图是否需要独立的checkpointer？

**建议**：
- Profile子图：使用per-invocation（默认，继承父图）
- Recommendation子图：使用per-invocation
- Compliance子图：使用per-invocation

你同意吗？

---

## 下一步

请确认以上设计方案，我将开始实施：
1. 创建子图State定义
2. 重构Agent为子图
3. 集成Store API
4. 优化三层存储

有任何疑问或需要调整的地方，请告诉我！

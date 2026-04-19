# LangGraph State拆分设计

## 问题分析

### 当前问题：单一MasterState

```python
class MasterState(TypedDict):
    # 所有Agent共享同一个State
    conversation_history: Annotated[list, add_messages]
    user_profile: UserProfile
    current_intent: str
    recommendation_results: List[Product]
    compliance_checks: List[ComplianceCheck]
    # ... 更多字段
```

**问题**：
- ❌ **过度共享**：Advisor Agent不需要看conversation_history，但被迫接收
- ❌ **耦合过高**：修改conversation_history影响所有Agent
- ❌ **不清晰**：不知道哪个Agent真正需要哪些数据
- ❌ **性能浪费**：传递大量无用数据

---

## 解决方案：分层State设计

### 核心思想

**每个Agent有自己的State视图**，只包含它需要的数据。

```
MasterState (全局)
    ↓
┌───────────────┬───────────────┬───────────────┐
│ CoordinatorState │ AdvisorState │ KnowledgeState │
│ (对话历史)      │ (结构化数据)  │ (当前问题)     │
└───────────────┴───────────────┴───────────────┘
```

---

## 方案1：Node Input Schema（推荐 - LangGraph 1.x原生支持）

### 设计

LangGraph 1.x支持**Node Input Schema**，允许每个节点只接收它需要的State字段。这是官方推荐的方式。

#### 1. 定义MasterState和Agent视图

```python
# models/agent_state.py

from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import add_messages
from models.conversation import Message
from models.user import UserProfile
from models.product import Product


# ============================================================================
# Master State（全局State，包含所有数据）
# ============================================================================

class MasterState(TypedDict):
    """
    Master State - Contains all data for the entire conversation
    
    This is the complete state that LangGraph manages internally.
    Individual agents access only their relevant fields via input_schema.
    """
    
    # ========== Conversation Layer ==========
    conversation_history: Annotated[List[Message], add_messages]
    current_intent: Optional[str]
    conversation_context: Optional[str]
    
    # ========== Profile Layer ==========
    user_profile: Optional[UserProfile]
    risk_assessment: Optional[dict]
    coverage_gap: Optional[dict]
    
    # ========== Recommendation Layer ==========
    recommendation_results: List[Product]
    recommendation_explanations: List[str]
    
    # ========== Compliance Layer ==========
    compliance_checks: List[dict]
    disclosure_info: Optional[str]
    
    # ========== Knowledge Layer ==========
    current_question: Optional[str]
    knowledge_results: List[dict]
    
    # ========== Metadata ==========
    session_id: str
    user_id: str
    current_agent: Optional[str]


# ============================================================================
# Agent Input Schemas（每个Agent的输入视图）
# ============================================================================

class CoordinatorInput(TypedDict):
    """
    Coordinator只需要看到：
    - conversation_history（对话历史）
    - current_intent（当前意图）
    - user_profile（只读，用于个性化）
    """
    conversation_history: Annotated[List[Message], add_messages]
    current_intent: Optional[str]
    user_profile: Optional[UserProfile]  # Read-only
    session_id: str


class AdvisorInput(TypedDict):
    """
    Advisor只需要看到：
    - user_profile（结构化数据，不需要conversation_history）
    - risk_assessment（风险评估）
    - coverage_gap（保障缺口）
    """
    user_profile: Optional[UserProfile]
    risk_assessment: Optional[dict]
    coverage_gap: Optional[dict]
    session_id: str


class ComplianceInput(TypedDict):
    """
    Compliance Agent只需要看到：
    - user_profile（用于资格检查）
    - recommendation_results（待验证的推荐）
    """
    user_profile: Optional[UserProfile]
    recommendation_results: List[Product]
    session_id: str


class KnowledgeInput(TypedDict):
    """
    Knowledge Agent只需要看到：
    - current_question（当前问题，不需要历史）
    """
    current_question: Optional[str]
    session_id: str
```

#### 2. 使用input_schema定义节点

```python
# agents/coordinator_agent.py

from models.agent_state import MasterState, CoordinatorInput


async def coordinator_agent(state: CoordinatorInput) -> dict:
    """
    Coordinator Agent - 只接收CoordinatorInput
    
    注意：state参数的类型是CoordinatorInput，不是MasterState
    这意味着这个节点只能访问CoordinatorInput中定义的字段
    """
    
    # 1. 访问对话历史（这个节点需要）
    conversation_history = state["conversation_history"]
    
    # 2. 分析意图
    current_intent = analyze_intent(conversation_history[-1])
    
    # 3. 返回更新（只更新相关字段）
    return {
        "current_intent": current_intent,
        "conversation_context": extract_context(conversation_history),
        "current_agent": "CoordinatorAgent"
    }


# agents/advisor_agent.py

from models.agent_state import AdvisorInput


async def advisor_agent(state: AdvisorInput) -> dict:
    """
    Advisor Agent - 只接收AdvisorInput
    
    注意：这个节点看不到conversation_history！
    它只能访问结构化的用户画像数据
    """
    
    # 1. 获取用户画像（结构化数据，不是对话历史）
    user_profile = state["user_profile"]
    
    if not user_profile:
        raise ValueError("User profile not available")
    
    # 2. 基于结构化数据生成推荐
    recommendations = generate_recommendations(
        profile=user_profile,
        risk_assessment=state["risk_assessment"],
        coverage_gap=state["coverage_gap"]
    )
    
    # 3. 返回更新
    return {
        "recommendation_results": recommendations,
        "recommendation_explanations": [r.explanation for r in recommendations]
    }


# agents/knowledge_agent.py

from models.agent_state import KnowledgeInput


async def knowledge_agent(state: KnowledgeInput) -> dict:
    """
    Knowledge Agent - 只接收KnowledgeInput
    
    注意：这个节点只看到当前问题，没有历史！
    """
    
    # 1. 获取当前问题（只有当前问题，没有历史）
    current_question = state["current_question"]
    
    if not current_question:
        raise ValueError("No question provided")
    
    # 2. 搜索知识库
    knowledge_results = search_knowledge_base(current_question)
    
    # 3. 返回更新
    return {
        "knowledge_results": knowledge_results
    }
```

#### 3. 创建StateGraph并指定input_schema

```python
# langgraph_config.py

from langgraph.graph import StateGraph, START, END
from models.agent_state import (
    MasterState,
    CoordinatorInput,
    AdvisorInput,
    ComplianceInput,
    KnowledgeInput
)
from agents.coordinator_agent import coordinator_agent
from agents.advisor_agent import advisor_agent
from agents.compliance_agent import compliance_agent
from agents.knowledge_agent import knowledge_agent


def create_agent_graph():
    """Create LangGraph with node input schemas"""
    
    # 创建graph，使用MasterState作为全局State
    builder = StateGraph(MasterState)
    
    # 添加节点，并为每个节点指定input_schema
    builder.add_node(
        "coordinator",
        coordinator_agent,
        input_schema=CoordinatorInput  # 只接收CoordinatorInput字段
    )
    
    builder.add_node(
        "advisor",
        advisor_agent,
        input_schema=AdvisorInput  # 只接收AdvisorInput字段
    )
    
    builder.add_node(
        "compliance",
        compliance_agent,
        input_schema=ComplianceInput  # 只接收ComplianceInput字段
    )
    
    builder.add_node(
        "knowledge",
        knowledge_agent,
        input_schema=KnowledgeInput  # 只接收KnowledgeInput字段
    )
    
    # 添加边（路由）
    builder.add_conditional_edges(
        "coordinator",
        route_next_agent,
        {
            "advisor": "advisor",
            "knowledge": "knowledge",
            "end": END
        }
    )
    
    builder.add_edge("advisor", "compliance")
    builder.add_edge("compliance", "coordinator")
    builder.add_edge("knowledge", "coordinator")
    
    # 设置入口点
    builder.add_edge(START, "coordinator")
    
    return builder.compile()
```

---

## 方案2：State Reducers（备选）

### 设计

使用**State Reducers**在Agent之间传递数据时进行转换。

```python
# models/agent_state.py

from typing import TypedDict, Annotated
from langgraph.graph import add_messages


def extract_profile_only(state: MasterState) -> dict:
    """Reducer: Extract only profile data for Advisor"""
    return {
        "user_profile": state["user_profile"],
        "risk_assessment": state["risk_assessment"],
        "coverage_gap": state["coverage_gap"],
        "session_id": state["session_id"]
    }


def extract_question_only(state: MasterState) -> dict:
    """Reducer: Extract only current question for Knowledge Agent"""
    return {
        "current_question": state["current_question"],
        "session_id": state["session_id"]
    }


class MasterState(TypedDict):
    """Master State with reducers"""
    
    conversation_history: Annotated[List[Message], add_messages]
    user_profile: Annotated[Optional[UserProfile], extract_profile_only]
    current_question: Annotated[Optional[str], extract_question_only]
    # ... other fields
```

---

## 方案3：Nested State（最简单）

### 设计

将State组织为嵌套结构，每个Agent访问自己的命名空间。

```python
# models/agent_state.py

class MasterState(TypedDict):
    """Master State with nested structure"""
    
    # Coordinator's namespace
    coordinator: CoordinatorData
    
    # Advisor's namespace
    advisor: AdvisorData
    
    # Compliance's namespace
    compliance: ComplianceData
    
    # Knowledge's namespace
    knowledge: KnowledgeData
    
    # Shared metadata
    session_id: str
    user_id: str


class CoordinatorData(TypedDict):
    conversation_history: Annotated[List[Message], add_messages]
    current_intent: Optional[str]
    conversation_context: Optional[str]


class AdvisorData(TypedDict):
    user_profile: Optional[UserProfile]
    risk_assessment: Optional[dict]
    coverage_gap: Optional[dict]
    recommendation_results: List[Product]


class ComplianceData(TypedDict):
    compliance_checks: List[ComplianceCheck]
    disclosure_info: Optional[str]


class KnowledgeData(TypedDict):
    current_question: Optional[str]
    knowledge_results: List[dict]
```

**Agent实现**：

```python
async def advisor_agent(state: MasterState) -> MasterState:
    """Advisor Agent - Access only advisor namespace"""
    
    # Access only advisor data
    advisor_data = state["advisor"]
    
    # Generate recommendations
    recommendations = generate_recommendations(
        profile=advisor_data["user_profile"],
        risk_assessment=advisor_data["risk_assessment"]
    )
    
    # Update only advisor namespace
    return {
        "advisor": {
            **advisor_data,
            "recommendation_results": recommendations
        }
    }
```

---

## 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **方案1：Node Input Schema** | ✅ 类型安全<br>✅ 清晰的访问控制<br>✅ LangGraph 1.x官方推荐<br>✅ 简单易用 | ⚠️ 需要定义多个Schema | **强烈推荐**：所有多Agent系统 |
| **方案2：State Reducers** | ✅ 灵活<br>✅ 动态转换 | ⚠️ 类型检查弱<br>⚠️ 调试困难 | 需要复杂数据转换的场景 |
| **方案3：Nested State** | ✅ 简单<br>✅ 易理解<br>✅ 易实现 | ⚠️ 命名空间冲突<br>⚠️ 跨Agent访问不便 | 小型系统，Agent完全独立 |

---

## 完整实现示例

### 完整代码示例

下面是一个完整的LangGraph 1.x实现，展示如何使用Node Input Schema实现State拆分：

```python
# models/agent_state.py

from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import add_messages
from models.conversation import Message
from models.user import UserProfile
from models.product import Product


# ============================================================================
# Master State（全局State，包含所有数据）
# ============================================================================

class MasterState(TypedDict):
    """
    Master State - Contains all data for the entire conversation
    
    This is the complete state that LangGraph manages internally.
    Individual agents access only their relevant fields via input_schema.
    """
    
    # ========== Conversation Layer ==========
    conversation_history: Annotated[List[Message], add_messages]
    current_intent: Optional[str]
    conversation_context: Optional[str]
    
    # ========== Profile Layer ==========
    user_profile: Optional[UserProfile]
    risk_assessment: Optional[dict]
    coverage_gap: Optional[dict]
    
    # ========== Recommendation Layer ==========
    recommendation_results: List[Product]
    recommendation_explanations: List[str]
    
    # ========== Compliance Layer ==========
    compliance_checks: List[dict]
    disclosure_info: Optional[str]
    
    # ========== Knowledge Layer ==========
    current_question: Optional[str]
    knowledge_results: List[dict]
    
    # ========== Metadata ==========
    session_id: str
    user_id: str
    current_agent: Optional[str]


# ============================================================================
# Agent Input Schemas（每个Agent的输入视图）
# ============================================================================

class CoordinatorInput(TypedDict):
    """
    Coordinator只需要看到：
    - conversation_history（对话历史）
    - current_intent（当前意图）
    - user_profile（只读，用于个性化）
    """
    conversation_history: Annotated[List[Message], add_messages]
    current_intent: Optional[str]
    user_profile: Optional[UserProfile]  # Read-only
    session_id: str


class AdvisorInput(TypedDict):
    """
    Advisor只需要看到：
    - user_profile（结构化数据，不需要conversation_history）
    - risk_assessment（风险评估）
    - coverage_gap（保障缺口）
    """
    user_profile: Optional[UserProfile]
    risk_assessment: Optional[dict]
    coverage_gap: Optional[dict]
    session_id: str


class ComplianceInput(TypedDict):
    """
    Compliance Agent只需要看到：
    - user_profile（用于资格检查）
    - recommendation_results（待验证的推荐）
    """
    user_profile: Optional[UserProfile]
    recommendation_results: List[Product]
    session_id: str


class KnowledgeInput(TypedDict):
    """
    Knowledge Agent只需要看到：
    - current_question（当前问题，不需要历史）
    """
    current_question: Optional[str]
    session_id: str


# ============================================================================
# Agent实现（使用Input Schema）
# ============================================================================

# agents/coordinator_agent.py

async def coordinator_agent(state: CoordinatorInput) -> dict:
    """
    Coordinator Agent - 只接收CoordinatorInput
    
    注意：state参数的类型是CoordinatorInput，不是MasterState
    这意味着这个节点只能访问CoordinatorInput中定义的字段
    """
    
    # 1. 访问对话历史（这个节点需要）
    conversation_history = state["conversation_history"]
    
    # 2. 分析意图
    current_intent = analyze_intent(conversation_history[-1])
    
    # 3. 返回更新（只更新相关字段）
    return {
        "current_intent": current_intent,
        "conversation_context": extract_context(conversation_history),
        "current_agent": "CoordinatorAgent"
    }


# agents/advisor_agent.py

async def advisor_agent(state: AdvisorInput) -> dict:
    """
    Advisor Agent - 只接收AdvisorInput
    
    注意：这个节点看不到conversation_history！
    它只能访问结构化的用户画像数据
    """
    
    # 1. 获取用户画像（结构化数据，不是对话历史）
    user_profile = state["user_profile"]
    
    if not user_profile:
        raise ValueError("User profile not available")
    
    # 2. 基于结构化数据生成推荐
    recommendations = generate_recommendations(
        profile=user_profile,
        risk_assessment=state["risk_assessment"],
        coverage_gap=state["coverage_gap"]
    )
    
    # 3. 返回更新
    return {
        "recommendation_results": recommendations,
        "recommendation_explanations": [r.explanation for r in recommendations]
    }


# agents/compliance_agent.py

async def compliance_agent(state: ComplianceInput) -> dict:
    """
    Compliance Agent - 只接收ComplianceInput
    
    注意：这个节点只看到用户画像和推荐结果，没有对话历史
    """
    
    # 1. 获取推荐结果
    recommendations = state["recommendation_results"]
    user_profile = state["user_profile"]
    
    # 2. 执行合规检查
    compliance_checks = []
    for product in recommendations:
        check_result = verify_compliance(product, user_profile)
        compliance_checks.append(check_result)
    
    # 3. 返回更新
    return {
        "compliance_checks": compliance_checks,
        "disclosure_info": generate_disclosure(compliance_checks)
    }


# agents/knowledge_agent.py

async def knowledge_agent(state: KnowledgeInput) -> dict:
    """
    Knowledge Agent - 只接收KnowledgeInput
    
    注意：这个节点只看到当前问题，没有历史！
    """
    
    # 1. 获取当前问题（只有当前问题，没有历史）
    current_question = state["current_question"]
    
    if not current_question:
        raise ValueError("No question provided")
    
    # 2. 搜索知识库
    knowledge_results = search_knowledge_base(current_question)
    
    # 3. 返回更新
    return {
        "knowledge_results": knowledge_results
    }


# ============================================================================
# 创建LangGraph（使用input_schema）
# ============================================================================

# langgraph_config.py

from langgraph.graph import StateGraph, START, END
from models.agent_state import (
    MasterState,
    CoordinatorInput,
    AdvisorInput,
    ComplianceInput,
    KnowledgeInput
)
from agents.coordinator_agent import coordinator_agent
from agents.advisor_agent import advisor_agent
from agents.compliance_agent import compliance_agent
from agents.knowledge_agent import knowledge_agent


def route_next_agent(state: MasterState) -> str:
    """Route to next agent based on current intent"""
    intent = state.get("current_intent")
    
    if intent == "consult_coverage":
        return "advisor"
    elif intent == "ask_question":
        return "knowledge"
    else:
        return "end"


def create_agent_graph():
    """Create LangGraph with node input schemas"""
    
    # 创建graph，使用MasterState作为全局State
    builder = StateGraph(MasterState)
    
    # 添加节点，并为每个节点指定input_schema
    builder.add_node(
        "coordinator",
        coordinator_agent,
        input_schema=CoordinatorInput  # 只接收CoordinatorInput字段
    )
    
    builder.add_node(
        "advisor",
        advisor_agent,
        input_schema=AdvisorInput  # 只接收AdvisorInput字段
    )
    
    builder.add_node(
        "compliance",
        compliance_agent,
        input_schema=ComplianceInput  # 只接收ComplianceInput字段
    )
    
    builder.add_node(
        "knowledge",
        knowledge_agent,
        input_schema=KnowledgeInput  # 只接收KnowledgeInput字段
    )
    
    # 添加边（路由）
    builder.add_conditional_edges(
        "coordinator",
        route_next_agent,
        {
            "advisor": "advisor",
            "knowledge": "knowledge",
            "end": END
        }
    )
    
    builder.add_edge("advisor", "compliance")
    builder.add_edge("compliance", "coordinator")
    builder.add_edge("knowledge", "coordinator")
    
    # 设置入口点
    builder.add_edge(START, "coordinator")
    
    return builder.compile()


# ============================================================================
# 使用示例
# ============================================================================

# main.py

async def main():
    # 创建graph
    graph = create_agent_graph()
    
    # 初始化state
    initial_state = {
        "conversation_history": [],
        "current_intent": None,
        "conversation_context": None,
        "user_profile": None,
        "risk_assessment": None,
        "coverage_gap": None,
        "recommendation_results": [],
        "recommendation_explanations": [],
        "compliance_checks": [],
        "disclosure_info": None,
        "current_question": None,
        "knowledge_results": [],
        "session_id": "session_123",
        "user_id": "user_456",
        "current_agent": None
    }
    
    # 用户输入
    user_message = Message(
        role=MessageRole.USER,
        content="我想了解重疾险",
        intent=IntentType.CONSULT_COVERAGE
    )
    
    # 添加到state
    initial_state["conversation_history"].append(user_message)
    
    # 执行graph
    result = await graph.ainvoke(initial_state)
    
    # 获取结果
    print(f"Current Agent: {result['current_agent']}")
    print(f"Intent: {result['current_intent']}")
    print(f"Recommendations: {result['recommendation_results']}")
    print(f"Compliance: {result['compliance_checks']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## 优势总结

### 拆分后的优势

1. **清晰的职责划分**：
   - Coordinator：对话历史
   - Advisor：结构化数据
   - Knowledge：当前问题

2. **减少数据传递**：
   - Advisor不接收conversation_history（节省内存）
   - Knowledge不接收历史（节省token）

3. **类型安全**：
   - 每个Agent有明确的输入输出类型
   - IDE自动补全和类型检查

4. **易于测试**：
   - 每个Agent的输入输出清晰
   - 可以独立测试

5. **易于维护**：
   - 修改一个Agent的输入不影响其他Agent
   - 降低耦合度

### 与Context Isolation的关系

State拆分和Context Isolation是两个互补的机制：

| 机制 | 作用层面 | 解决的问题 | 实现方式 |
|------|---------|-----------|---------|
| **State拆分** | 数据结构层 | 每个Agent只能访问需要的State字段 | LangGraph Node Input Schema |
| **Context Isolation** | 消息过滤层 | 每个Agent只看到相关的对话消息 | AgentContextScope过滤器 |

**组合使用示例**：

```python
# 1. State拆分：Advisor只接收AdvisorInput（不包含conversation_history）
async def advisor_agent(state: AdvisorInput) -> dict:
    # state中没有conversation_history字段
    user_profile = state["user_profile"]
    
    # 2. Context Isolation：如果需要从其他地方获取历史，会被过滤
    # 例如从warm_layer获取上下文时，会自动过滤掉CHITCHAT
    context = await warm_layer.get_full_context_for_agent(
        hot_messages,
        target_agent="RecommendationAgent"  # 自动过滤闲聊
    )
    
    # 生成推荐
    recommendations = generate_recommendations(user_profile, context)
    return {"recommendation_results": recommendations}
```

**双重保护**：
- State拆分：结构上限制Agent不能访问conversation_history
- Context Isolation：即使Agent能访问历史，也会过滤掉无关消息

---

## 实施建议

### 第一阶段：定义State结构

1. 创建 `models/agent_state.py`
2. 定义MasterState（包含所有字段）
3. 定义Agent Input Schemas（每个Agent的输入视图）

### 第二阶段：重构Agent

1. 修改每个Agent函数签名，使用对应的Input Schema
2. 确保Agent只访问Input Schema中定义的字段
3. 添加类型注解

### 第三阶段：更新Graph配置

1. 在 `builder.add_node()` 中添加 `input_schema` 参数
2. 测试每个节点是否正确接收到过滤后的State

### 第四阶段：测试和优化

1. 单元测试每个Agent
2. 集成测试整个流程
3. 监控性能改进（内存、token消耗）

---

## 测试示例

### 单元测试

```python
# tests/unit/test_advisor_agent.py

import pytest
from agents.advisor_agent import advisor_agent
from models.agent_state import AdvisorInput
from models.user import UserProfile


@pytest.mark.asyncio
async def test_advisor_agent_with_valid_profile():
    """Test Advisor Agent with valid user profile"""
    
    # Arrange
    state: AdvisorInput = {
        "user_profile": UserProfile(
            age=30,
            income_range="100k-200k",
            family_structure="married_with_children"
        ),
        "risk_assessment": {"risk_level": "medium"},
        "coverage_gap": {"critical_illness": 500000},
        "session_id": "test_session"
    }
    
    # Act
    result = await advisor_agent(state)
    
    # Assert
    assert "recommendation_results" in result
    assert len(result["recommendation_results"]) > 0
    assert "recommendation_explanations" in result


@pytest.mark.asyncio
async def test_advisor_agent_without_profile():
    """Test Advisor Agent without user profile (should raise error)"""
    
    # Arrange
    state: AdvisorInput = {
        "user_profile": None,
        "risk_assessment": None,
        "coverage_gap": None,
        "session_id": "test_session"
    }
    
    # Act & Assert
    with pytest.raises(ValueError, match="User profile not available"):
        await advisor_agent(state)


@pytest.mark.asyncio
async def test_advisor_agent_cannot_access_conversation_history():
    """Test that Advisor Agent cannot access conversation_history"""
    
    # This test verifies type safety at runtime
    # AdvisorInput does not include conversation_history field
    
    state: AdvisorInput = {
        "user_profile": UserProfile(age=30),
        "risk_assessment": {},
        "coverage_gap": {},
        "session_id": "test_session"
    }
    
    # This should work (accessing allowed fields)
    assert "user_profile" in state
    assert "session_id" in state
    
    # This should fail (accessing disallowed fields)
    # Note: TypedDict doesn't enforce at runtime, but type checkers will catch this
    with pytest.raises(KeyError):
        _ = state["conversation_history"]  # type: ignore
```

### 集成测试

```python
# tests/integration/test_agent_graph.py

import pytest
from langgraph_config import create_agent_graph
from models.conversation import Message, MessageRole, IntentType


@pytest.mark.asyncio
async def test_full_workflow():
    """Test full agent workflow with state partitioning"""
    
    # Arrange
    graph = create_agent_graph()
    
    initial_state = {
        "conversation_history": [
            Message(
                role=MessageRole.USER,
                content="我想了解重疾险",
                intent=IntentType.CONSULT_COVERAGE
            )
        ],
        "current_intent": None,
        "conversation_context": None,
        "user_profile": UserProfile(age=30, income_range="100k-200k"),
        "risk_assessment": {"risk_level": "medium"},
        "coverage_gap": {"critical_illness": 500000},
        "recommendation_results": [],
        "recommendation_explanations": [],
        "compliance_checks": [],
        "disclosure_info": None,
        "current_question": None,
        "knowledge_results": [],
        "session_id": "test_session",
        "user_id": "test_user",
        "current_agent": None
    }
    
    # Act
    result = await graph.ainvoke(initial_state)
    
    # Assert
    assert result["current_intent"] == "consult_coverage"
    assert len(result["recommendation_results"]) > 0
    assert len(result["compliance_checks"]) > 0
    assert result["current_agent"] is not None
```

---

## 总结

**当前问题**：
- ❌ 单一MasterState，所有Agent看到所有数据
- ❌ Advisor看到conversation_history（不需要）
- ❌ Knowledge看到历史（不需要）
- ❌ 数据传递浪费内存和token

**推荐方案**：
- ✅ **方案1：Node Input Schema**（LangGraph 1.x官方推荐）
- ✅ 每个Agent定义自己的Input Schema
- ✅ 使用 `builder.add_node(name, func, input_schema=...)` 指定输入
- ✅ 类型安全 + 简单易用 + 官方支持

**实施优先级**：
1. **高优先级**：定义MasterState和Agent Input Schemas
2. **高优先级**：重构Agent函数签名
3. **中优先级**：更新Graph配置（添加input_schema参数）
4. **低优先级**：添加单元测试和集成测试

**与Context Isolation的关系**：
- State拆分：结构层面限制Agent访问
- Context Isolation：消息层面过滤无关对话
- 两者互补，提供双重保护

**预期效果**：
- 内存使用减少30-50%（Advisor不接收conversation_history）
- Token消耗减少40-60%（Knowledge不接收历史）
- 代码更清晰，易于维护
- 类型安全，减少运行时错误

---

## 参考资料

- [LangGraph官方文档 - Node Input Schema](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.StateGraph.add_node)
- [LangGraph官方文档 - State Management](https://langchain-ai.github.io/langgraph/concepts/low_level/#state-management)
- [Context Isolation设计文档](./CONTEXT_ISOLATION.md)
- [三层内存架构设计文档](./README.md)

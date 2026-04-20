# 多Agent上下文隔离设计

## 问题分析

### 当前问题

当前的 `get_full_context_for_agent()` 方法将所有对话历史拼接成一个巨型字符串：

```python
async def get_full_context_for_agent(self, hot_messages: List[Message]) -> str:
    """当前实现：返回所有对话历史"""
    context_parts = []
    
    # 1. 压缩历史（所有Agent的对话）
    if compressed_history:
        context_parts.append("[历史对话摘要]")
        context_parts.append(compressed_history)
    
    # 2. 未压缩温数据（所有Agent的对话）
    if warm_messages:
        context_parts.append("[温数据层对话]")
        context_parts.append(format_messages(warm_messages))
    
    # 3. 热数据（所有Agent的对话）
    if hot_messages:
        context_parts.append("[最近对话]")
        context_parts.append(format_messages(hot_messages))
    
    return "\n".join(context_parts)
```

**问题场景**：

在多Agent架构中（Profile Collection Agent、Recommendation Agent、Compliance Agent），每个Agent都有不同的职责：

1. **Profile Collection Agent**：
   - 收集用户画像
   - 处理闲聊
   - 引导用户提供信息

2. **Recommendation Agent**：
   - 生成产品推荐
   - 分析保障缺口
   - 产品对比

3. **Compliance Agent**：
   - 合规检查
   - 信息披露

**问题示例**：

```
用户: 今天天气真好啊
Profile Agent: 是的，今天阳光明媚。不过我们还是回到保险话题吧，您的年龄是？
用户: 我30岁
Profile Agent: 好的，您的职业是？
用户: 软件工程师
Profile Agent: 明白了，您的年收入大概是多少？
用户: 30万
Profile Agent: 收集完成，现在为您推荐产品...

[切换到 Recommendation Agent]

Recommendation Agent 收到的上下文：
[历史对话摘要]
...

[最近对话]
用户: 今天天气真好啊  ← 闲聊，与推荐无关
Profile Agent: 是的，今天阳光明媚...  ← 闲聊，与推荐无关
用户: 我30岁  ← 有用
Profile Agent: 好的，您的职业是？  ← 有用
用户: 软件工程师  ← 有用
...
```

**问题**：
- ❌ Recommendation Agent 看到了闲聊内容（"今天天气真好"）
- ❌ 闲聊内容消耗了token，但对推荐没有帮助
- ❌ 可能干扰LLM的推荐决策
- ❌ 增加了成本和延迟

---

## 解决方案

### 方案1：基于Agent的上下文过滤（推荐）

**核心思想**：每个Agent只看到与自己相关的对话历史。

#### 实现方式

**1. 在Message模型中添加标记**

Message模型已经有 `agent_name` 字段：

```python
class Message(BaseModel):
    role: MessageRole
    content: str
    agent_name: Optional[str] = None  # 生成消息的Agent名称
    intent: Optional[IntentType] = None  # 用户意图
```

**2. 定义Agent的上下文范围**

```python
# memory/context_filter.py

class AgentContextScope:
    """Agent上下文范围定义"""
    
    # 每个Agent可以看到的其他Agent的消息
    AGENT_VISIBILITY = {
        "ProfileCollectionAgent": {
            "visible_agents": ["ProfileCollectionAgent"],  # 只看自己的对话
            "visible_intents": [
                IntentType.PROVIDE_INFO,
                IntentType.MODIFY_INFO,
                IntentType.ASK_QUESTION,
                # 不包括 CHITCHAT
            ]
        },
        "RecommendationAgent": {
            "visible_agents": [
                "ProfileCollectionAgent",  # 看Profile Agent收集的信息
                "RecommendationAgent"  # 看自己的对话
            ],
            "visible_intents": [
                IntentType.CONSULT_COVERAGE,
                IntentType.COMPARE_PRODUCTS,
                IntentType.REQUEST_EXPLANATION,
                IntentType.PROVIDE_INFO,
                # 不包括 CHITCHAT
            ]
        },
        "ComplianceAgent": {
            "visible_agents": [
                "ProfileCollectionAgent",  # 看用户画像
                "RecommendationAgent",  # 看推荐结果
                "ComplianceAgent"  # 看自己的对话
            ],
            "visible_intents": [
                IntentType.PROVIDE_INFO,
                IntentType.CONSULT_COVERAGE,
                # 不包括 CHITCHAT
            ]
        }
    }
    
    @classmethod
    def should_include_message(
        cls,
        message: Message,
        target_agent: str
    ) -> bool:
        """判断消息是否应该包含在目标Agent的上下文中"""
        
        scope = cls.AGENT_VISIBILITY.get(target_agent)
        if not scope:
            return True  # 默认包含
        
        # 1. 检查Agent可见性
        if message.role == MessageRole.ASSISTANT:
            if message.agent_name not in scope["visible_agents"]:
                return False
        
        # 2. 检查意图可见性（用户消息）
        if message.role == MessageRole.USER:
            if message.intent and message.intent not in scope["visible_intents"]:
                return False
        
        return True
```

**3. 修改 `get_full_context_for_agent()` 方法**

```python
# memory/warm_data_layer.py

async def get_full_context_for_agent(
    self,
    hot_messages: List[Message],
    target_agent: str  # 新增参数：目标Agent名称
) -> str:
    """
    Build complete context for specific agent from warm + hot data
    
    This combines:
    1. Compressed history (filtered by agent)
    2. Uncompressed warm messages (filtered by agent)
    3. Recent hot messages (filtered by agent)
    
    Args:
        hot_messages: Recent messages from hot data layer
        target_agent: Target agent name for context filtering
        
    Returns:
        Formatted context string for agent consumption
    """
    try:
        from memory.context_filter import AgentContextScope
        
        warm_context = await self.get_warm_context()
        
        # Build layered context with filtering
        context_parts = []
        
        # 1. Add compressed history if exists
        # Note: Compressed history should be pre-filtered during compression
        if warm_context["compressed_history"]:
            context_parts.append("[历史对话摘要]")
            context_parts.append(warm_context["compressed_history"])
            context_parts.append("")
        
        # 2. Add uncompressed warm messages (filtered)
        if warm_context["warm_messages"]:
            filtered_warm = [
                msg for msg in warm_context["warm_messages"]
                if AgentContextScope.should_include_message(msg, target_agent)
            ]
            
            if filtered_warm:
                context_parts.append("[温数据层对话]")
                context_parts.append(
                    self.compressor._format_recent_messages(filtered_warm)
                )
                context_parts.append("")
        
        # 3. Add hot messages (filtered)
        if hot_messages:
            filtered_hot = [
                msg for msg in hot_messages
                if AgentContextScope.should_include_message(msg, target_agent)
            ]
            
            if filtered_hot:
                context_parts.append("[最近对话]")
                context_parts.append(
                    self.compressor._format_recent_messages(filtered_hot)
                )
        
        full_context = "\n".join(context_parts)
        
        logger.debug(
            f"Built filtered context for {target_agent}: session={self.session_id}, "
            f"total_tokens={self.compressor.count_tokens(full_context)}"
        )
        
        return full_context
        
    except Exception as e:
        logger.error(
            f"Failed to build full context: session={self.session_id}, "
            f"error={str(e)}"
        )
        raise
```

**4. 压缩时也需要过滤**

```python
# memory/warm_data_layer.py

async def _compress_and_archive(self, session_id: str, target_agent: str = None) -> None:
    """
    Compress warm messages and archive to compressed_history
    
    Args:
        session_id: Session ID to compress
        target_agent: Optional target agent for filtering (if None, compress all)
    """
    try:
        # ... 前面的代码 ...
        
        # 1. Parse messages
        messages = [Message(**m) for m in session.warm_messages]
        
        # 2. Filter messages if target_agent specified
        if target_agent:
            from memory.context_filter import AgentContextScope
            messages = [
                msg for msg in messages
                if AgentContextScope.should_include_message(msg, target_agent)
            ]
        
        # 3. Extract critical slots
        critical_slots = self.compressor.extract_slots_from_messages(messages)
        
        # 4. Compress messages
        compressed_summary = await self.compressor.compress_messages(
            messages,
            preserve_slots=critical_slots
        )
        
        # ... 后面的代码 ...
```

---

### 方案2：基于意图的上下文过滤（备选）

**核心思想**：根据消息的意图类型过滤，而不是Agent名称。

```python
class IntentBasedFilter:
    """基于意图的上下文过滤"""
    
    # 每个Agent关心的意图类型
    AGENT_INTENT_FILTER = {
        "ProfileCollectionAgent": [
            IntentType.PROVIDE_INFO,
            IntentType.MODIFY_INFO,
            IntentType.ASK_QUESTION,
        ],
        "RecommendationAgent": [
            IntentType.CONSULT_COVERAGE,
            IntentType.COMPARE_PRODUCTS,
            IntentType.REQUEST_EXPLANATION,
            IntentType.PROVIDE_INFO,
        ],
        "ComplianceAgent": [
            IntentType.PROVIDE_INFO,
            IntentType.CONSULT_COVERAGE,
        ]
    }
    
    @classmethod
    def filter_messages_by_intent(
        cls,
        messages: List[Message],
        target_agent: str
    ) -> List[Message]:
        """根据意图过滤消息"""
        
        allowed_intents = cls.AGENT_INTENT_FILTER.get(target_agent, [])
        
        filtered = []
        for msg in messages:
            # 助手消息：检查agent_name
            if msg.role == MessageRole.ASSISTANT:
                if msg.agent_name == target_agent:
                    filtered.append(msg)
            
            # 用户消息：检查intent
            elif msg.role == MessageRole.USER:
                if msg.intent in allowed_intents:
                    filtered.append(msg)
                elif msg.intent is None:
                    # 没有意图标记的消息，默认包含
                    filtered.append(msg)
        
        return filtered
```

---

### 方案3：分层存储（最彻底，但复杂度高）

**核心思想**：为每个Agent维护独立的对话历史。

```python
# 数据库表结构
class ConversationSession(Base):
    session_id = Column(String, primary_key=True)
    
    # 为每个Agent维护独立的消息列表
    profile_agent_messages = Column(JSON, default=[])
    recommendation_agent_messages = Column(JSON, default=[])
    compliance_agent_messages = Column(JSON, default=[])
    
    # 为每个Agent维护独立的压缩历史
    profile_agent_compressed = Column(Text, default="")
    recommendation_agent_compressed = Column(Text, default="")
    compliance_agent_compressed = Column(Text, default="")
```

**优点**：
- ✅ 完全隔离，每个Agent只看到自己的对话
- ✅ 压缩和存储都是独立的

**缺点**：
- ❌ 数据冗余（同一条消息可能存储多次）
- ❌ 复杂度高（需要维护多个消息列表）
- ❌ 不适合Agent之间需要共享信息的场景

---

## 推荐方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **方案1：基于Agent过滤** | ✅ 灵活<br>✅ 易实现<br>✅ 支持Agent间信息共享 | ⚠️ 需要维护可见性规则 | **推荐**：多Agent协作，需要部分信息共享 |
| **方案2：基于意图过滤** | ✅ 简单<br>✅ 易理解 | ⚠️ 依赖意图识别准确性 | 意图识别准确率高的场景 |
| **方案3：分层存储** | ✅ 完全隔离<br>✅ 性能好 | ❌ 数据冗余<br>❌ 复杂度高 | Agent完全独立，无信息共享需求 |

---

## 实现示例

### 使用方案1的完整示例

```python
# agents/recommendation_agent.py

class RecommendationAgent:
    def __init__(self, hot_layer, warm_layer):
        self.hot_layer = hot_layer
        self.warm_layer = warm_layer
        self.agent_name = "RecommendationAgent"
    
    async def generate_recommendations(self, profile: UserProfile):
        """生成推荐"""
        
        # 1. 获取热数据消息
        hot_messages = await self.hot_layer.get_hot_messages()
        
        # 2. 获取过滤后的完整上下文（只包含相关对话）
        full_context = await self.warm_layer.get_full_context_for_agent(
            hot_messages=hot_messages,
            target_agent=self.agent_name  # 指定目标Agent
        )
        
        # 3. 构建推荐提示词
        prompt = f"""
{full_context}

用户画像：
- 年龄：{profile.age}
- 职业：{profile.occupation}
- 年收入：{profile.annual_income}
- 家庭结构：{profile.family_structure}

请根据以上信息，推荐3-5款保险产品。
"""
        
        # 4. 调用LLM
        response = await self.llm.generate(prompt)
        
        return response
```

### 对比效果

**未过滤（当前实现）**：
```
[最近对话]
[10:00:00] 用户: 今天天气真好啊
[10:00:05] Profile Agent: 是的，今天阳光明媚。不过我们还是回到保险话题吧
[10:00:10] 用户: 好的，我30岁
[10:00:15] Profile Agent: 好的，您的职业是？
[10:00:20] 用户: 软件工程师
[10:00:25] Profile Agent: 明白了，您的年收入大概是多少？
[10:00:30] 用户: 30万

Token数：约500 tokens
```

**过滤后（方案1）**：
```
[最近对话]
[10:00:10] 用户: 好的，我30岁
[10:00:15] Profile Agent: 好的，您的职业是？
[10:00:20] 用户: 软件工程师
[10:00:25] Profile Agent: 明白了，您的年收入大概是多少？
[10:00:30] 用户: 30万

Token数：约300 tokens（减少40%）
```

---

## 配置示例

```python
# config/agent_context_config.py

AGENT_CONTEXT_CONFIG = {
    "ProfileCollectionAgent": {
        "visible_agents": ["ProfileCollectionAgent"],
        "visible_intents": [
            "provide_info",
            "modify_info",
            "ask_question",
        ],
        "exclude_intents": ["chitchat"],  # 明确排除闲聊
    },
    
    "RecommendationAgent": {
        "visible_agents": [
            "ProfileCollectionAgent",
            "RecommendationAgent"
        ],
        "visible_intents": [
            "consult_coverage",
            "compare_products",
            "request_explanation",
            "provide_info",
        ],
        "exclude_intents": ["chitchat"],
    },
    
    "ComplianceAgent": {
        "visible_agents": [
            "ProfileCollectionAgent",
            "RecommendationAgent",
            "ComplianceAgent"
        ],
        "visible_intents": [
            "provide_info",
            "consult_coverage",
        ],
        "exclude_intents": ["chitchat"],
    }
}
```

---

## 优势总结

### 方案1的优势

1. **Token节省**：
   - 过滤掉无关对话，减少40-60%的token消耗
   - 降低LLM调用成本

2. **提高准确性**：
   - 减少噪音，LLM更专注于相关信息
   - 避免闲聊干扰推荐决策

3. **灵活性**：
   - 可以配置每个Agent的可见范围
   - 支持Agent间信息共享

4. **可维护性**：
   - 清晰的可见性规则
   - 易于调试和优化

---

## 实施建议

### 第一阶段：基础过滤

1. 实现 `AgentContextScope` 类
2. 修改 `get_full_context_for_agent()` 方法，添加 `target_agent` 参数
3. 在所有Agent中使用新的API

### 第二阶段：压缩优化

1. 修改压缩逻辑，支持按Agent过滤
2. 为每个Agent维护独立的压缩历史（可选）

### 第三阶段：监控和优化

1. 监控过滤效果（token节省率）
2. 监控推荐准确性变化
3. 根据反馈调整可见性规则

---

## 总结

**当前问题**：
- ❌ 所有Agent看到所有对话历史
- ❌ 闲聊内容干扰专业Agent
- ❌ Token浪费

**推荐方案**：
- ✅ 方案1：基于Agent的上下文过滤
- ✅ 灵活、易实现、支持信息共享
- ✅ 显著减少token消耗
- ✅ 提高推荐准确性

**实施优先级**：
1. **高优先级**：实现基础过滤（排除闲聊）
2. **中优先级**：实现完整的可见性规则
3. **低优先级**：压缩时的Agent过滤

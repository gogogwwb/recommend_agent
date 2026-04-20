# Langfuse 集成指南

## 概述

Langfuse 是一个开源的 LLM 工程平台，提供可观测性、评估和 Prompt 管理功能。本项目使用 Langfuse 替代 LangSmith，实现 Agent 的监控、调试和评估。

## 为什么选择 Langfuse

| 特性 | Langfuse | LangSmith |
|------|----------|-----------|
| **开源** | ✅ MIT License | ❌ 闭源 SaaS |
| **自托管** | ✅ 完整功能支持 | ❌ 仅企业版 |
| **数据主权** | ✅ 可完全 air-gapped | ⚠️ 中等 |
| **框架支持** | ✅ 80+ 框架 | ⚠️ LangChain 优先 |
| **OpenTelemetry** | ✅ 原生支持 | ⚠️ 支持但不原生 |

## 默认指标支持情况

| 指标 | 默认支持 | 说明 |
|------|----------|------|
| **Token & 成本** | ✅ 自动追踪 | 自动计算 token 使用量和成本 |
| **延迟** | ✅ 自动追踪 | 自动追踪每个 span 的延迟 |
| **TTFT** | ⚠️ 需手动实现 | Python SDK 需使用 `TTFTTracker` |
| **Score/评分** | ⚠️ 需手动上报 | 需调用 `report_score()` 方法 |

## 快速开始

### 1. 创建 Langfuse 账号

1. 访问 [cloud.langfuse.com](https://cloud.langfuse.com/)
2. 注册免费账号
3. 在 Project Settings > API Keys 生成密钥

### 2. 配置环境变量

在 `.env` 文件中添加：

```bash
# Langfuse 配置
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxx
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com  # EU 区域
# LANGFUSE_HOST=https://us.cloud.langfuse.com  # US 区域
```

### 3. 或通过代码配置

```python
from utils.langfuse_config import configure_langfuse

configure_langfuse(
    secret_key="sk-lf-xxxxxxxxxxxx",
    public_key="pk-lf-xxxxxxxxxxxx",
    host="https://cloud.langfuse.com"
)
```

## 使用方法

### 基本追踪

配置完成后，Langfuse 会自动追踪所有 LangGraph 执行：

```python
from utils.langfuse_config import get_langfuse_handler

# 获取 Handler
handler = get_langfuse_handler(
    user_id="user_123",
    session_id="session_456",
    tags=["production", "recommendation"]
)

# 在 LangGraph 中使用
result = await graph.ainvoke(input_state, config={"callbacks": [handler]})
```

### 使用便捷函数

```python
from agents.main_graph import run_main_graph

# 自动包含 Langfuse 追踪
result = await run_main_graph(
    session_id="session_456",
    user_id="user_123",
    messages=[HumanMessage(content="推荐重疾险")],
    environment="production",
    tags=["user-message"]
)
```

### TTFT 追踪

Langfuse Python SDK 不自动追踪 TTFT，需要手动实现：

```python
from utils.langfuse_config import create_ttft_tracker

# 创建 TTFT 追踪器
tracker = create_ttft_tracker(trace_id="trace_123")

# 开始追踪
tracker.start()

# 流式调用 LLM
async for chunk in llm.astream(prompt):
    if not tracker.first_token_received:
        tracker.mark_first_token()
    # 处理 chunk...

# 获取 TTFT
ttft_ms = tracker.get_ttft_ms()
print(f"TTFT: {ttft_ms:.2f}ms")

# 上报到 Langfuse
tracker.report_to_langfuse()
```

### 上报评分

```python
from utils.langfuse_config import report_score, report_user_feedback, report_llm_judge_score

# 上报用户反馈
report_user_feedback(
    trace_id="trace_123",
    rating=0.9,
    comment="用户认为回答很有帮助"
)

# 上报 LLM-as-Judge 评估
report_llm_judge_score(
    trace_id="trace_123",
    metric_name="relevance",
    score=0.85,
    reasoning="回答与用户问题高度相关"
)

# 上报自定义评分
report_score(
    trace_id="trace_123",
    name="intent_accuracy",
    value=0.95,
    comment="意图识别准确率"
)
```

### 敏感数据脱敏

```python
from utils.langfuse_config import anonymize_sensitive_data

text = "我的手机号是13812345678，身份证是110101199001011234"
anonymized = anonymize_sensitive_data(text)
# 输出: "我的手机号是<phone>，身份证是<id_card>"
```

## 查看追踪

1. 访问 [cloud.langfuse.com](https://cloud.langfuse.com/)
2. 导航到项目
3. 点击追踪查看详情

### 追踪视图

- **详情视图**：逐步执行流程
- **消息视图**：用户与 Agent 的对话历史
- **输入/输出**：请求和响应数据
- **元数据**：自定义标签和元数据
- **评分**：用户反馈和评估分数

## Dashboard 指标

Langfuse Dashboard 自动提供：

### Traces Section
- Trace count
- Latency (p50, p95, p99)
- Error rates

### LLM Calls Section
- LLM call count
- Latency
- Token usage
- Cost

### Scores Section
- User feedback scores
- LLM-as-Judge scores
- Custom scores

## 最佳实践

### 1. 使用有意义的标签

```python
handler = get_langfuse_handler(
    tags=["production", "recommendation", "v1.0"]
)
```

### 2. 添加用户上下文

```python
handler = get_langfuse_handler(
    user_id="user_123",
    session_id="session_456"
)
```

### 3. 分离环境

```python
# 开发环境
configure_langfuse(host="https://cloud.langfuse.com")
# 使用 tags 区分环境
handler = get_langfuse_handler(tags=["dev"])

# 生产环境
handler = get_langfuse_handler(tags=["production"])
```

### 4. 及时上报评分

```python
# 在用户交互后立即上报
report_user_feedback(trace_id=trace_id, rating=user_rating)

# 在 LLM-as-Judge 评估后上报
report_llm_judge_score(trace_id=trace_id, metric_name="accuracy", score=score)
```

### 5. 应用退出前刷新

```python
from utils.langfuse_config import flush_langfuse, shutdown_langfuse

# 确保所有事件已发送
flush_langfuse()

# 或完全关闭客户端
shutdown_langfuse()
```

## 自托管 Langfuse

Langfuse 支持自托管，适合对数据主权有严格要求的场景：

### Docker Compose

```yaml
version: '3.8'
services:
  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://...
      - NEXTAUTH_SECRET=...
      - SALT=...
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=...
      - POSTGRES_PASSWORD=...
      - POSTGRES_DB=langfuse
  
  redis:
    image: redis:7
```

### 配置自托管地址

```bash
LANGFUSE_HOST=http://localhost:3000
```

## 费用说明

Langfuse 提供：
- **Cloud Free**: 每月 50,000 events
- **Cloud Pro**: $59/月，500,000 events
- **Self-hosted**: 免费，无限制

开发环境使用 Free 版即可满足需求。

## 故障排除

### 追踪未显示

1. 检查 `LANGFUSE_SECRET_KEY` 和 `LANGFUSE_PUBLIC_KEY` 已设置
2. 验证密钥格式正确（以 `sk-lf-` 和 `pk-lf-` 开头）
3. 检查 `LANGFUSE_HOST` 是否正确

### 追踪缺失

1. 确保调用了 `flush_langfuse()` 或 `shutdown_langfuse()`
2. 检查是否有异常导致事件未发送

### 评分未显示

1. 确保使用正确的 `trace_id`
2. 检查评分值是否在有效范围内

## 相关文档

- [Langfuse 官方文档](https://langfuse.com/docs)
- [LangChain 集成](https://langfuse.com/docs/integrations/langchain)
- [LangGraph 集成](https://langfuse.com/guides/cookbook/integration_langgraph)
- [自托管指南](https://langfuse.com/docs/deployment/self-host)

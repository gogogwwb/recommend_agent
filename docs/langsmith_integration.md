# LangSmith 集成指南

## 概述

LangSmith 是 LangChain 提供的 LLM 应用可观测性和评估平台。本项目集成 LangSmith 用于保险推荐 Agent 的监控、调试和评估。

## 功能特性

### 1. 追踪 (Tracing)
- 自动追踪 LangGraph 执行流程
- 可视化 Agent 执行流程
- 逐步执行详情
- 输入/输出检查

### 2. 调试 (Debugging)
- 实时查看追踪
- 错误追踪和堆栈信息
- 消息历史检查
- 工具调用可视化

### 3. 评估 (Evaluation)
- 创建测试数据集
- 对追踪进行评估
- 比较模型性能
- 追踪指标变化

### 4. 监控 (Monitoring)
- 生产环境追踪收集
- 性能指标
- 成本追踪
- 告警配置

## 快速开始

### 1. 创建 LangSmith 账号

1. 访问 [smith.langchain.com](https://smith.langchain.com/)
2. 注册免费账号
3. 在 Settings > API Keys 生成 API Key

### 2. 配置环境变量

在 `.env` 文件中添加：

```bash
# LangSmith 配置
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxxxxx
LANGSMITH_PROJECT=insurance-recommendation-agent
LANGSMITH_WORKSPACE_ID=  # 可选，多工作空间账号需要
```

### 3. 或通过代码配置

```python
from utils.langsmith_config import configure_langsmith

configure_langsmith(
    tracing=True,
    api_key="lsv2_pt_xxxxxxxxxxxx",
    project="insurance-recommendation-agent"
)
```

## 使用方法

### 基本追踪

配置完成后，LangSmith 会自动追踪所有 LangGraph 执行：

```python
from agents.main_graph import create_main_graph_with_checkpointer

# 创建图
graph = create_main_graph_with_checkpointer()

# 调用 - 自动追踪
result = await graph.ainvoke(input_state)
```

### 带元数据的追踪

为追踪添加自定义元数据和标签：

```python
from utils.langsmith_config import get_trace_config

# 创建追踪配置
config = get_trace_config(
    user_id="user_123",
    session_id="session_456",
    environment="production",
    tags=["recommendation", "insurance"]
)

# 添加 thread_id 用于 checkpointer
config["configurable"] = {"thread_id": "session_456"}

# 使用配置调用
result = await graph.ainvoke(input_state, config=config)
```

### 选择性追踪

追踪特定的调用：

```python
from utils.langsmith_config import trace_context

# 追踪此调用
with trace_context(
    project_name="recommendation-test",
    tags=["production"],
    metadata={"user_id": "user_123"}
):
    result = await graph.ainvoke(input_state)

# 跳过此调用的追踪
with trace_context(enabled=False):
    result = await graph.ainvoke(input_state)
```

### 敏感数据脱敏

防止敏感数据被记录到 LangSmith：

```python
from utils.langsmith_config import get_tracer_with_anonymizer

# 获取带脱敏功能的追踪器
tracer = get_tracer_with_anonymizer()

# 用于图
graph = graph.with_config({'callbacks': [tracer]})
```

脱敏器会自动处理：
- 中国身份证号（18位）
- 中国手机号
- 电子邮箱
- 银行卡号（16位）
- 美国社会安全号码

## 查看追踪

1. 访问 [smith.langchain.com](https://smith.langchain.com/)
2. 导航到项目：`insurance-recommendation-agent`
3. 点击追踪查看详情

### 追踪视图

- **详情视图**：逐步执行流程
- **消息视图**：用户与 Agent 的对话历史
- **输入/输出**：请求和响应数据
- **元数据**：自定义标签和元数据

## 最佳实践

### 1. 使用有意义的标签

```python
config = get_trace_config(
    tags=["production", "recommendation", "v1.0"]
)
```

### 2. 添加用户上下文

```python
config = get_trace_config(
    user_id="user_123",
    session_id="session_456"
)
```

### 3. 分离环境

```python
# 开发环境
configure_langsmith(project="insurance-agent-dev")

# 生产环境
configure_langsmith(project="insurance-agent-prod")
```

### 4. 脱敏敏感数据

生产环境始终使用脱敏功能：

```python
tracer = get_tracer_with_anonymizer()
graph = graph.with_config({'callbacks': [tracer]})
```

## 费用说明

LangSmith 提供：
- **免费版**：每月 5,000 条追踪
- **Plus 版**：$39/月，50,000 条追踪
- **企业版**：定制价格

开发环境使用免费版即可满足需求。

## 故障排除

### 追踪未显示

1. 检查 `LANGSMITH_TRACING=true`
2. 验证 `LANGSMITH_API_KEY` 已设置
3. 检查项目名称是否匹配

### API Key 错误

1. 从 LangSmith 设置中重新生成 API Key
2. 确保环境变量中没有多余空格

### 追踪缺失

1. 检查是否使用了 `trace_context(enabled=False)`
2. 验证图是否使用 LangChain/LangGraph 组件

## 相关文档

- [LangSmith 官方文档](https://docs.langchain.com/langsmith/)
- [LangGraph 可观测性](https://docs.langchain.com/oss/python/langgraph/observability)
- [LangGraph 追踪](https://docs.langchain.com/langsmith/trace-with-langgraph)

"""
LangSmith 集成示例

本示例演示如何使用 LangSmith 监控和调试保险推荐 Agent。

核心功能：
- 自动追踪 LangGraph 执行
- 自定义元数据和标签
- 选择性追踪
- 敏感数据脱敏

前置条件：
1. 创建 LangSmith 账号: https://smith.langchain.com/
2. 从设置页面生成 API Key
3. 设置环境变量或通过代码配置

使用方法：
    # 设置环境变量
    export LANGSMITH_TRACING=true
    export LANGSMITH_API_KEY=lsv2_pt_...
    export LANGSMITH_PROJECT=insurance-recommendation-agent
    
    # 运行示例
    python examples/langsmith_example.py
"""
import asyncio
import os
from langchain_core.messages import HumanMessage

from utils.langsmith_config import (
    configure_langsmith,
    is_tracing_enabled,
    trace_context,
    get_trace_config,
    get_tracer_with_anonymizer,
)


def example_configure_langsmith():
    """示例：通过代码配置 LangSmith"""
    print("=" * 60)
    print("示例 1：配置 LangSmith")
    print("=" * 60)
    
    # 方式 1：通过环境变量配置
    # export LANGSMITH_TRACING=true
    # export LANGSMITH_API_KEY=lsv2_pt_...
    # export LANGSMITH_PROJECT=insurance-recommendation-agent
    
    # 方式 2：通过代码配置
    configure_langsmith(
        tracing=True,
        api_key=os.environ.get("LANGSMITH_API_KEY"),
        project="insurance-recommendation-agent"
    )
    
    # 检查追踪是否启用
    if is_tracing_enabled():
        print("✓ LangSmith 追踪已启用")
        print(f"  项目: {os.environ.get('LANGSMITH_PROJECT', 'default')}")
    else:
        print("✗ LangSmith 追踪未启用")
        print("  请设置 LANGSMITH_TRACING=true 和 LANGSMITH_API_KEY")


async def example_trace_with_metadata():
    """示例：带元数据和标签的追踪"""
    print("\n" + "=" * 60)
    print("示例 2：带元数据的追踪")
    print("=" * 60)
    
    if not is_tracing_enabled():
        print("跳过：LangSmith 追踪未启用")
        return
    
    # 创建带元数据的追踪配置
    config = get_trace_config(
        user_id="user_123",
        session_id="session_456",
        environment="development",
        tags=["recommendation", "insurance", "test"]
    )
    
    print("追踪配置已创建:")
    print(f"  标签: {config.get('tags')}")
    print(f"  元数据: {config.get('metadata')}")
    
    # 用于 Agent 调用
    # result = await agent.ainvoke(input_state, config=config)
    print("\n使用方法:")
    print("  result = await agent.ainvoke(input_state, config=config)")


async def example_selective_tracing():
    """示例：选择性追踪"""
    print("\n" + "=" * 60)
    print("示例 3：选择性追踪")
    print("=" * 60)
    
    if not is_tracing_enabled():
        print("跳过：LangSmith 追踪未启用")
        return
    
    # 追踪特定调用
    print("追踪特定调用:")
    
    with trace_context(
        project_name="recommendation-test",
        tags=["production", "recommendation"],
        metadata={"user_id": "user_123", "test": True}
    ):
        print("  ✓ 此调用会被追踪")
        # result = await agent.ainvoke(input_state)
    
    # 跳过特定调用的追踪
    with trace_context(enabled=False):
        print("  ✗ 此调用不会被追踪")
        # result = await agent.ainvoke(input_state)


def example_anonymize_sensitive_data():
    """示例：敏感数据脱敏"""
    print("\n" + "=" * 60)
    print("示例 4：敏感数据脱敏")
    print("=" * 60)
    
    if not is_tracing_enabled():
        print("跳过：LangSmith 追踪未启用")
        return
    
    # 获取带脱敏功能的追踪器
    tracer = get_tracer_with_anonymizer()
    
    if tracer:
        print("✓ 已创建带脱敏功能的追踪器")
        print("  以下模式会被自动脱敏:")
        print("  - 中国身份证号（18位）")
        print("  - 中国手机号")
        print("  - 电子邮箱")
        print("  - 银行卡号（16位）")
        
        # 用于图
        # graph = graph.with_config({'callbacks': [tracer]})
        print("\n使用方法:")
        print("  graph = graph.with_config({'callbacks': [tracer]})")
    else:
        print("✗ 无法创建带脱敏功能的追踪器")


async def example_full_integration():
    """示例：与 Main Graph 完整集成"""
    print("\n" + "=" * 60)
    print("示例 5：与 Main Graph 完整集成")
    print("=" * 60)
    
    if not is_tracing_enabled():
        print("跳过：LangSmith 追踪未启用")
        return
    
    print("""
完整集成示例：

```python
import asyncio
from langchain_core.messages import HumanMessage
from agents.main_graph import create_main_graph_with_checkpointer
from utils.langsmith_config import (
    configure_langsmith,
    get_trace_config,
    trace_context,
)

# 1. 启动时配置 LangSmith
configure_langsmith(
    tracing=True,
    project="insurance-recommendation-agent"
)

# 2. 创建带 checkpointer 的图
graph = create_main_graph_with_checkpointer()

# 3. 创建带元数据的追踪配置
config = get_trace_config(
    user_id="user_123",
    session_id="session_456",
    environment="production",
    tags=["recommendation", "insurance"]
)

# 添加 thread_id 用于 checkpointer
config["configurable"] = {"thread_id": "session_456"}

# 4. 带追踪的调用
async def run_agent():
    # 方式 A：使用配置追踪
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="我想了解重疾险")]},
        config=config
    )
    
    # 方式 B：使用 tracing_context 选择性追踪
    with trace_context(
        project_name="recommendation-prod",
        tags=["production"],
        metadata={"user_id": "user_123"}
    ):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="推荐一些保险产品")]},
            config=config
        )
    
    return result

# 5. 在 LangSmith UI 查看追踪
# https://smith.langchain.com/o/<org>/projects/p/<project>
```
""")


def example_langsmith_features():
    """示例：LangSmith 功能概览"""
    print("\n" + "=" * 60)
    print("示例 6：LangSmith 功能概览")
    print("=" * 60)
    
    print("""
LangSmith 提供以下监控和调试功能：

1. 追踪 (Tracing)
   - 自动追踪 LangGraph 执行流程
   - 可视化 Agent 执行流程
   - 逐步执行详情
   - 输入/输出检查

2. 调试 (Debugging)
   - 实时查看追踪
   - 错误追踪和堆栈信息
   - 消息历史检查
   - 工具调用可视化

3. 评估 (Evaluation)
   - 创建测试数据集
   - 对追踪进行评估
   - 比较模型性能
   - 追踪指标变化

4. 监控 (Monitoring)
   - 生产环境追踪收集
   - 性能指标
   - 成本追踪
   - 告警配置

5. 协作 (Collaboration)
   - 与团队分享追踪
   - 注释和评论
   - 创建反馈数据集
   - 版本控制提示词

查看追踪: https://smith.langchain.com/
""")


async def main():
    """运行所有示例"""
    example_configure_langsmith()
    await example_trace_with_metadata()
    await example_selective_tracing()
    example_anonymize_sensitive_data()
    await example_full_integration()
    example_langsmith_features()
    
    print("\n" + "=" * 60)
    print("所有示例已完成！")
    print("=" * 60)
    
    if is_tracing_enabled():
        print(f"\n查看追踪:")
        print(f"  https://smith.langchain.com/o/default/projects/p/{os.environ.get('LANGSMITH_PROJECT', 'default')}")


if __name__ == "__main__":
    asyncio.run(main())

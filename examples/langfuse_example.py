"""
Langfuse 集成示例

本示例展示如何使用 Langfuse 进行 LLM 可观测性监控：
1. 基本追踪配置
2. TTFT (Time-to-First-Token) 追踪
3. 评分上报
4. 敏感数据脱敏

运行前请确保设置环境变量：
    export LANGFUSE_SECRET_KEY=sk-lf-...
    export LANGFUSE_PUBLIC_KEY=pk-lf-...
    export LANGFUSE_HOST=https://cloud.langfuse.com
"""
import asyncio
import os
import logging
from typing import List

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_basic_tracing():
    """
    示例 1: 基本追踪配置
    
    展示如何配置 Langfuse 并创建追踪 Handler
    """
    from utils.langfuse_config import (
        configure_langfuse,
        get_langfuse_handler,
        is_langfuse_enabled,
    )
    
    print("\n" + "=" * 60)
    print("示例 1: 基本追踪配置")
    print("=" * 60)
    
    # 配置 Langfuse
    configure_langfuse(
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    
    # 检查是否启用
    if is_langfuse_enabled():
        print("✅ Langfuse 已启用")
    else:
        print("❌ Langfuse 未启用，请检查环境变量")
        return
    
    # 创建 Handler
    handler = get_langfuse_handler(
        user_id="user_example_123",
        session_id="session_example_456",
        tags=["example", "basic-tracing"],
        trace_name="basic-tracing-example",
    )
    
    if handler:
        print(f"✅ 创建 Langfuse Handler 成功")
        print(f"   - User ID: user_example_123")
        print(f"   - Session ID: session_example_456")
        print(f"   - Tags: ['example', 'basic-tracing']")
    else:
        print("❌ 创建 Handler 失败")


def example_ttft_tracking():
    """
    示例 2: TTFT 追踪
    
    展示如何手动追踪 Time-to-First-Token
    """
    from utils.langfuse_config import create_ttft_tracker
    
    print("\n" + "=" * 60)
    print("示例 2: TTFT (Time-to-First-Token) 追踪")
    print("=" * 60)
    
    # 创建 TTFT 追踪器
    tracker = create_ttft_tracker(trace_id="trace_ttft_example")
    
    # 模拟 LLM 流式调用
    print("\n模拟 LLM 流式调用...")
    
    tracker.start()
    print(f"   开始时间: {tracker.start_time:.4f}")
    
    # 模拟延迟
    import time
    time.sleep(0.15)  # 模拟 150ms 延迟
    
    # 标记第一个 token
    tracker.mark_first_token()
    
    # 获取 TTFT
    ttft_ms = tracker.get_ttft_ms()
    
    print(f"   第一个 token 时间: {tracker.first_token_time:.4f}")
    print(f"   ✅ TTFT: {ttft_ms:.2f}ms")
    
    # 注意: 实际使用时需要调用 tracker.report_to_langfuse()
    # 这里仅演示 TTFT 计算
    print(f"\n   提示: 实际使用时调用 tracker.report_to_langfuse() 上报到 Langfuse")


def example_score_reporting():
    """
    示例 3: 评分上报
    
    展示如何上报用户反馈和 LLM-as-Judge 评分
    """
    from utils.langfuse_config import (
        report_score,
        report_user_feedback,
        report_llm_judge_score,
    )
    
    print("\n" + "=" * 60)
    print("示例 3: 评分上报")
    print("=" * 60)
    
    # 模拟 trace_id
    trace_id = "trace_score_example"
    
    print("\n上报用户反馈...")
    # 上报用户反馈
    success = report_user_feedback(
        trace_id=trace_id,
        rating=0.9,
        comment="用户认为回答很有帮助",
    )
    if success:
        print("   ✅ 用户反馈上报成功: rating=0.9")
    else:
        print("   ❌ 用户反馈上报失败（Langfuse 未启用）")
    
    print("\n上报 LLM-as-Judge 评估...")
    # 上报 LLM-as-Judge 评估
    success = report_llm_judge_score(
        trace_id=trace_id,
        metric_name="relevance",
        score=0.85,
        reasoning="回答与用户问题高度相关，提供了具体的保险产品建议",
    )
    if success:
        print("   ✅ LLM-as-Judge 评估上报成功: relevance=0.85")
    else:
        print("   ❌ LLM-as-Judge 评估上报失败（Langfuse 未启用）")
    
    print("\n上报自定义评分...")
    # 上报自定义评分
    success = report_score(
        trace_id=trace_id,
        name="intent_accuracy",
        value=0.95,
        comment="意图识别准确率",
    )
    if success:
        print("   ✅ 自定义评分上报成功: intent_accuracy=0.95")
    else:
        print("   ❌ 自定义评分上报失败（Langfuse 未启用）")


def example_sensitive_data_anonymization():
    """
    示例 4: 敏感数据脱敏
    
    展示如何脱敏敏感数据
    """
    from utils.langfuse_config import anonymize_sensitive_data
    
    print("\n" + "=" * 60)
    print("示例 4: 敏感数据脱敏")
    print("=" * 60)
    
    # 测试数据
    test_cases = [
        "我的手机号是13812345678",
        "身份证号码是110101199001011234",
        "邮箱是test@example.com",
        "银行卡号是6222021234567890",
        "SSN是123-45-6789",
        "综合信息：手机13812345678，邮箱test@example.com，身份证110101199001011234",
    ]
    
    print("\n脱敏测试:")
    for text in test_cases:
        anonymized = anonymize_sensitive_data(text)
        print(f"   原文: {text}")
        print(f"   脱敏: {anonymized}")
        print()


async def example_langgraph_tracing():
    """
    示例 5: LangGraph 追踪
    
    展示如何在 LangGraph 中使用 Langfuse
    """
    from utils.langfuse_config import (
        configure_langfuse,
        get_langfuse_handler,
        flush_langfuse,
    )
    
    print("\n" + "=" * 60)
    print("示例 5: LangGraph 追踪")
    print("=" * 60)
    
    # 配置 Langfuse
    configure_langfuse()
    
    # 创建 Handler
    handler = get_langfuse_handler(
        user_id="user_langgraph_example",
        session_id="session_langgraph_example",
        tags=["example", "langgraph"],
        trace_name="langgraph-example",
    )
    
    if not handler:
        print("❌ Langfuse 未配置，跳过 LangGraph 追踪示例")
        return
    
    print("\n在 LangGraph 中使用 Langfuse:")
    print("""
    from langgraph.graph import StateGraph, START, END
    
    # 创建图
    builder = StateGraph(State)
    builder.add_node("node1", node1_func)
    builder.add_edge(START, "node1")
    builder.add_edge("node1", END)
    graph = builder.compile()
    
    # 使用 Langfuse Handler
    handler = get_langfuse_handler(
        user_id="user_123",
        session_id="session_456",
        tags=["production"]
    )
    
    # 调用图
    result = await graph.ainvoke(
        input_state,
        config={"callbacks": [handler]}
    )
    
    # 刷新确保数据发送
    flush_langfuse()
    """)
    
    print("✅ LangGraph 追踪配置完成")


def example_trace_config():
    """
    示例 6: 追踪配置
    
    展示如何创建完整的追踪配置
    """
    from utils.langfuse_config import get_trace_config
    
    print("\n" + "=" * 60)
    print("示例 6: 追踪配置")
    print("=" * 60)
    
    # 创建追踪配置
    config = get_trace_config(
        user_id="user_config_example",
        session_id="session_config_example",
        environment="production",
        tags=["recommendation", "insurance"],
        trace_name="recommendation-agent",
    )
    
    print("\n追踪配置:")
    print(f"   Tags: {config.get('tags', [])}")
    print(f"   Metadata: {config.get('metadata', {})}")
    
    if "callbacks" in config:
        print(f"   Callbacks: {len(config['callbacks'])} handler(s)")
        print("   ✅ 追踪配置创建成功")
    else:
        print("   ❌ 未创建 Callbacks（Langfuse 未启用）")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Langfuse 集成示例")
    print("=" * 60)
    
    # 检查环境变量
    if not os.environ.get("LANGFUSE_SECRET_KEY"):
        print("\n⚠️  警告: LANGFUSE_SECRET_KEY 未设置")
        print("   请设置环境变量后运行:")
        print("   export LANGFUSE_SECRET_KEY=sk-lf-...")
        print("   export LANGFUSE_PUBLIC_KEY=pk-lf-...")
        print("   export LANGFUSE_HOST=https://cloud.langfuse.com")
        print("\n   部分示例将在无追踪模式下运行...")
    
    # 运行示例
    example_basic_tracing()
    example_ttft_tracking()
    example_score_reporting()
    example_sensitive_data_anonymization()
    example_trace_config()
    
    # 异步示例
    asyncio.run(example_langgraph_tracing())
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)
    print("\n下一步:")
    print("1. 访问 https://cloud.langfuse.com/ 查看追踪")
    print("2. 在 Dashboard 中查看指标")
    print("3. 配置告警规则")


if __name__ == "__main__":
    main()

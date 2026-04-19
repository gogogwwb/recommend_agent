"""
Context Isolation Example - Multi-Agent Context Filtering

This example demonstrates how to use context filtering in a multi-agent architecture
to ensure each agent only sees relevant conversation history.
"""

import asyncio
from datetime import datetime
from models.conversation import Message, MessageRole, IntentType


async def main():
    """Demonstrate context isolation for multi-agent architecture"""
    
    # Simulate conversation history
    messages = [
        # Turn 1: Chitchat (should be filtered out for Recommendation Agent)
        Message(
            role=MessageRole.USER,
            content="今天天气真好啊",
            timestamp=datetime.now(),
            intent=IntentType.CHITCHAT
        ),
        Message(
            role=MessageRole.ASSISTANT,
            content="是的，今天阳光明媚。不过我们还是回到保险话题吧，您的年龄是？",
            timestamp=datetime.now(),
            agent_name="ProfileCollectionAgent"
        ),
        
        # Turn 2: Profile collection (should be visible to Recommendation Agent)
        Message(
            role=MessageRole.USER,
            content="我30岁",
            timestamp=datetime.now(),
            intent=IntentType.PROVIDE_INFO,
            extracted_slots={"age": 30}
        ),
        Message(
            role=MessageRole.ASSISTANT,
            content="好的，您的职业是什么？",
            timestamp=datetime.now(),
            agent_name="ProfileCollectionAgent"
        ),
        
        # Turn 3: Profile collection (should be visible to Recommendation Agent)
        Message(
            role=MessageRole.USER,
            content="软件工程师",
            timestamp=datetime.now(),
            intent=IntentType.PROVIDE_INFO,
            extracted_slots={"occupation": "软件工程师"}
        ),
        Message(
            role=MessageRole.ASSISTANT,
            content="明白了，您的年收入大概是多少？",
            timestamp=datetime.now(),
            agent_name="ProfileCollectionAgent"
        ),
        
        # Turn 4: Profile collection (should be visible to Recommendation Agent)
        Message(
            role=MessageRole.USER,
            content="30万",
            timestamp=datetime.now(),
            intent=IntentType.PROVIDE_INFO,
            extracted_slots={"annual_income": 300000}
        ),
        Message(
            role=MessageRole.ASSISTANT,
            content="收集完成，现在为您推荐产品...",
            timestamp=datetime.now(),
            agent_name="ProfileCollectionAgent"
        ),
    ]
    
    print("=" * 80)
    print("Context Isolation Example")
    print("=" * 80)
    
    # Test 1: No filtering (all messages)
    print("\n1. No Filtering (all messages):")
    print("-" * 80)
    print_messages(messages)
    print(f"\nTotal messages: {len(messages)}")
    print(f"Estimated tokens: {estimate_tokens(messages)}")
    
    # Test 2: Filter for RecommendationAgent
    print("\n2. Filtered for RecommendationAgent:")
    print("-" * 80)
    from memory.context_filter import AgentContextScope
    
    filtered_messages = AgentContextScope.filter_messages(
        messages,
        target_agent="RecommendationAgent"
    )
    print_messages(filtered_messages)
    print(f"\nTotal messages: {len(filtered_messages)}")
    print(f"Estimated tokens: {estimate_tokens(filtered_messages)}")
    print(f"Reduction: {100 * (len(messages) - len(filtered_messages)) / len(messages):.1f}%")
    
    # Test 3: Filter for ProfileCollectionAgent
    print("\n3. Filtered for ProfileCollectionAgent:")
    print("-" * 80)
    filtered_messages = AgentContextScope.filter_messages(
        messages,
        target_agent="ProfileCollectionAgent"
    )
    print_messages(filtered_messages)
    print(f"\nTotal messages: {len(filtered_messages)}")
    print(f"Estimated tokens: {estimate_tokens(filtered_messages)}")
    
    # Test 4: Show visibility rules
    print("\n4. Visibility Rules:")
    print("-" * 80)
    for agent_name in ["ProfileCollectionAgent", "RecommendationAgent", "ComplianceAgent"]:
        visible_agents = AgentContextScope.get_visible_agents(agent_name)
        visible_intents = AgentContextScope.get_visible_intents(agent_name)
        excluded_intents = AgentContextScope.get_excluded_intents(agent_name)
        
        print(f"\n{agent_name}:")
        print(f"  Visible Agents: {', '.join(visible_agents)}")
        print(f"  Visible Intents: {', '.join([i.value for i in visible_intents])}")
        print(f"  Excluded Intents: {', '.join([i.value for i in excluded_intents])}")


def print_messages(messages):
    """Print messages in a readable format"""
    for msg in messages:
        role_label = "用户" if msg.role == MessageRole.USER else "助手"
        timestamp = msg.timestamp.strftime("%H:%M:%S")
        
        # Add intent/agent info
        extra_info = ""
        if msg.role == MessageRole.USER and msg.intent:
            extra_info = f" [意图: {msg.intent.value}]"
        elif msg.role == MessageRole.ASSISTANT and msg.agent_name:
            extra_info = f" [Agent: {msg.agent_name}]"
        
        print(f"[{timestamp}] {role_label}{extra_info}: {msg.content}")


def estimate_tokens(messages):
    """Estimate token count (rough approximation)"""
    total_chars = sum(len(msg.content) for msg in messages)
    return total_chars // 4  # Rough estimate: 1 token ≈ 4 characters


if __name__ == "__main__":
    asyncio.run(main())

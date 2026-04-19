"""
Example usage of HotDataLayer

This example demonstrates how to use the HotDataLayer for managing
recent conversation data in Redis.
"""

import asyncio
from datetime import datetime

from memory.hot_data_layer import HotDataLayer
from models.conversation import Message, MessageRole
from utils.redis_client import get_redis_client


async def main():
    """Demonstrate HotDataLayer usage"""
    
    # Initialize Redis client
    redis_client = get_redis_client()
    
    # Check Redis health
    health = redis_client.health_check()
    if not health["healthy"]:
        print(f"Redis is not healthy: {health['error']}")
        return
    
    print("✓ Redis connection healthy")
    print(f"  Redis version: {health['info']['redis_version']}")
    print(f"  Connected clients: {health['info']['connected_clients']}")
    print()
    
    # Create HotDataLayer for a session
    session_id = "demo-session-001"
    hot_layer = HotDataLayer(
        redis_client=redis_client,
        session_id=session_id,
        max_hot_turns=5,
        ttl_seconds=3600
    )
    
    print(f"Created HotDataLayer for session: {session_id}")
    print()
    
    # Example 1: Add messages to hot layer
    print("=" * 60)
    print("Example 1: Adding messages to hot layer")
    print("=" * 60)
    
    messages = [
        Message(role=MessageRole.USER, content="你好，我想了解保险产品", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="您好！我可以帮您推荐合适的保险产品。请问您今年多大年龄？", timestamp=datetime.now()),
        Message(role=MessageRole.USER, content="我今年30岁", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="好的，30岁正是购买保险的好时机。请问您的职业是什么？", timestamp=datetime.now()),
        Message(role=MessageRole.USER, content="我是软件工程师", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="了解了。软件工程师属于低风险职业。请问您目前的婚姻状况？", timestamp=datetime.now()),
    ]
    
    for i, msg in enumerate(messages, 1):
        await hot_layer.add_message(msg)
        print(f"  Added message {i}: {msg.role.value} - {msg.content[:30]}...")
    
    print()
    
    # Example 2: Retrieve messages
    print("=" * 60)
    print("Example 2: Retrieving messages from hot layer")
    print("=" * 60)
    
    retrieved_messages = await hot_layer.get_hot_messages()
    print(f"Retrieved {len(retrieved_messages)} messages:")
    for i, msg in enumerate(retrieved_messages, 1):
        print(f"  {i}. [{msg.role.value}] {msg.content}")
    
    print()
    
    # Example 3: Update slots
    print("=" * 60)
    print("Example 3: Updating user profile slots")
    print("=" * 60)
    
    slots = {
        "age": 30,
        "occupation": "software_engineer",
        "marital_status": "single"
    }
    
    await hot_layer.update_slots(slots)
    print(f"Updated slots: {slots}")
    
    # Retrieve slots
    retrieved_slots = await hot_layer.get_slots()
    print(f"Retrieved slots: {retrieved_slots}")
    print()
    
    # Example 4: Get complete hot context
    print("=" * 60)
    print("Example 4: Getting complete hot context")
    print("=" * 60)
    
    context = await hot_layer.get_hot_context()
    print(f"Hot context contains:")
    print(f"  - Messages: {len(context['hot_messages'])}")
    print(f"  - Slots: {len(context['slots'])}")
    print(f"  - Metadata: {context['metadata']}")
    print(f"  - Session ID: {context['session_id']}")
    print()
    
    # Example 5: Check statistics
    print("=" * 60)
    print("Example 5: Hot layer statistics")
    print("=" * 60)
    
    message_count = await hot_layer.get_message_count()
    turn_count = await hot_layer.get_turn_count()
    is_empty = await hot_layer.is_empty()
    
    print(f"  Message count: {message_count}")
    print(f"  Turn count: {turn_count}")
    print(f"  Is empty: {is_empty}")
    print()
    
    # Example 6: Test automatic demotion (add more messages)
    print("=" * 60)
    print("Example 6: Testing automatic demotion")
    print("=" * 60)
    
    print("Adding 6 more messages (total will exceed 5 turns)...")
    
    additional_messages = [
        Message(role=MessageRole.USER, content="我已婚，有一个孩子", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="好的，有家庭责任的话，建议考虑寿险和重疾险。", timestamp=datetime.now()),
        Message(role=MessageRole.USER, content="我的年收入大约30万", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="根据您的收入水平，建议保额在150-300万之间。", timestamp=datetime.now()),
        Message(role=MessageRole.USER, content="好的，请给我推荐一些产品", timestamp=datetime.now()),
        Message(role=MessageRole.ASSISTANT, content="我为您推荐以下产品...", timestamp=datetime.now()),
    ]
    
    for msg in additional_messages:
        await hot_layer.add_message(msg)
    
    final_count = await hot_layer.get_message_count()
    print(f"Final message count in hot layer: {final_count}")
    print(f"(Should be capped at {hot_layer.max_hot_turns * 2} messages)")
    print()
    
    # Example 7: Refresh TTL
    print("=" * 60)
    print("Example 7: Refreshing TTL")
    print("=" * 60)
    
    await hot_layer.refresh_ttl()
    print(f"✓ TTL refreshed to {hot_layer.ttl_seconds} seconds")
    print()
    
    # Example 8: Clear hot data
    print("=" * 60)
    print("Example 8: Clearing hot data")
    print("=" * 60)
    
    await hot_layer.clear()
    print("✓ Hot data cleared")
    
    # Verify it's empty
    is_empty_after_clear = await hot_layer.is_empty()
    print(f"Is empty after clear: {is_empty_after_clear}")
    print()
    
    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

"""
Warm Data Layer Usage Example

This example demonstrates how to use the Warm Data Layer for
conversation history management with intelligent compression.
"""

import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from memory.warm_data_layer import WarmDataLayer, ConversationCompressor
from models.conversation import Message, MessageRole
from models.db_models import Base


async def main():
    """Main example function"""
    
    # ==================== Setup ====================
    
    print("=" * 60)
    print("Warm Data Layer Example")
    print("=" * 60)
    
    # Create async database engine (in-memory for demo)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session maker
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # ==================== Example 1: Basic Usage ====================
    
    print("\n[Example 1] Basic Message Appending")
    print("-" * 60)
    
    async with async_session_maker() as session:
        # Create warm data layer
        warm_layer = WarmDataLayer(
            db_session=session,
            session_id="demo-session-001",
            compression_token_threshold=3000,
            enable_async_compression=True
        )
        
        # Create sample messages
        messages = [
            Message(
                role=MessageRole.USER,
                content="我今年30岁，想了解重疾险",
                timestamp=datetime.now(),
                extracted_slots={"age": 30, "interested_product_type": "critical_illness"}
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="好的，我了解到您30岁，对重疾险感兴趣。请问您的职业是什么？",
                timestamp=datetime.now(),
                agent_name="ProfileCollectionAgent"
            ),
            Message(
                role=MessageRole.USER,
                content="我是软件工程师，年收入大约30万",
                timestamp=datetime.now(),
                extracted_slots={"occupation": "软件工程师", "annual_income": 300000}
            ),
        ]
        
        # Append messages
        for i, message in enumerate(messages, 1):
            await warm_layer.append_message(message)
            print(f"✓ Appended message {i}: {message.role.value}")
        
        # Get warm context
        warm_context = await warm_layer.get_warm_context()
        print(f"\n📊 Warm Context Stats:")
        print(f"   - Messages: {len(warm_context['warm_messages'])}")
        print(f"   - Token Count: {warm_context['token_count']}")
        print(f"   - Compression Count: {warm_context['compression_count']}")
    
    # ==================== Example 2: Token-Based Compression ====================
    
    print("\n\n[Example 2] Token-Based Compression Trigger")
    print("-" * 60)
    
    async with async_session_maker() as session:
        # Create warm layer with low threshold for demo
        warm_layer = WarmDataLayer(
            db_session=session,
            session_id="demo-session-002",
            compression_token_threshold=200,  # Low threshold for demo
            enable_async_compression=False  # Synchronous for demo
        )
        
        # Add many messages to trigger compression
        long_content = "这是一个关于保险需求的详细描述。" * 20
        
        print("Adding messages to trigger compression...")
        for i in range(5):
            message = Message(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Message {i+1}: {long_content}",
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
            
            # Check if compression triggered
            warm_context = await warm_layer.get_warm_context()
            if warm_context['compression_count'] > 0:
                print(f"✓ Compression triggered after message {i+1}")
                break
        
        # Show compression results
        warm_context = await warm_layer.get_warm_context()
        print(f"\n📊 After Compression:")
        print(f"   - Compression Batches: {warm_context['compression_count']}")
        print(f"   - Compressed History Length: {len(warm_context['compressed_history'])} chars")
        print(f"   - Remaining Warm Messages: {len(warm_context['warm_messages'])}")
        print(f"   - Total Token Count: {warm_context['token_count']}")
    
    # ==================== Example 3: Critical Slot Preservation ====================
    
    print("\n\n[Example 3] Critical Slot Preservation")
    print("-" * 60)
    
    async with async_session_maker() as session:
        warm_layer = WarmDataLayer(
            db_session=session,
            session_id="demo-session-003",
            compression_token_threshold=100,
            enable_async_compression=False
        )
        
        # Add messages with critical slots
        messages_with_slots = [
            Message(
                role=MessageRole.USER,
                content="我30岁，软件工程师，年收入30万" * 10,
                timestamp=datetime.now(),
                extracted_slots={
                    "age": 30,
                    "occupation": "软件工程师",
                    "annual_income": 300000,
                    "risk_preference": "balanced"
                }
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="了解您的情况了" * 10,
                timestamp=datetime.now()
            ),
        ]
        
        for message in messages_with_slots:
            await warm_layer.append_message(message)
        
        # Wait a bit for potential async compression
        await asyncio.sleep(0.1)
        
        # Check if compression was triggered
        warm_context = await warm_layer.get_warm_context()
        
        if warm_context['compression_count'] == 0:
            # If not compressed yet (threshold not reached), show uncompressed state
            print("✓ Messages added (not yet compressed)")
            print(f"\n📊 Uncompressed State:")
            print(f"   - Uncompressed messages: {len(warm_context['warm_messages'])}")
            uncompressed_tokens = await warm_layer.get_uncompressed_token_count()
            print(f"   - Uncompressed tokens: {uncompressed_tokens}")
            print(f"   - Threshold: {warm_layer.compression_token_threshold}")
        else:
            # Compression was triggered
            print("✓ Compression triggered automatically")
        
        compressed = warm_context['compressed_history']
        
        print("✓ Compression completed")
        
        if compressed:
            print(f"\n📝 Compressed History Preview:")
            print(compressed[:300] + "..." if len(compressed) > 300 else compressed)
            
            # Verify critical slots preserved
            print(f"\n🔑 Critical Slots Preserved:")
            if "[保留的关键信息]" in compressed:
                print("   ✓ Slot preservation section found")
                if "age" in compressed:
                    print("   ✓ Age preserved")
                if "occupation" in compressed:
                    print("   ✓ Occupation preserved")
                if "annual_income" in compressed:
                    print("   ✓ Annual income preserved")
            else:
                print("   ⚠ Slot preservation section not found")
        else:
            print("\n⚠ No compression occurred (threshold not reached)")
            print(f"   This is normal if messages are short")
            uncompressed_tokens = await warm_layer.get_uncompressed_token_count()
            print(f"   Uncompressed tokens: {uncompressed_tokens}/{warm_layer.compression_token_threshold}")
    
    # ==================== Example 4: Full Context Building ====================
    
    print("\n\n[Example 4] Full Context Building (Warm + Hot)")
    print("-" * 60)
    
    async with async_session_maker() as session:
        warm_layer = WarmDataLayer(
            db_session=session,
            session_id="demo-session-004"
        )
        
        # Add some warm messages
        warm_messages = [
            Message(
                role=MessageRole.USER,
                content="早期对话内容1",
                timestamp=datetime.now()
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="早期回复内容1",
                timestamp=datetime.now()
            ),
        ]
        
        for message in warm_messages:
            await warm_layer.append_message(message)
        
        # Simulate hot messages (from Redis)
        hot_messages = [
            Message(
                role=MessageRole.USER,
                content="最近的用户消息",
                timestamp=datetime.now()
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="最近的助手回复",
                timestamp=datetime.now()
            ),
        ]
        
        # Build full context
        full_context = await warm_layer.get_full_context_for_agent(hot_messages)
        
        print("✓ Full context built successfully")
        print(f"\n📄 Full Context Preview:")
        print(full_context[:400] + "..." if len(full_context) > 400 else full_context)
        
        # Calculate token count
        compressor = ConversationCompressor()
        token_count = compressor.count_tokens(full_context)
        print(f"\n📊 Context Stats:")
        print(f"   - Total Length: {len(full_context)} chars")
        print(f"   - Total Tokens: {token_count}")
    
    # ==================== Example 5: Async Compression ====================
    
    print("\n\n[Example 5] Asynchronous Compression")
    print("-" * 60)
    
    async with async_session_maker() as session:
        warm_layer = WarmDataLayer(
            db_session=session,
            session_id="demo-session-005",
            compression_token_threshold=100,
            enable_async_compression=True  # Async mode
        )
        
        # Add messages that trigger compression
        long_content = "这是一个很长的消息内容。" * 30
        
        print("Adding messages (async compression enabled)...")
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
            print(f"✓ Message {i+1} appended (non-blocking)")
        
        print("\n⏳ Waiting for async compression tasks...")
        await warm_layer.wait_for_pending_compressions()
        print("✓ All compression tasks completed")
        
        # Check results
        warm_context = await warm_layer.get_warm_context()
        print(f"\n📊 Final Stats:")
        print(f"   - Compression Batches: {warm_context['compression_count']}")
        print(f"   - Token Count: {warm_context['token_count']}")
    
    # ==================== Cleanup ====================
    
    await engine.dispose()
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

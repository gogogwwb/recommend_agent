"""
Unit tests for Warm Data Layer

Tests the warm data layer functionality including:
- Message appending
- Token-based compression triggering
- Async compression
- Context retrieval
- Critical slot preservation
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from memory.warm_data_layer import WarmDataLayer, ConversationCompressor
from models.conversation import Message, MessageRole
from models.db_models import Base, ConversationSession as ConversationSessionModel


# ==================== Fixtures ====================

@pytest.fixture
async def async_db_session():
    """Create an in-memory async SQLite database for testing"""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
def sample_messages():
    """Create sample messages for testing"""
    return [
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
        Message(
            role=MessageRole.ASSISTANT,
            content="明白了。作为软件工程师，年收入30万，您的风险承受能力如何？",
            timestamp=datetime.now(),
            agent_name="ProfileCollectionAgent"
        ),
    ]


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing"""
    client = AsyncMock()
    client.generate = AsyncMock(return_value="用户30岁，软件工程师，年收入30万，对重疾险感兴趣。")
    return client


# ==================== ConversationCompressor Tests ====================

class TestConversationCompressor:
    """Test ConversationCompressor functionality"""
    
    def test_count_tokens(self):
        """Test token counting"""
        compressor = ConversationCompressor()
        
        text = "Hello, world!"
        token_count = compressor.count_tokens(text)
        
        assert token_count > 0
        assert isinstance(token_count, int)
    
    def test_count_messages_tokens(self, sample_messages):
        """Test counting tokens in messages"""
        compressor = ConversationCompressor()
        
        token_count = compressor.count_messages_tokens(sample_messages)
        
        assert token_count > 0
        # Should include content + overhead
        assert token_count > len("".join(m.content for m in sample_messages)) // 4
    
    def test_extract_slots_from_messages(self, sample_messages):
        """Test extracting slots from messages"""
        compressor = ConversationCompressor()
        
        slots = compressor.extract_slots_from_messages(sample_messages)
        
        assert "age" in slots
        assert slots["age"] == 30
        assert "occupation" in slots
        assert slots["occupation"] == "软件工程师"
        assert "annual_income" in slots
        assert slots["annual_income"] == 300000
    
    @pytest.mark.asyncio
    async def test_compress_messages_rule_based(self, sample_messages):
        """Test rule-based compression (no LLM)"""
        compressor = ConversationCompressor(llm_client=None)
        
        compressed = await compressor.compress_messages(sample_messages)
        
        assert isinstance(compressed, str)
        assert len(compressed) > 0
        # Should contain critical slots
        assert "age=30" in compressed or "30" in compressed
        assert "occupation" in compressed or "软件工程师" in compressed
    
    @pytest.mark.asyncio
    async def test_compress_messages_with_llm(self, sample_messages, mock_llm_client):
        """Test LLM-based compression"""
        compressor = ConversationCompressor(llm_client=mock_llm_client)
        
        compressed = await compressor.compress_messages(sample_messages)
        
        assert isinstance(compressed, str)
        assert len(compressed) > 0
        # Should call LLM
        mock_llm_client.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_compress_preserves_critical_slots(self, sample_messages):
        """Test that compression preserves critical slots"""
        compressor = ConversationCompressor(llm_client=None)
        
        compressed = await compressor.compress_messages(sample_messages)
        
        # Check that critical slots are preserved in JSON format
        assert "[保留的关键信息]" in compressed
        assert "age" in compressed
        assert "30" in compressed
        assert "annual_income" in compressed
    
    def test_decompress_for_context(self, sample_messages):
        """Test building context from compressed history"""
        compressor = ConversationCompressor()
        
        compressed_history = "用户30岁，软件工程师，对重疾险感兴趣。"
        recent_messages = sample_messages[:2]
        
        context = compressor.decompress_for_context(compressed_history, recent_messages)
        
        assert "[历史对话摘要]" in context
        assert compressed_history in context
        assert "[最近对话]" in context
        assert "30岁" in context or "重疾险" in context


# ==================== WarmDataLayer Tests ====================

class TestWarmDataLayer:
    """Test WarmDataLayer functionality"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, async_db_session):
        """Test warm data layer initialization"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-001"
        )
        
        assert warm_layer.session_id == "test-session-001"
        assert warm_layer.compression_token_threshold == 3000
        assert warm_layer.enable_async_compression is True
    
    @pytest.mark.asyncio
    async def test_append_message(self, async_db_session, sample_messages):
        """Test appending message to warm layer"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-002"
        )
        
        # Append first message
        await warm_layer.append_message(sample_messages[0])
        
        # Verify message was saved
        warm_context = await warm_layer.get_warm_context()
        assert len(warm_context["warm_messages"]) == 1
        assert warm_context["warm_messages"][0].content == sample_messages[0].content
    
    @pytest.mark.asyncio
    async def test_append_multiple_messages(self, async_db_session, sample_messages):
        """Test appending multiple messages"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-003"
        )
        
        # Append all messages
        for message in sample_messages:
            await warm_layer.append_message(message)
        
        # Verify all messages saved
        warm_context = await warm_layer.get_warm_context()
        assert len(warm_context["warm_messages"]) == len(sample_messages)
    
    @pytest.mark.asyncio
    async def test_compression_not_triggered_below_threshold(self, async_db_session):
        """Test that compression is not triggered below token threshold"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-004",
            compression_token_threshold=10000  # High threshold
        )
        
        # Add a few short messages
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=f"Short message {i}",
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Verify no compression occurred
        warm_context = await warm_layer.get_warm_context()
        assert warm_context["compression_count"] == 0
        assert len(warm_context["warm_messages"]) == 3
        assert warm_context["compressed_history"] == ""
    
    @pytest.mark.asyncio
    async def test_compression_triggered_above_threshold(self, async_db_session):
        """Test that compression is triggered when threshold exceeded"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-005",
            compression_token_threshold=50,  # Very low threshold
            enable_async_compression=False  # Synchronous for testing
        )
        
        # Add messages that exceed threshold
        long_content = "这是一个很长的消息内容，用于测试压缩功能。" * 10
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Verify compression occurred
        warm_context = await warm_layer.get_warm_context()
        assert warm_context["compression_count"] > 0
        assert warm_context["compressed_history"] != ""
        # Warm messages should be cleared after compression
        assert len(warm_context["warm_messages"]) == 0
    
    @pytest.mark.asyncio
    async def test_async_compression(self, async_db_session):
        """Test asynchronous compression"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-006",
            compression_token_threshold=50,
            enable_async_compression=True
        )
        
        # Add messages that trigger compression
        long_content = "这是一个很长的消息内容。" * 20
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Wait for async compression to complete
        await warm_layer.wait_for_pending_compressions()
        
        # Verify compression occurred
        warm_context = await warm_layer.get_warm_context()
        assert warm_context["compression_count"] > 0
    
    @pytest.mark.asyncio
    async def test_get_warm_context(self, async_db_session, sample_messages):
        """Test retrieving warm context"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-007"
        )
        
        # Add messages
        for message in sample_messages:
            await warm_layer.append_message(message)
        
        # Get context
        context = await warm_layer.get_warm_context()
        
        assert "compressed_history" in context
        assert "warm_messages" in context
        assert "compression_count" in context
        assert "token_count" in context
        assert context["session_id"] == "test-session-007"
    
    @pytest.mark.asyncio
    async def test_get_full_context_for_agent(self, async_db_session, sample_messages):
        """Test building full context for agent"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-008"
        )
        
        # Add some messages to warm layer
        for message in sample_messages[:2]:
            await warm_layer.append_message(message)
        
        # Get full context with hot messages
        hot_messages = sample_messages[2:]
        full_context = await warm_layer.get_full_context_for_agent(hot_messages)
        
        assert isinstance(full_context, str)
        assert len(full_context) > 0
        # Should contain both warm and hot messages
        assert "[温数据层对话]" in full_context or "[最近对话]" in full_context
    
    @pytest.mark.asyncio
    async def test_get_uncompressed_token_count(self, async_db_session, sample_messages):
        """Test getting uncompressed token count"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-010",
            compression_token_threshold=100000  # Very high to prevent auto-compression
        )
        
        # Add messages
        for message in sample_messages:
            await warm_layer.append_message(message)
        
        # Get uncompressed token count
        uncompressed_count = await warm_layer.get_uncompressed_token_count()
        
        assert uncompressed_count > 0
        assert isinstance(uncompressed_count, int)
        
        # Total count should include uncompressed
        total_count = await warm_layer.get_token_count()
        assert total_count >= uncompressed_count
    
    @pytest.mark.asyncio
    async def test_multiple_compression_batches(self, async_db_session):
        """Test multiple compression batches"""
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-011",
            compression_token_threshold=50,
            enable_async_compression=False
        )
        
        # Add messages in batches
        long_content = "这是一个很长的消息内容。" * 20
        
        # First batch
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Second batch
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Verify multiple compressions
        warm_context = await warm_layer.get_warm_context()
        assert warm_context["compression_count"] >= 2
        assert "[压缩批次" in warm_context["compressed_history"]
    
    @pytest.mark.asyncio
    async def test_no_repeated_compression_after_threshold(self, async_db_session):
        """
        Test that compression doesn't trigger repeatedly after threshold is reached
        
        This is a critical test to ensure we only count uncompressed messages,
        not total history tokens.
        """
        warm_layer = WarmDataLayer(
            db_session=async_db_session,
            session_id="test-session-012",
            compression_token_threshold=100,
            enable_async_compression=False
        )
        
        # Add messages to trigger first compression
        long_content = "这是一个很长的消息内容。" * 20
        
        # First batch - should trigger compression
        for i in range(3):
            message = Message(
                role=MessageRole.USER,
                content=long_content,
                timestamp=datetime.now()
            )
            await warm_layer.append_message(message)
        
        # Check first compression
        warm_context = await warm_layer.get_warm_context()
        first_compression_count = warm_context["compression_count"]
        assert first_compression_count >= 1
        
        # Add ONE more short message
        short_message = Message(
            role=MessageRole.USER,
            content="Short message",
            timestamp=datetime.now()
        )
        await warm_layer.append_message(short_message)
        
        # Verify compression did NOT trigger again
        warm_context = await warm_layer.get_warm_context()
        assert warm_context["compression_count"] == first_compression_count
        
        # Verify the short message is in warm_messages (not compressed)
        assert len(warm_context["warm_messages"]) == 1
        assert warm_context["warm_messages"][0]["content"] == "Short message"


# ==================== Integration Tests ====================

class TestWarmDataLayerIntegration:
    """Integration tests for warm data layer with hot data layer"""
    
    @pytest.mark.asyncio
    async def test_hot_to_warm_demotion(self, async_db_session):
        """Test message demotion from hot to warm layer"""
        # This would require HotDataLayer integration
        # Placeholder for future integration test
        pass
    
    @pytest.mark.asyncio
    async def test_full_memory_hierarchy(self, async_db_session):
        """Test complete memory hierarchy (hot -> warm -> cold)"""
        # This would require full memory system integration
        # Placeholder for future integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

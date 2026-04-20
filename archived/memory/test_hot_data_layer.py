"""
Unit tests for Hot Data Layer

Tests the Redis-based hot data layer implementation including:
- Message storage and retrieval
- Automatic demotion to warm layer
- Slot management
- Context retrieval
- TTL and expiration
- Clear operations
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from memory.hot_data_layer import HotDataLayer
from models.conversation import Message, MessageRole
from utils.redis_client import RedisClient


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client"""
    mock_client = Mock(spec=RedisClient)
    mock_client.client = MagicMock()
    return mock_client


@pytest.fixture
def hot_data_layer(mock_redis_client):
    """Create a HotDataLayer instance with mock Redis client"""
    return HotDataLayer(
        redis_client=mock_redis_client,
        session_id="test-session-001",
        max_hot_turns=5,
        ttl_seconds=3600
    )


@pytest.fixture
def sample_message():
    """Create a sample message"""
    return Message(
        role=MessageRole.USER,
        content="我今年30岁，想了解重疾险",
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_messages():
    """Create a list of sample messages"""
    messages = []
    for i in range(12):  # 6 turns = 12 messages
        role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
        content = f"Message {i}"
        messages.append(Message(role=role, content=content, timestamp=datetime.now()))
    return messages


class TestHotDataLayerInitialization:
    """Test HotDataLayer initialization"""
    
    def test_initialization(self, mock_redis_client):
        """Test basic initialization"""
        hot_layer = HotDataLayer(
            redis_client=mock_redis_client,
            session_id="test-session",
            max_hot_turns=5,
            ttl_seconds=3600
        )
        
        assert hot_layer.session_id == "test-session"
        assert hot_layer.max_hot_turns == 5
        assert hot_layer.ttl_seconds == 3600
        assert hot_layer.key_prefix == "hot:test-session"
    
    def test_default_parameters(self, mock_redis_client):
        """Test default parameters"""
        hot_layer = HotDataLayer(
            redis_client=mock_redis_client,
            session_id="test-session"
        )
        
        assert hot_layer.max_hot_turns == 5
        assert hot_layer.ttl_seconds == 3600


class TestAddMessage:
    """Test add_message functionality"""
    
    @pytest.mark.asyncio
    async def test_add_single_message(self, hot_data_layer, sample_message, mock_redis_client):
        """Test adding a single message"""
        # Setup mock
        mock_redis_client.client.llen.return_value = 1
        mock_redis_client.client.rpush.return_value = 1
        mock_redis_client.client.expire.return_value = True
        mock_redis_client.client.get.return_value = None
        
        # Add message
        await hot_data_layer.add_message(sample_message)
        
        # Verify Redis operations
        mock_redis_client.client.rpush.assert_called_once()
        mock_redis_client.client.expire.assert_called()
        
        # Verify message was serialized
        call_args = mock_redis_client.client.rpush.call_args
        assert call_args[0][0] == hot_data_layer.messages_key
        message_json = call_args[0][1]
        assert "我今年30岁" in message_json
    
    @pytest.mark.asyncio
    async def test_add_message_updates_metadata(self, hot_data_layer, sample_message, mock_redis_client):
        """Test that adding a message updates metadata"""
        # Setup mock
        mock_redis_client.client.llen.return_value = 1
        mock_redis_client.client.rpush.return_value = 1
        mock_redis_client.client.expire.return_value = True
        mock_redis_client.client.get.return_value = None
        mock_redis_client.client.setex.return_value = True
        
        # Add message
        await hot_data_layer.add_message(sample_message)
        
        # Verify metadata was updated
        assert mock_redis_client.client.setex.called
    
    @pytest.mark.asyncio
    async def test_add_message_triggers_demotion(self, hot_data_layer, mock_redis_client):
        """Test that exceeding max turns triggers demotion"""
        # Setup mock - simulate 11 messages (exceeds 10 = 5 turns * 2)
        mock_redis_client.client.llen.return_value = 11
        mock_redis_client.client.rpush.return_value = 11
        mock_redis_client.client.lrange.return_value = [
            Message(role=MessageRole.USER, content="Old message").model_dump_json()
        ]
        mock_redis_client.client.ltrim.return_value = True
        mock_redis_client.client.expire.return_value = True
        mock_redis_client.client.get.return_value = None
        mock_redis_client.client.setex.return_value = True
        
        # Create mock warm layer
        mock_warm_layer = AsyncMock()
        
        # Add message
        message = Message(role=MessageRole.USER, content="New message")
        await hot_data_layer.add_message(message, warm_layer=mock_warm_layer)
        
        # Verify demotion occurred
        mock_redis_client.client.lrange.assert_called_once()
        mock_redis_client.client.ltrim.assert_called_once()
        mock_warm_layer.append_message.assert_called_once()


class TestGetHotMessages:
    """Test get_hot_messages functionality"""
    
    @pytest.mark.asyncio
    async def test_get_empty_messages(self, hot_data_layer, mock_redis_client):
        """Test getting messages when none exist"""
        mock_redis_client.client.lrange.return_value = []
        
        messages = await hot_data_layer.get_hot_messages()
        
        assert messages == []
        mock_redis_client.client.lrange.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_multiple_messages(self, hot_data_layer, mock_redis_client):
        """Test getting multiple messages"""
        # Create sample messages
        sample_messages = [
            Message(role=MessageRole.USER, content="Message 1"),
            Message(role=MessageRole.ASSISTANT, content="Message 2"),
            Message(role=MessageRole.USER, content="Message 3"),
        ]
        
        # Mock Redis response
        mock_redis_client.client.lrange.return_value = [
            msg.model_dump_json() for msg in sample_messages
        ]
        
        # Get messages
        messages = await hot_data_layer.get_hot_messages()
        
        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"
        assert messages[2].content == "Message 3"


class TestUpdateSlots:
    """Test update_slots functionality"""
    
    @pytest.mark.asyncio
    async def test_update_empty_slots(self, hot_data_layer, mock_redis_client):
        """Test updating slots when none exist"""
        mock_redis_client.client.get.return_value = None
        mock_redis_client.client.setex.return_value = True
        
        slots = {"age": 30, "occupation": "engineer"}
        await hot_data_layer.update_slots(slots)
        
        # Verify setex was called with correct data
        mock_redis_client.client.setex.assert_called_once()
        call_args = mock_redis_client.client.setex.call_args
        
        # Verify the slots were saved
        saved_slots = json.loads(call_args[0][2])
        assert saved_slots["age"] == 30
        assert saved_slots["occupation"] == "engineer"
    
    @pytest.mark.asyncio
    async def test_update_existing_slots(self, hot_data_layer, mock_redis_client):
        """Test updating slots when some already exist"""
        # Mock existing slots
        existing_slots = {"age": 25, "city": "Beijing"}
        mock_redis_client.client.get.return_value = json.dumps(existing_slots)
        mock_redis_client.client.setex.return_value = True
        
        # Update with new slots
        new_slots = {"age": 30, "occupation": "engineer"}
        await hot_data_layer.update_slots(new_slots)
        
        # Verify merged slots
        call_args = mock_redis_client.client.setex.call_args
        saved_slots = json.loads(call_args[0][2])
        
        assert saved_slots["age"] == 30  # Updated
        assert saved_slots["city"] == "Beijing"  # Preserved
        assert saved_slots["occupation"] == "engineer"  # Added
    
    @pytest.mark.asyncio
    async def test_update_empty_slots_dict(self, hot_data_layer, mock_redis_client):
        """Test updating with empty slots dictionary"""
        await hot_data_layer.update_slots({})
        
        # Should not call Redis
        mock_redis_client.client.setex.assert_not_called()


class TestGetSlots:
    """Test get_slots functionality"""
    
    @pytest.mark.asyncio
    async def test_get_empty_slots(self, hot_data_layer, mock_redis_client):
        """Test getting slots when none exist"""
        mock_redis_client.client.get.return_value = None
        
        slots = await hot_data_layer.get_slots()
        
        assert slots == {}
    
    @pytest.mark.asyncio
    async def test_get_existing_slots(self, hot_data_layer, mock_redis_client):
        """Test getting existing slots"""
        slots_data = {"age": 30, "occupation": "engineer", "city": "Beijing"}
        mock_redis_client.client.get.return_value = json.dumps(slots_data)
        
        slots = await hot_data_layer.get_slots()
        
        assert slots == slots_data


class TestGetHotContext:
    """Test get_hot_context functionality"""
    
    @pytest.mark.asyncio
    async def test_get_complete_context(self, hot_data_layer, mock_redis_client):
        """Test getting complete hot context"""
        # Mock messages
        sample_messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there"),
        ]
        mock_redis_client.client.lrange.return_value = [
            msg.model_dump_json() for msg in sample_messages
        ]
        
        # Mock slots
        slots_data = {"age": 30, "occupation": "engineer"}
        mock_redis_client.client.get.side_effect = [
            json.dumps(slots_data),  # For get_slots
            json.dumps({"turn_count": 1, "message_count": 2})  # For get_metadata
        ]
        
        # Get context
        context = await hot_data_layer.get_hot_context()
        
        assert "hot_messages" in context
        assert "slots" in context
        assert "metadata" in context
        assert "session_id" in context
        
        assert len(context["hot_messages"]) == 2
        assert context["slots"]["age"] == 30
        assert context["session_id"] == "test-session-001"


class TestClear:
    """Test clear functionality"""
    
    @pytest.mark.asyncio
    async def test_clear_hot_data(self, hot_data_layer, mock_redis_client):
        """Test clearing all hot data"""
        mock_redis_client.client.delete.return_value = 4
        
        await hot_data_layer.clear()
        
        # Verify delete was called with all hot keys
        mock_redis_client.client.delete.assert_called_once()
        call_args = mock_redis_client.client.delete.call_args[0]
        
        # Should delete all hot data keys
        assert len(call_args) == 4


class TestUtilityMethods:
    """Test utility methods"""
    
    @pytest.mark.asyncio
    async def test_get_message_count(self, hot_data_layer, mock_redis_client):
        """Test getting message count"""
        mock_redis_client.client.llen.return_value = 8
        
        count = await hot_data_layer.get_message_count()
        
        assert count == 8
    
    @pytest.mark.asyncio
    async def test_get_turn_count(self, hot_data_layer, mock_redis_client):
        """Test getting turn count"""
        mock_redis_client.client.llen.return_value = 8
        
        turn_count = await hot_data_layer.get_turn_count()
        
        assert turn_count == 4  # 8 messages / 2 = 4 turns
    
    @pytest.mark.asyncio
    async def test_is_empty_true(self, hot_data_layer, mock_redis_client):
        """Test is_empty when no messages"""
        mock_redis_client.client.llen.return_value = 0
        
        is_empty = await hot_data_layer.is_empty()
        
        assert is_empty is True
    
    @pytest.mark.asyncio
    async def test_is_empty_false(self, hot_data_layer, mock_redis_client):
        """Test is_empty when messages exist"""
        mock_redis_client.client.llen.return_value = 5
        
        is_empty = await hot_data_layer.is_empty()
        
        assert is_empty is False
    
    @pytest.mark.asyncio
    async def test_refresh_ttl(self, hot_data_layer, mock_redis_client):
        """Test refreshing TTL"""
        mock_redis_client.client.exists.return_value = True
        mock_redis_client.client.expire.return_value = True
        
        await hot_data_layer.refresh_ttl()
        
        # Should call expire for each hot data key
        assert mock_redis_client.client.expire.call_count >= 1


class TestErrorHandling:
    """Test error handling"""
    
    @pytest.mark.asyncio
    async def test_add_message_redis_error(self, hot_data_layer, sample_message, mock_redis_client):
        """Test handling Redis error when adding message"""
        mock_redis_client.client.rpush.side_effect = Exception("Redis connection error")
        
        with pytest.raises(Exception) as exc_info:
            await hot_data_layer.add_message(sample_message)
        
        assert "Redis connection error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_messages_redis_error(self, hot_data_layer, mock_redis_client):
        """Test handling Redis error when getting messages"""
        mock_redis_client.client.lrange.side_effect = Exception("Redis connection error")
        
        with pytest.raises(Exception) as exc_info:
            await hot_data_layer.get_hot_messages()
        
        assert "Redis connection error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_clear_redis_error(self, hot_data_layer, mock_redis_client):
        """Test handling Redis error when clearing"""
        mock_redis_client.client.delete.side_effect = Exception("Redis connection error")
        
        with pytest.raises(Exception) as exc_info:
            await hot_data_layer.clear()
        
        assert "Redis connection error" in str(exc_info.value)


class TestDemotionLogic:
    """Test message demotion logic"""
    
    @pytest.mark.asyncio
    async def test_no_demotion_under_limit(self, hot_data_layer, mock_redis_client):
        """Test that no demotion occurs when under limit"""
        # Setup - 8 messages (under 10 limit)
        mock_redis_client.client.llen.return_value = 8
        mock_redis_client.client.rpush.return_value = 8
        mock_redis_client.client.expire.return_value = True
        mock_redis_client.client.get.return_value = None
        mock_redis_client.client.setex.return_value = True
        
        mock_warm_layer = AsyncMock()
        
        message = Message(role=MessageRole.USER, content="Test")
        await hot_data_layer.add_message(message, warm_layer=mock_warm_layer)
        
        # Verify no demotion occurred
        mock_redis_client.client.lrange.assert_not_called()
        mock_warm_layer.append_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_demotion_without_warm_layer(self, hot_data_layer, mock_redis_client):
        """Test demotion when no warm layer is provided"""
        # Setup - 11 messages (exceeds limit)
        mock_redis_client.client.llen.return_value = 11
        mock_redis_client.client.rpush.return_value = 11
        mock_redis_client.client.lrange.return_value = [
            Message(role=MessageRole.USER, content="Old").model_dump_json()
        ]
        mock_redis_client.client.ltrim.return_value = True
        mock_redis_client.client.expire.return_value = True
        mock_redis_client.client.get.return_value = None
        mock_redis_client.client.setex.return_value = True
        
        # Add message without warm layer
        message = Message(role=MessageRole.USER, content="New")
        await hot_data_layer.add_message(message, warm_layer=None)
        
        # Verify trim still occurred (messages are lost)
        mock_redis_client.client.ltrim.assert_called_once()

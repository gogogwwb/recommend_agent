"""
Unit tests for Redis client
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from utils.redis_client import RedisClient, RedisKeyNamespace, get_redis_client, close_redis_client
from redis.exceptions import ConnectionError, TimeoutError, RedisError


class TestRedisKeyNamespace:
    """Test Redis key naming conventions"""
    
    def test_hot_messages_key(self):
        """Test hot messages key generation"""
        session_id = "test-session-123"
        expected = "hot:test-session-123:messages"
        assert RedisKeyNamespace.hot_messages(session_id) == expected
    
    def test_hot_slots_key(self):
        """Test hot slots key generation"""
        session_id = "test-session-123"
        expected = "hot:test-session-123:slots"
        assert RedisKeyNamespace.hot_slots(session_id) == expected
    
    def test_hot_context_key(self):
        """Test hot context key generation"""
        session_id = "test-session-123"
        expected = "hot:test-session-123:context"
        assert RedisKeyNamespace.hot_context(session_id) == expected
    
    def test_hot_metadata_key(self):
        """Test hot metadata key generation"""
        session_id = "test-session-123"
        expected = "hot:test-session-123:metadata"
        assert RedisKeyNamespace.hot_metadata(session_id) == expected
    
    def test_cache_recommendation_key(self):
        """Test cache recommendation key generation"""
        profile_hash = "abc123"
        expected = "cache:recommendation:abc123"
        assert RedisKeyNamespace.cache_recommendation(profile_hash) == expected
    
    def test_cache_product_vector_key(self):
        """Test cache product vector key generation"""
        product_id = "prod-001"
        expected = "cache:product:prod-001:vector"
        assert RedisKeyNamespace.cache_product_vector(product_id) == expected
    
    def test_session_lock_key(self):
        """Test session lock key generation"""
        session_id = "test-session-123"
        expected = "lock:session:test-session-123"
        assert RedisKeyNamespace.session_lock(session_id) == expected
    
    def test_get_all_hot_keys(self):
        """Test getting all hot keys for a session"""
        session_id = "test-session-123"
        keys = RedisKeyNamespace.get_all_hot_keys(session_id)
        
        assert len(keys) == 4
        assert "hot:test-session-123:messages" in keys
        assert "hot:test-session-123:slots" in keys
        assert "hot:test-session-123:context" in keys
        assert "hot:test-session-123:metadata" in keys


class TestRedisClient:
    """Test Redis client functionality"""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        with patch('utils.redis_client.redis.Redis') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance
    
    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool"""
        with patch('utils.redis_client.ConnectionPool') as mock:
            yield mock
    
    def test_initialization(self, mock_pool, mock_redis):
        """Test Redis client initialization"""
        client = RedisClient()
        
        # Verify connection pool was created
        mock_pool.assert_called_once()
        
        # Verify pool configuration
        call_kwargs = mock_pool.call_args[1]
        assert call_kwargs['max_connections'] == 50
        assert call_kwargs['socket_timeout'] == 5
        assert call_kwargs['decode_responses'] is True
        assert call_kwargs['health_check_interval'] == 30
    
    def test_health_check_success(self, mock_pool, mock_redis):
        """Test successful health check"""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            'redis_version': '7.0.0',
            'connected_clients': 5,
            'used_memory_human': '1M',
            'uptime_in_seconds': 3600
        }
        mock_redis.get.return_value = "ok"
        
        client = RedisClient()
        health = client.health_check()
        
        assert health['healthy'] is True
        assert health['ping_response'] is True
        assert health['error'] is None
        assert health['info']['redis_version'] == '7.0.0'
    
    def test_health_check_connection_error(self, mock_pool, mock_redis):
        """Test health check with connection error"""
        mock_redis.ping.side_effect = ConnectionError("Connection refused")
        
        client = RedisClient()
        health = client.health_check()
        
        assert health['healthy'] is False
        assert 'Connection error' in health['error']
    
    def test_health_check_timeout(self, mock_pool, mock_redis):
        """Test health check with timeout"""
        mock_redis.ping.side_effect = TimeoutError("Timeout")
        
        client = RedisClient()
        health = client.health_check()
        
        assert health['healthy'] is False
        assert 'Timeout error' in health['error']
    
    def test_is_healthy_success(self, mock_pool, mock_redis):
        """Test is_healthy returns True when Redis is healthy"""
        mock_redis.ping.return_value = True
        
        client = RedisClient()
        assert client.is_healthy() is True
    
    def test_is_healthy_failure(self, mock_pool, mock_redis):
        """Test is_healthy returns False when Redis is unhealthy"""
        mock_redis.ping.side_effect = RedisError("Error")
        
        client = RedisClient()
        assert client.is_healthy() is False
    
    def test_add_hot_message(self, mock_pool, mock_redis):
        """Test adding hot message"""
        client = RedisClient()
        session_id = "test-session"
        message = '{"role": "user", "content": "Hello"}'
        
        client.add_hot_message(session_id, message)
        
        # Verify rpush was called
        expected_key = "hot:test-session:messages"
        mock_redis.rpush.assert_called_once_with(expected_key, message)
        
        # Verify ltrim was called to keep only recent messages
        mock_redis.ltrim.assert_called_once_with(expected_key, -5, -1)
        
        # Verify expiration was set
        mock_redis.expire.assert_called_once()
    
    def test_get_hot_messages(self, mock_pool, mock_redis):
        """Test getting hot messages"""
        mock_redis.lrange.return_value = [
            '{"role": "user", "content": "Hello"}',
            '{"role": "assistant", "content": "Hi"}'
        ]
        
        client = RedisClient()
        messages = client.get_hot_messages("test-session")
        
        assert len(messages) == 2
        assert '{"role": "user", "content": "Hello"}' in messages
    
    def test_set_and_get_hot_slots(self, mock_pool, mock_redis):
        """Test setting and getting hot slots"""
        mock_redis.get.return_value = '{"age": 30, "income": "high"}'
        
        client = RedisClient()
        
        # Set slots
        slots_data = '{"age": 30, "income": "high"}'
        client.set_hot_slots("test-session", slots_data)
        
        # Verify setex was called
        expected_key = "hot:test-session:slots"
        mock_redis.setex.assert_called_once()
        
        # Get slots
        result = client.get_hot_slots("test-session")
        assert result == slots_data
    
    def test_clear_hot_data(self, mock_pool, mock_redis):
        """Test clearing hot data"""
        client = RedisClient()
        session_id = "test-session"
        
        client.clear_hot_data(session_id)
        
        # Verify delete was called with all hot keys
        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args[0]
        assert len(call_args) == 4
        assert f"hot:{session_id}:messages" in call_args
        assert f"hot:{session_id}:slots" in call_args
    
    def test_set_and_get_cache(self, mock_pool, mock_redis):
        """Test cache operations"""
        mock_redis.get.return_value = '{"result": "cached"}'
        
        client = RedisClient()
        
        # Set cache
        key = "cache:test:key"
        value = '{"result": "cached"}'
        client.set_cache(key, value, ttl_seconds=3600)
        
        # Verify setex was called
        mock_redis.setex.assert_called_once()
        
        # Get cache
        result = client.get_cache(key)
        assert result == value
    
    def test_acquire_session_lock_success(self, mock_pool, mock_redis):
        """Test acquiring session lock successfully"""
        mock_redis.set.return_value = True
        
        client = RedisClient()
        result = client.acquire_session_lock("test-session", timeout_seconds=10)
        
        assert result is True
        expected_key = "lock:session:test-session"
        mock_redis.set.assert_called_once_with(expected_key, "locked", nx=True, ex=10)
    
    def test_acquire_session_lock_failure(self, mock_pool, mock_redis):
        """Test acquiring session lock when already locked"""
        mock_redis.set.return_value = False
        
        client = RedisClient()
        result = client.acquire_session_lock("test-session")
        
        assert result is False
    
    def test_release_session_lock(self, mock_pool, mock_redis):
        """Test releasing session lock"""
        client = RedisClient()
        client.release_session_lock("test-session")
        
        expected_key = "lock:session:test-session"
        mock_redis.delete.assert_called_once_with(expected_key)
    
    def test_active_session_management(self, mock_pool, mock_redis):
        """Test active session management"""
        mock_redis.smembers.return_value = {"session-1", "session-2"}
        
        client = RedisClient()
        
        # Add active session
        client.add_active_session("session-1")
        mock_redis.sadd.assert_called_once_with("active:sessions", "session-1")
        
        # Get active sessions
        sessions = client.get_active_sessions()
        assert len(sessions) == 2
        assert "session-1" in sessions
        
        # Remove active session
        client.remove_active_session("session-1")
        mock_redis.srem.assert_called_once_with("active:sessions", "session-1")
    
    def test_increment_metric(self, mock_pool, mock_redis):
        """Test incrementing metric"""
        client = RedisClient()
        key = "metrics:agent:profile"
        
        client.increment_metric(key, amount=5)
        mock_redis.incrby.assert_called_once_with(key, 5)
    
    def test_close(self, mock_pool, mock_redis):
        """Test closing Redis client"""
        mock_pool_instance = MagicMock()
        mock_pool.return_value = mock_pool_instance
        
        client = RedisClient()
        client.close()
        
        mock_pool_instance.disconnect.assert_called_once()


class TestGlobalRedisClient:
    """Test global Redis client singleton"""
    
    def test_get_redis_client_singleton(self):
        """Test that get_redis_client returns singleton instance"""
        with patch('utils.redis_client.RedisClient') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            # First call creates instance
            client1 = get_redis_client()
            
            # Second call returns same instance
            client2 = get_redis_client()
            
            assert client1 is client2
            mock_class.assert_called_once()
    
    def test_close_redis_client(self):
        """Test closing global Redis client"""
        # Reset global client first
        import utils.redis_client
        utils.redis_client._redis_client = None
        
        with patch('utils.redis_client.RedisClient') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            # Get client
            client = get_redis_client()
            
            # Close client
            close_redis_client()
            
            # Verify close was called
            mock_instance.close.assert_called_once()

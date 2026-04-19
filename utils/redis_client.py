"""
Redis client with connection pool, key naming conventions, and health checks
"""
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from config import get_settings

logger = logging.getLogger(__name__)


class RedisKeyNamespace:
    """Redis key naming conventions"""
    
    # Hot data layer - recent conversation messages
    HOT_SESSION = "hot:{session_id}:messages"
    HOT_SLOTS = "hot:{session_id}:slots"
    HOT_CONTEXT = "hot:{session_id}:context"
    HOT_METADATA = "hot:{session_id}:metadata"
    
    # Cache layer
    CACHE_RECOMMENDATION = "cache:recommendation:{profile_hash}"
    CACHE_PRODUCT_VECTOR = "cache:product:{product_id}:vector"
    CACHE_USER_PROFILE = "cache:user:{user_id}:profile"
    
    # Session management
    SESSION_LOCK = "lock:session:{session_id}"
    SESSION_STATE = "state:session:{session_id}"
    SESSION_ACTIVE = "active:sessions"
    
    # Performance metrics
    METRICS_AGENT = "metrics:agent:{agent_name}"
    METRICS_SESSION = "metrics:session:{session_id}"
    
    @staticmethod
    def hot_messages(session_id: str) -> str:
        """Get key for hot messages"""
        return f"hot:{session_id}:messages"
    
    @staticmethod
    def hot_slots(session_id: str) -> str:
        """Get key for hot slots"""
        return f"hot:{session_id}:slots"
    
    @staticmethod
    def hot_context(session_id: str) -> str:
        """Get key for hot context"""
        return f"hot:{session_id}:context"
    
    @staticmethod
    def hot_metadata(session_id: str) -> str:
        """Get key for hot metadata"""
        return f"hot:{session_id}:metadata"
    
    @staticmethod
    def cache_recommendation(profile_hash: str) -> str:
        """Get key for cached recommendation"""
        return f"cache:recommendation:{profile_hash}"
    
    @staticmethod
    def cache_product_vector(product_id: str) -> str:
        """Get key for cached product vector"""
        return f"cache:product:{product_id}:vector"
    
    @staticmethod
    def cache_user_profile(user_id: str) -> str:
        """Get key for cached user profile"""
        return f"cache:user:{user_id}:profile"
    
    @staticmethod
    def session_lock(session_id: str) -> str:
        """Get key for session lock"""
        return f"lock:session:{session_id}"
    
    @staticmethod
    def session_state(session_id: str) -> str:
        """Get key for session state"""
        return f"state:session:{session_id}"
    
    @staticmethod
    def metrics_agent(agent_name: str) -> str:
        """Get key for agent metrics"""
        return f"metrics:agent:{agent_name}"
    
    @staticmethod
    def metrics_session(session_id: str) -> str:
        """Get key for session metrics"""
        return f"metrics:session:{session_id}"
    
    @staticmethod
    def get_all_hot_keys(session_id: str) -> List[str]:
        """Get all hot data keys for a session"""
        return [
            RedisKeyNamespace.hot_messages(session_id),
            RedisKeyNamespace.hot_slots(session_id),
            RedisKeyNamespace.hot_context(session_id),
            RedisKeyNamespace.hot_metadata(session_id),
        ]


class RedisClient:
    """Redis client with connection pool and health checks"""
    
    def __init__(self):
        """Initialize Redis client with connection pool"""
        self.settings = get_settings()
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize Redis connection pool"""
        try:
            # Create connection pool
            self._pool = ConnectionPool(
                host=self.settings.REDIS_HOST,
                port=self.settings.REDIS_PORT,
                db=self.settings.REDIS_DB,
                password=self.settings.REDIS_PASSWORD,
                max_connections=50,  # Maximum connections in pool
                socket_timeout=5,    # Socket timeout in seconds
                socket_connect_timeout=5,  # Connection timeout
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30,  # Health check every 30 seconds
                decode_responses=True,  # Automatically decode responses to strings
            )
            
            # Create Redis client from pool
            self._client = redis.Redis(connection_pool=self._pool)
            
            logger.info(
                f"Redis connection pool initialized: "
                f"host={self.settings.REDIS_HOST}, "
                f"port={self.settings.REDIS_PORT}, "
                f"db={self.settings.REDIS_DB}"
            )
            
        except RedisError as e:
            logger.error(f"Failed to initialize Redis connection pool: {e}")
            raise
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        return self._client
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform Redis health check
        
        Returns:
            Dict with health status information
        """
        health_status = {
            "healthy": False,
            "redis_host": self.settings.REDIS_HOST,
            "redis_port": self.settings.REDIS_PORT,
            "redis_db": self.settings.REDIS_DB,
            "error": None,
            "ping_response": None,
            "info": {}
        }
        
        try:
            # Test connection with PING
            ping_response = self._client.ping()
            health_status["ping_response"] = ping_response
            
            # Get Redis server info
            info = self._client.info()
            health_status["info"] = {
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
            
            # Check if we can write and read
            test_key = "health_check:test"
            test_value = "ok"
            self._client.setex(test_key, 10, test_value)
            read_value = self._client.get(test_key)
            
            if read_value == test_value:
                health_status["healthy"] = True
                logger.debug("Redis health check passed")
            else:
                health_status["error"] = "Write/read test failed"
                logger.warning("Redis health check failed: write/read test failed")
            
            # Clean up test key
            self._client.delete(test_key)
            
        except ConnectionError as e:
            health_status["error"] = f"Connection error: {str(e)}"
            logger.error(f"Redis health check failed: {e}")
        except TimeoutError as e:
            health_status["error"] = f"Timeout error: {str(e)}"
            logger.error(f"Redis health check timeout: {e}")
        except RedisError as e:
            health_status["error"] = f"Redis error: {str(e)}"
            logger.error(f"Redis health check error: {e}")
        except Exception as e:
            health_status["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"Redis health check unexpected error: {e}")
        
        return health_status
    
    def is_healthy(self) -> bool:
        """
        Quick health check - returns True if Redis is healthy
        
        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            return self._client.ping()
        except RedisError:
            return False
    
    # Hot data operations
    
    def add_hot_message(self, session_id: str, message: str, max_messages: int = 5) -> None:
        """
        Add message to hot data layer (recent messages)
        
        Args:
            session_id: Session ID
            message: Message content (JSON string)
            max_messages: Maximum number of messages to keep (default: 5)
        """
        key = RedisKeyNamespace.hot_messages(session_id)
        
        # Add message to list (right push)
        self._client.rpush(key, message)
        
        # Trim list to keep only recent messages
        self._client.ltrim(key, -max_messages, -1)
        
        # Set expiration (30 minutes)
        self._client.expire(key, timedelta(minutes=30))
    
    def get_hot_messages(self, session_id: str) -> List[str]:
        """
        Get hot messages for a session
        
        Args:
            session_id: Session ID
            
        Returns:
            List of message strings (JSON)
        """
        key = RedisKeyNamespace.hot_messages(session_id)
        return self._client.lrange(key, 0, -1)
    
    def set_hot_slots(self, session_id: str, slots: str) -> None:
        """
        Set hot slots data
        
        Args:
            session_id: Session ID
            slots: Slots data (JSON string)
        """
        key = RedisKeyNamespace.hot_slots(session_id)
        self._client.setex(key, timedelta(minutes=30), slots)
    
    def get_hot_slots(self, session_id: str) -> Optional[str]:
        """
        Get hot slots data
        
        Args:
            session_id: Session ID
            
        Returns:
            Slots data (JSON string) or None
        """
        key = RedisKeyNamespace.hot_slots(session_id)
        return self._client.get(key)
    
    def set_hot_context(self, session_id: str, context: str) -> None:
        """
        Set hot context data
        
        Args:
            session_id: Session ID
            context: Context data (JSON string)
        """
        key = RedisKeyNamespace.hot_context(session_id)
        self._client.setex(key, timedelta(minutes=30), context)
    
    def get_hot_context(self, session_id: str) -> Optional[str]:
        """
        Get hot context data
        
        Args:
            session_id: Session ID
            
        Returns:
            Context data (JSON string) or None
        """
        key = RedisKeyNamespace.hot_context(session_id)
        return self._client.get(key)
    
    def clear_hot_data(self, session_id: str) -> None:
        """
        Clear all hot data for a session
        
        Args:
            session_id: Session ID
        """
        keys = RedisKeyNamespace.get_all_hot_keys(session_id)
        if keys:
            self._client.delete(*keys)
        logger.info(f"Cleared hot data for session: {session_id}")
    
    # Cache operations
    
    def set_cache(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """
        Set cache value with TTL
        
        Args:
            key: Cache key
            value: Cache value (JSON string)
            ttl_seconds: Time to live in seconds (default: 1 hour)
        """
        self._client.setex(key, timedelta(seconds=ttl_seconds), value)
    
    def get_cache(self, key: str) -> Optional[str]:
        """
        Get cache value
        
        Args:
            key: Cache key
            
        Returns:
            Cache value (JSON string) or None
        """
        return self._client.get(key)
    
    def delete_cache(self, key: str) -> None:
        """
        Delete cache value
        
        Args:
            key: Cache key
        """
        self._client.delete(key)
    
    # Session management
    
    def acquire_session_lock(self, session_id: str, timeout_seconds: int = 10) -> bool:
        """
        Acquire lock for a session (for concurrency control)
        
        Args:
            session_id: Session ID
            timeout_seconds: Lock timeout in seconds
            
        Returns:
            True if lock acquired, False otherwise
        """
        key = RedisKeyNamespace.session_lock(session_id)
        return self._client.set(key, "locked", nx=True, ex=timeout_seconds)
    
    def release_session_lock(self, session_id: str) -> None:
        """
        Release lock for a session
        
        Args:
            session_id: Session ID
        """
        key = RedisKeyNamespace.session_lock(session_id)
        self._client.delete(key)
    
    def add_active_session(self, session_id: str) -> None:
        """
        Add session to active sessions set
        
        Args:
            session_id: Session ID
        """
        self._client.sadd(RedisKeyNamespace.SESSION_ACTIVE, session_id)
    
    def remove_active_session(self, session_id: str) -> None:
        """
        Remove session from active sessions set
        
        Args:
            session_id: Session ID
        """
        self._client.srem(RedisKeyNamespace.SESSION_ACTIVE, session_id)
    
    def get_active_sessions(self) -> List[str]:
        """
        Get all active session IDs
        
        Returns:
            List of active session IDs
        """
        return list(self._client.smembers(RedisKeyNamespace.SESSION_ACTIVE))
    
    # Metrics operations
    
    def increment_metric(self, key: str, amount: int = 1) -> None:
        """
        Increment a metric counter
        
        Args:
            key: Metric key
            amount: Amount to increment (default: 1)
        """
        self._client.incrby(key, amount)
    
    def set_metric(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """
        Set a metric value
        
        Args:
            key: Metric key
            value: Metric value
            ttl_seconds: Time to live in seconds
        """
        self._client.setex(key, timedelta(seconds=ttl_seconds), value)
    
    def get_metric(self, key: str) -> Optional[str]:
        """
        Get a metric value
        
        Args:
            key: Metric key
            
        Returns:
            Metric value or None
        """
        return self._client.get(key)
    
    def close(self):
        """Close Redis connection pool"""
        if self._pool:
            self._pool.disconnect()
            logger.info("Redis connection pool closed")


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """
    Get global Redis client instance (singleton pattern)
    
    Returns:
        RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis_client():
    """Close global Redis client"""
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None

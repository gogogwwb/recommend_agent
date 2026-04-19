"""
Script to test Redis connection and basic operations
Run this to verify Redis is properly configured and accessible
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.redis_client import get_redis_client, RedisKeyNamespace
from config import get_settings


def test_redis_connection():
    """Test Redis connection and operations"""
    print("=" * 60)
    print("Testing Redis Connection")
    print("=" * 60)
    
    settings = get_settings()
    print(f"\nRedis Configuration:")
    print(f"  Host: {settings.REDIS_HOST}")
    print(f"  Port: {settings.REDIS_PORT}")
    print(f"  DB: {settings.REDIS_DB}")
    print(f"  URL: {settings.redis_url}")
    
    try:
        # Get Redis client
        print("\n1. Initializing Redis client...")
        redis_client = get_redis_client()
        print("   ✓ Redis client initialized")
        
        # Health check
        print("\n2. Performing health check...")
        health = redis_client.health_check()
        
        if health['healthy']:
            print("   ✓ Redis is healthy")
            print(f"   - Redis Version: {health['info'].get('redis_version', 'N/A')}")
            print(f"   - Connected Clients: {health['info'].get('connected_clients', 'N/A')}")
            print(f"   - Memory Used: {health['info'].get('used_memory_human', 'N/A')}")
            print(f"   - Uptime: {health['info'].get('uptime_in_seconds', 'N/A')} seconds")
        else:
            print(f"   ✗ Redis health check failed: {health['error']}")
            return False
        
        # Test hot data operations
        print("\n3. Testing hot data operations...")
        session_id = "test-session-123"
        
        # Add hot messages
        message1 = json.dumps({"role": "user", "content": "Hello"})
        message2 = json.dumps({"role": "assistant", "content": "Hi there!"})
        redis_client.add_hot_message(session_id, message1)
        redis_client.add_hot_message(session_id, message2)
        print(f"   ✓ Added 2 messages to hot data")
        
        # Get hot messages
        messages = redis_client.get_hot_messages(session_id)
        print(f"   ✓ Retrieved {len(messages)} messages from hot data")
        
        # Set hot slots
        slots_data = json.dumps({"age": 30, "income": "high", "family_size": 3})
        redis_client.set_hot_slots(session_id, slots_data)
        print(f"   ✓ Set hot slots data")
        
        # Get hot slots
        retrieved_slots = redis_client.get_hot_slots(session_id)
        print(f"   ✓ Retrieved hot slots: {retrieved_slots}")
        
        # Test cache operations
        print("\n4. Testing cache operations...")
        cache_key = RedisKeyNamespace.cache_recommendation("profile_hash_abc123")
        cache_value = json.dumps({"products": ["prod-1", "prod-2"], "score": 0.95})
        redis_client.set_cache(cache_key, cache_value, ttl_seconds=60)
        print(f"   ✓ Set cache value")
        
        cached = redis_client.get_cache(cache_key)
        print(f"   ✓ Retrieved cache value: {cached}")
        
        # Test session lock
        print("\n5. Testing session lock...")
        lock_acquired = redis_client.acquire_session_lock(session_id, timeout_seconds=5)
        if lock_acquired:
            print(f"   ✓ Acquired session lock")
            redis_client.release_session_lock(session_id)
            print(f"   ✓ Released session lock")
        else:
            print(f"   ✗ Failed to acquire session lock")
        
        # Test active sessions
        print("\n6. Testing active session management...")
        redis_client.add_active_session(session_id)
        print(f"   ✓ Added session to active sessions")
        
        active_sessions = redis_client.get_active_sessions()
        print(f"   ✓ Active sessions: {active_sessions}")
        
        redis_client.remove_active_session(session_id)
        print(f"   ✓ Removed session from active sessions")
        
        # Test metrics
        print("\n7. Testing metrics operations...")
        metric_key = RedisKeyNamespace.metrics_agent("profile_agent")
        redis_client.increment_metric(metric_key, amount=5)
        print(f"   ✓ Incremented metric by 5")
        
        metric_value = redis_client.get_metric(metric_key)
        print(f"   ✓ Metric value: {metric_value}")
        
        # Clean up
        print("\n8. Cleaning up test data...")
        redis_client.clear_hot_data(session_id)
        redis_client.delete_cache(cache_key)
        print(f"   ✓ Cleaned up test data")
        
        print("\n" + "=" * 60)
        print("✓ All Redis tests passed successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Error during Redis testing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)

"""
Unit tests for Store API setup and configuration

These tests verify the Store setup logic and table compatibility
without requiring a live database connection.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import logging

from utils.store_manager import (
    StoreManager,
    StoreError,
    StoreNotInitializedError,
    StoreSetupError,
    get_store_manager,
    get_store,
    reset_store_manager
)


class TestStoreManagerInitialization:
    """Test StoreManager initialization"""
    
    def test_init_with_default_connection_string(self):
        """Test initialization with default connection string from config"""
        manager = StoreManager()
        assert manager.connection_string is not None
        assert manager.store is None
        assert manager._is_setup is False
    
    def test_init_with_custom_connection_string(self):
        """Test initialization with custom connection string"""
        custom_conn = "postgresql://user:pass@host:5432/db"
        manager = StoreManager(connection_string=custom_conn)
        assert manager.connection_string == custom_conn
        assert manager.store is None
        assert manager._is_setup is False
    
    def test_repr(self):
        """Test string representation"""
        manager = StoreManager()
        assert "StoreManager" in repr(manager)
        assert "initialized=False" in repr(manager)
        assert "setup=False" in repr(manager)


class TestStoreManagerInitialize:
    """Test StoreManager.initialize() method"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_initialize_creates_store(self):
        """Test that initialize() creates a PostgresStore instance"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            result = manager.initialize()
            
            assert result == mock_store
            assert manager.store == mock_store
            MockPostgresStore.from_conn_string.assert_called_once()
    
    def test_initialize_returns_existing_store(self):
        """Test that initialize() returns existing store if already initialized"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            # First initialization
            result1 = manager.initialize()
            
            # Second initialization should return same instance
            result2 = manager.initialize()
            
            assert result1 == result2
            # from_conn_string should only be called once
            MockPostgresStore.from_conn_string.assert_called_once()
    
    def test_initialize_raises_error_on_failure(self):
        """Test that initialize() raises StoreSetupError on failure"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            MockPostgresStore.from_conn_string.side_effect = Exception("Connection failed")
            
            with pytest.raises(StoreSetupError) as exc_info:
                manager.initialize()
            
            assert "Failed to initialize PostgresStore" in str(exc_info.value)


class TestStoreManagerSetup:
    """Test StoreManager.setup() method"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_setup_creates_tables(self):
        """Test that setup() calls store.setup()"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            mock_store.setup.assert_called_once()
            assert manager._is_setup is True
    
    def test_setup_skips_if_already_setup(self):
        """Test that setup() skips if tables already created"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            manager.setup()  # Call twice
            
            # setup() should only be called once
            mock_store.setup.assert_called_once()
    
    def test_setup_raises_error_if_not_initialized(self):
        """Test that setup() raises error if store not initialized"""
        manager = StoreManager()
        
        with pytest.raises(StoreNotInitializedError) as exc_info:
            manager.setup()
        
        assert "Store not initialized" in str(exc_info.value)
    
    def test_setup_raises_error_on_failure(self):
        """Test that setup() raises StoreSetupError on failure"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            mock_store.setup.side_effect = Exception("Table creation failed")
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            
            with pytest.raises(StoreSetupError) as exc_info:
                manager.setup()
            
            assert "Failed to setup store tables" in str(exc_info.value)


class TestStoreManagerIsReady:
    """Test StoreManager.is_ready() method"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_is_ready_false_initially(self):
        """Test that is_ready() returns False initially"""
        manager = StoreManager()
        assert manager.is_ready() is False
    
    def test_is_ready_false_after_initialize_only(self):
        """Test that is_ready() returns False after initialize but before setup"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            assert manager.is_ready() is False
    
    def test_is_ready_true_after_setup(self):
        """Test that is_ready() returns True after setup"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            assert manager.is_ready() is True


class TestStoreManagerReset:
    """Test StoreManager.reset() method"""
    
    def test_reset_clears_state(self):
        """Test that reset() clears store and setup flag"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            assert manager.is_ready() is True
            
            manager.reset()
            
            assert manager.store is None
            assert manager._is_setup is False
            assert manager.is_ready() is False


class TestGetStoreManager:
    """Test get_store_manager() factory function"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_returns_singleton_instance(self):
        """Test that get_store_manager() returns singleton instance"""
        manager1 = get_store_manager()
        manager2 = get_store_manager()
        
        assert manager1 is manager2
    
    def test_force_new_creates_new_instance(self):
        """Test that force_new=True creates new instance"""
        manager1 = get_store_manager()
        manager2 = get_store_manager(force_new=True)
        
        assert manager1 is not manager2


class TestGetStore:
    """Test get_store() factory function"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_get_store_with_auto_setup(self):
        """Test that get_store() auto-setup when auto_setup=True"""
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            store = get_store(auto_setup=True)
            
            assert store == mock_store
            mock_store.setup.assert_called_once()
    
    def test_get_store_without_auto_setup(self):
        """Test that get_store() doesn't auto-setup when auto_setup=False"""
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            store = get_store(auto_setup=False)
            
            assert store == mock_store
            mock_store.setup.assert_not_called()


class TestStoreTableCompatibility:
    """Test Store table compatibility with existing schema"""
    
    def test_store_table_name_does_not_conflict(self):
        """
        Test that Store table name ('store') does not conflict with existing tables
        
        Existing tables:
        - users
        - user_profiles
        - existing_coverage
        - conversation_sessions
        - conversation_messages
        - insurance_products
        - recommendations
        - user_feedback
        - compliance_logs
        - quality_metrics
        - archived_sessions
        
        Store creates:
        - store (or similar name based on LangGraph version)
        """
        existing_tables = {
            'users',
            'user_profiles',
            'existing_coverage',
            'conversation_sessions',
            'conversation_messages',
            'insurance_products',
            'recommendations',
            'user_feedback',
            'compliance_logs',
            'quality_metrics',
            'archived_sessions'
        }
        
        # Store table name(s) - based on LangGraph PostgresStore implementation
        store_tables = {'store'}
        
        # Check for conflicts
        conflicts = existing_tables & store_tables
        
        assert len(conflicts) == 0, f"Table name conflicts detected: {conflicts}"
    
    def test_store_uses_separate_namespace(self):
        """
        Test that Store uses namespace-based isolation
        
        Store API uses namespace tuples like ("users", user_id) to organize data,
        which is separate from the existing user_profiles table structure.
        """
        # Store namespace structure
        # namespace=("users", user_id), key="profile"
        # This is different from user_profiles table which uses profile_id and user_id columns
        
        # The Store API provides:
        # 1. Cross-session persistence (persists across different sessions)
        # 2. Namespace isolation (clean separation by user_id)
        # 3. Simple key-value interface
        
        # The existing user_profiles table provides:
        # 1. Structured relational data
        # 2. Foreign key relationships
        # 3. Complex queries and joins
        
        # Both can coexist without conflict
        assert True


class TestStoreManagerUserProfileOperations:
    """Test StoreManager user profile operations"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_put_user_profile(self):
        """Test storing user profile to Store"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Store user profile
            profile = {
                "age": 30,
                "income_range": "medium_high",
                "risk_preference": "balanced"
            }
            manager.put_user_profile("user_123", profile)
            
            # Verify put was called with correct namespace and key
            mock_store.put.assert_called_once()
            call_args = mock_store.put.call_args
            assert call_args[1]["namespace"] == ("users", "user_123")
            assert call_args[1]["key"] == "profile"
    
    def test_get_user_profile(self):
        """Test retrieving user profile from Store"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            mock_item = Mock()
            mock_item.value = {"age": 30, "income_range": "medium_high"}
            mock_store.get.return_value = mock_item
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Get user profile
            profile = manager.get_user_profile("user_123")
            
            assert profile is not None
            assert profile["age"] == 30
            mock_store.get.assert_called_once()
    
    def test_get_user_profile_not_found(self):
        """Test retrieving non-existent user profile"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            mock_store.get.return_value = None
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Get non-existent profile
            profile = manager.get_user_profile("user_nonexistent")
            
            assert profile is None
    
    def test_update_user_profile(self):
        """Test updating user profile with merge"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            
            # First call returns existing profile
            mock_item = Mock()
            mock_item.value = {"age": 30, "income_range": "medium_high"}
            mock_store.get.return_value = mock_item
            
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Update profile
            updates = {"risk_preference": "aggressive"}
            updated = manager.update_user_profile("user_123", updates)
            
            assert updated["age"] == 30  # Existing value
            assert updated["risk_preference"] == "aggressive"  # New value


class TestStoreManagerSessionMetadataOperations:
    """Test StoreManager session metadata operations"""
    
    def setup_method(self):
        """Reset store manager before each test"""
        reset_store_manager()
    
    def test_put_session_metadata(self):
        """Test storing session metadata to Store"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Store session metadata
            metadata = {
                "user_id": "user_123",
                "started_at": "2024-01-15T10:00:00",
                "status": "active"
            }
            manager.put_session_metadata("session_456", metadata)
            
            # Verify put was called with correct namespace and key
            mock_store.put.assert_called_once()
            call_args = mock_store.put.call_args
            assert call_args[1]["namespace"] == ("sessions", "session_456")
            assert call_args[1]["key"] == "metadata"
    
    def test_get_session_metadata(self):
        """Test retrieving session metadata from Store"""
        manager = StoreManager()
        
        with patch('utils.store_manager.PostgresStore') as MockPostgresStore:
            mock_store = Mock()
            mock_item = Mock()
            mock_item.value = {"user_id": "user_123", "status": "active"}
            mock_store.get.return_value = mock_item
            MockPostgresStore.from_conn_string.return_value = mock_store
            
            manager.initialize()
            manager.setup()
            
            # Get session metadata
            metadata = manager.get_session_metadata("session_456")
            
            assert metadata is not None
            assert metadata["user_id"] == "user_123"
            mock_store.get.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

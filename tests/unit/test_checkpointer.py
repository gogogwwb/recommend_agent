"""
Unit tests for PostgresSaver Checkpointer Manager

Tests the checkpointer initialization, setup, and factory methods.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import threading

from utils.checkpointer import (
    CheckpointerManager,
    CheckpointerError,
    CheckpointerNotInitializedError,
    CheckpointerSetupError,
    get_checkpointer_manager,
    get_checkpointer,
    reset_checkpointer,
)


class TestCheckpointerManager:
    """Tests for CheckpointerManager class"""
    
    def test_init_with_default_connection_string(self):
        """Test initialization with default connection string from config"""
        manager = CheckpointerManager()
        assert manager.connection_string is not None
        assert manager.checkpointer is None
        assert manager._is_setup is False
    
    def test_init_with_custom_connection_string(self):
        """Test initialization with custom connection string"""
        custom_conn = "postgresql://user:pass@host:5432/db"
        manager = CheckpointerManager(connection_string=custom_conn)
        assert manager.connection_string == custom_conn
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_initialize_creates_checkpointer(self, mock_postgres_saver):
        """Test that initialize() creates PostgresSaver instance"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        result = manager.initialize()
        
        assert result == mock_saver
        assert manager.checkpointer == mock_saver
        mock_postgres_saver.from_conn_string.assert_called_once_with("postgresql://test")
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_initialize_idempotent(self, mock_postgres_saver):
        """Test that initialize() is idempotent - doesn't recreate if already initialized"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        result1 = manager.initialize()
        result2 = manager.initialize()
        
        assert result1 == result2
        mock_postgres_saver.from_conn_string.assert_called_once()
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_initialize_failure_raises_error(self, mock_postgres_saver):
        """Test that initialization failure raises CheckpointerSetupError"""
        mock_postgres_saver.from_conn_string.side_effect = Exception("Connection failed")
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        
        with pytest.raises(CheckpointerSetupError) as exc_info:
            manager.initialize()
        
        assert "Connection failed" in str(exc_info.value)
    
    def test_setup_without_initialize_raises_error(self):
        """Test that setup() without initialize() raises error"""
        manager = CheckpointerManager(connection_string="postgresql://test")
        
        with pytest.raises(CheckpointerNotInitializedError):
            manager.setup()
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_setup_creates_tables(self, mock_postgres_saver):
        """Test that setup() calls checkpointer.setup()"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        manager.initialize()
        manager.setup()
        
        mock_saver.setup.assert_called_once()
        assert manager._is_setup is True
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_setup_idempotent(self, mock_postgres_saver):
        """Test that setup() is idempotent"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        manager.initialize()
        manager.setup()
        manager.setup()  # Call again
        
        mock_saver.setup.assert_called_once()
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_setup_failure_raises_error(self, mock_postgres_saver):
        """Test that setup failure raises CheckpointerSetupError"""
        mock_saver = Mock()
        mock_saver.setup.side_effect = Exception("Table creation failed")
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        manager.initialize()
        
        with pytest.raises(CheckpointerSetupError) as exc_info:
            manager.setup()
        
        assert "Table creation failed" in str(exc_info.value)
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_get_checkpointer_auto_initializes(self, mock_postgres_saver):
        """Test that get_checkpointer() auto-initializes if needed"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        result = manager.get_checkpointer()
        
        assert result == mock_saver
        assert manager.checkpointer is not None
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_is_ready(self, mock_postgres_saver):
        """Test is_ready() returns correct status"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        
        # Not ready before initialization
        assert manager.is_ready() is False
        
        # Not ready after initialization but before setup
        manager.initialize()
        assert manager.is_ready() is False
        
        # Ready after setup
        manager.setup()
        assert manager.is_ready() is True
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_reset(self, mock_postgres_saver):
        """Test reset() clears the checkpointer state"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        manager = CheckpointerManager(connection_string="postgresql://test")
        manager.initialize()
        manager.setup()
        
        assert manager.is_ready() is True
        
        manager.reset()
        
        assert manager.checkpointer is None
        assert manager._is_setup is False
    
    def test_repr(self):
        """Test __repr__ returns meaningful string"""
        manager = CheckpointerManager(connection_string="postgresql://test")
        repr_str = repr(manager)
        
        assert "CheckpointerManager" in repr_str
        assert "initialized=False" in repr_str
        assert "setup=False" in repr_str


class TestGlobalFunctions:
    """Tests for global factory functions"""
    
    def setup_method(self):
        """Reset global state before each test"""
        reset_checkpointer()
    
    def teardown_method(self):
        """Reset global state after each test"""
        reset_checkpointer()
    
    def test_get_checkpointer_manager_singleton(self):
        """Test that get_checkpointer_manager returns singleton"""
        manager1 = get_checkpointer_manager()
        manager2 = get_checkpointer_manager()
        
        assert manager1 is manager2
    
    def test_get_checkpointer_manager_force_new(self):
        """Test that force_new creates new instance"""
        manager1 = get_checkpointer_manager()
        manager2 = get_checkpointer_manager(force_new=True)
        
        assert manager1 is not manager2
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_get_checkpointer_returns_checkpointer(self, mock_postgres_saver):
        """Test that get_checkpointer returns PostgresSaver instance"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        result = get_checkpointer()
        
        assert result == mock_saver
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_get_checkpointer_auto_setup(self, mock_postgres_saver):
        """Test that get_checkpointer with auto_setup=True calls setup"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        get_checkpointer(auto_setup=True)
        
        mock_saver.setup.assert_called_once()
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_get_checkpointer_no_auto_setup(self, mock_postgres_saver):
        """Test that get_checkpointer with auto_setup=False doesn't call setup"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        get_checkpointer(auto_setup=False)
        
        mock_saver.setup.assert_not_called()
    
    def test_reset_checkpointer_clears_global(self):
        """Test that reset_checkpointer clears global instance"""
        manager1 = get_checkpointer_manager()
        assert manager1 is not None
        
        reset_checkpointer()
        
        # Get new manager - should be different instance
        manager2 = get_checkpointer_manager()
        assert manager1 is not manager2


class TestThreadSafety:
    """Tests for thread safety"""
    
    def setup_method(self):
        """Reset global state before each test"""
        reset_checkpointer()
    
    def teardown_method(self):
        """Reset global state after each test"""
        reset_checkpointer()
    
    @patch('utils.checkpointer.PostgresSaver')
    def test_concurrent_initialization(self, mock_postgres_saver):
        """Test that concurrent initialization is thread-safe"""
        mock_saver = Mock()
        mock_postgres_saver.from_conn_string.return_value = mock_saver
        
        results = []
        errors = []
        
        def init_checkpointer():
            try:
                manager = get_checkpointer_manager()
                manager.initialize()
                results.append(manager)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=init_checkpointer) for _ in range(10)]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should have no errors
        assert len(errors) == 0
        
        # All results should be the same instance (singleton)
        assert all(r is results[0] for r in results)
        
        # from_conn_string should only be called once
        mock_postgres_saver.from_conn_string.assert_called_once()

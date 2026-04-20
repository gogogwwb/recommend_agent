"""
Unit tests for LangSmith Configuration
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from utils.langsmith_config import (
    configure_langsmith,
    is_tracing_enabled,
    get_trace_config,
    trace_context,
)


# ==================== Fixtures ====================

@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test"""
    # Save original values
    original = {}
    for key in ["LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_WORKSPACE_ID"]:
        original[key] = os.environ.get(key)
        if key in os.environ:
            del os.environ[key]
    
    yield
    
    # Restore original values
    for key, value in original.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


# ==================== Configuration Tests ====================

class TestConfigureLangSmith:
    """Tests for configure_langsmith function"""
    
    def test_configure_with_all_params(self):
        """Test configuration with all parameters"""
        configure_langsmith(
            tracing=True,
            api_key="test_api_key",
            project="test-project",
            workspace_id="test-workspace"
        )
        
        assert os.environ["LANGSMITH_TRACING"] == "true"
        assert os.environ["LANGSMITH_API_KEY"] == "test_api_key"
        assert os.environ["LANGSMITH_PROJECT"] == "test-project"
        assert os.environ["LANGSMITH_WORKSPACE_ID"] == "test-workspace"
    
    def test_configure_tracing_false(self):
        """Test configuration with tracing=False"""
        configure_langsmith(tracing=False)
        
        assert os.environ["LANGSMITH_TRACING"] == "false"
    
    def test_configure_with_none_params(self):
        """Test configuration with None parameters (should not set)"""
        configure_langsmith(tracing=None, api_key=None, project=None)
        
        # Should not set any values
        assert "LANGSMITH_TRACING" not in os.environ
        assert "LANGSMITH_API_KEY" not in os.environ
    
    @patch('utils.langsmith_config.get_settings')
    def test_configure_from_settings(self, mock_get_settings):
        """Test configuration from settings"""
        mock_settings = MagicMock()
        mock_settings.LANGSMITH_TRACING = True
        mock_settings.LANGSMITH_API_KEY = "settings_api_key"
        mock_settings.LANGSMITH_PROJECT = "settings-project"
        mock_settings.LANGSMITH_WORKSPACE_ID = None
        mock_get_settings.return_value = mock_settings
        
        configure_langsmith()
        
        assert os.environ["LANGSMITH_TRACING"] == "true"
        assert os.environ["LANGSMITH_API_KEY"] == "settings_api_key"
        assert os.environ["LANGSMITH_PROJECT"] == "settings-project"


class TestIsTracingEnabled:
    """Tests for is_tracing_enabled function"""
    
    def test_tracing_enabled(self):
        """Test when tracing is enabled"""
        os.environ["LANGSMITH_TRACING"] = "true"
        assert is_tracing_enabled() is True
    
    def test_tracing_disabled(self):
        """Test when tracing is disabled"""
        os.environ["LANGSMITH_TRACING"] = "false"
        assert is_tracing_enabled() is False
    
    def test_tracing_not_set(self):
        """Test when tracing is not set"""
        assert is_tracing_enabled() is False
    
    def test_tracing_case_insensitive(self):
        """Test that tracing is case insensitive"""
        os.environ["LANGSMITH_TRACING"] = "TRUE"
        assert is_tracing_enabled() is True


# ==================== Trace Config Tests ====================

class TestGetTraceConfig:
    """Tests for get_trace_config function"""
    
    def test_basic_config(self):
        """Test basic config generation"""
        config = get_trace_config()
        
        assert "tags" in config
        assert "metadata" in config
        assert "development" in config["tags"]
        assert config["metadata"]["environment"] == "development"
    
    def test_config_with_user_and_session(self):
        """Test config with user_id and session_id"""
        config = get_trace_config(
            user_id="user_123",
            session_id="session_456"
        )
        
        assert config["metadata"]["user_id"] == "user_123"
        assert config["metadata"]["session_id"] == "session_456"
    
    def test_config_with_custom_tags(self):
        """Test config with custom tags"""
        config = get_trace_config(
            environment="production",
            tags=["recommendation", "insurance"]
        )
        
        assert "production" in config["tags"]
        assert "recommendation" in config["tags"]
        assert "insurance" in config["tags"]
    
    def test_config_with_all_params(self):
        """Test config with all parameters"""
        config = get_trace_config(
            user_id="user_123",
            session_id="session_456",
            environment="staging",
            tags=["test", "demo"]
        )
        
        assert config["metadata"]["user_id"] == "user_123"
        assert config["metadata"]["session_id"] == "session_456"
        assert config["metadata"]["environment"] == "staging"
        assert "staging" in config["tags"]
        assert "test" in config["tags"]
        assert "demo" in config["tags"]


# ==================== Trace Context Tests ====================

class TestTraceContext:
    """Tests for trace_context context manager"""
    
    def test_trace_context_without_langsmith(self):
        """Test trace_context when langsmith is not installed"""
        with patch.dict('sys.modules', {'langsmith': None}):
            # Should not raise error
            with trace_context(enabled=True):
                pass
    
    def test_trace_context_with_langsmith(self):
        """Test trace_context with langsmith installed"""
        # Create a mock for langsmith module
        mock_ls = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=None)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_ls.tracing_context.return_value = mock_context
        
        with patch.dict('sys.modules', {'langsmith': mock_ls}):
            # Re-import to get the mocked module
            from utils import langsmith_config
            import importlib
            importlib.reload(langsmith_config)
            
            with langsmith_config.trace_context(
                enabled=True,
                project_name="test-project",
                tags=["test"],
                metadata={"key": "value"}
            ):
                pass


# ==================== Integration Tests ====================

class TestLangSmithIntegration:
    """Integration tests for LangSmith configuration"""
    
    def test_full_configuration_flow(self):
        """Test full configuration flow"""
        # 1. Configure LangSmith
        configure_langsmith(
            tracing=True,
            api_key="test_key",
            project="test-project"
        )
        
        # 2. Check tracing is enabled
        assert is_tracing_enabled() is True
        
        # 3. Get trace config
        config = get_trace_config(
            user_id="user_123",
            session_id="session_456",
            environment="production"
        )
        
        # 4. Verify config
        assert config["metadata"]["user_id"] == "user_123"
        assert config["metadata"]["session_id"] == "session_456"
        assert "production" in config["tags"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

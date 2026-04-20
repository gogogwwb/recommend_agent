"""
Unit tests for Short-Term Memory Management

Tests the SummarizationMiddleware factory and configuration.
"""
import pytest
from unittest.mock import patch

from memory.short_term_memory import (
    create_summarization_middleware,
    get_default_summarization_config,
    DEFAULT_MAX_TOKENS_BEFORE_SUMMARY,
    DEFAULT_MESSAGES_TO_KEEP,
    DEFAULT_SUMMARIZATION_MODEL,
    DEFAULT_TRIM_TOKENS_FOR_SUMMARIZATION,
)


# ==================== Constants Tests ====================

class TestConstants:
    """Tests for module constants"""
    
    def test_default_values(self):
        """Test default constant values"""
        assert DEFAULT_MAX_TOKENS_BEFORE_SUMMARY == 5000
        assert DEFAULT_MESSAGES_TO_KEEP == 20  # 10 turns
        assert DEFAULT_SUMMARIZATION_MODEL == "gpt-4o-mini"
        assert DEFAULT_TRIM_TOKENS_FOR_SUMMARIZATION == 4000


# ==================== Factory Function Tests ====================

class TestCreateSummarizationMiddleware:
    """Tests for create_summarization_middleware factory function"""
    
    def test_create_with_defaults(self):
        """Test middleware creation with default parameters"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            middleware = create_summarization_middleware()
            
            assert middleware is not None
            # Verify trigger is set correctly
            assert middleware.trigger == ("tokens", DEFAULT_MAX_TOKENS_BEFORE_SUMMARY)
            # Verify keep is set correctly
            assert middleware.keep == ("messages", DEFAULT_MESSAGES_TO_KEEP)
    
    def test_create_with_custom_params(self):
        """Test middleware creation with custom parameters"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            middleware = create_summarization_middleware(
                max_tokens_before_summary=3000,
                messages_to_keep=10,
                summarization_model="gpt-3.5-turbo"
            )
            
            assert middleware is not None
            assert middleware.trigger == ("tokens", 3000)
            assert middleware.keep == ("messages", 10)
    
    def test_create_with_multiple_triggers(self):
        """Test that middleware can be created (trigger is single value in our wrapper)"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            # Our wrapper only supports single trigger
            middleware = create_summarization_middleware(
                max_tokens_before_summary=5000
            )
            
            assert middleware is not None
            assert middleware.trigger == ("tokens", 5000)


# ==================== Configuration Tests ====================

class TestGetDefaultSummarizationConfig:
    """Tests for get_default_summarization_config function"""
    
    def test_get_config(self):
        """Test getting default configuration"""
        config = get_default_summarization_config()
        
        assert isinstance(config, dict)
        assert "max_tokens_before_summary" in config
        assert "messages_to_keep" in config
        assert "summarization_model" in config
        
        # Verify values match constants
        assert config["max_tokens_before_summary"] == DEFAULT_MAX_TOKENS_BEFORE_SUMMARY
        assert config["messages_to_keep"] == DEFAULT_MESSAGES_TO_KEEP
        assert config["summarization_model"] == DEFAULT_SUMMARIZATION_MODEL


# ==================== Integration Tests ====================

class TestSummarizationMiddlewareIntegration:
    """Integration tests verifying SummarizationMiddleware behavior"""
    
    def test_middleware_has_required_methods(self):
        """Test that middleware has all required methods from LangChain"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            middleware = create_summarization_middleware()
            
            # Verify middleware has the key methods from LangChain 1.x
            assert hasattr(middleware, 'before_model')
            assert hasattr(middleware, 'abefore_model')
            assert hasattr(middleware, 'token_counter')
            assert hasattr(middleware, '_should_summarize')
            assert hasattr(middleware, '_create_summary')
            assert hasattr(middleware, '_acreate_summary')
            assert hasattr(middleware, '_partition_messages')
    
    def test_middleware_uses_langchain_token_counter(self):
        """Test that middleware uses LangChain's built-in token counter"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            middleware = create_summarization_middleware()
            
            # Verify token_counter is set (LangChain's count_tokens_approximately)
            assert middleware.token_counter is not None
            assert callable(middleware.token_counter)


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_zero_tokens_threshold(self):
        """Test that zero tokens threshold raises error"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            # LangChain validates this internally
            with pytest.raises(ValueError):
                create_summarization_middleware(max_tokens_before_summary=0)
    
    def test_zero_messages_to_keep(self):
        """Test that zero messages to keep raises error"""
        with patch('memory.short_term_memory.ChatOpenAI'):
            # LangChain validates this internally
            with pytest.raises(ValueError):
                create_summarization_middleware(messages_to_keep=0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Memory system for the insurance recommendation agent.

This module provides memory management utilities and documentation.

Current Implementation:
- Short-Term Memory: SummarizationMiddleware for conversation compression
- Session Persistence: LangGraph PostgresSaver (see utils/checkpointer.py)
- Cross-Session Data: Store API for user profiles (see utils/store_manager.py)

Archived:
- HotDataLayer, WarmDataLayer, ContextFilter (see archived/memory/)
"""

from memory.short_term_memory import (
    create_summarization_middleware,
    get_default_summarization_config,
    DEFAULT_MAX_TOKENS_BEFORE_SUMMARY,
    DEFAULT_MESSAGES_TO_KEEP,
    DEFAULT_SUMMARIZATION_MODEL,
    DEFAULT_TRIM_TOKENS_FOR_SUMMARIZATION,
)

__all__ = [
    # Factory function
    "create_summarization_middleware",
    
    # Convenience functions
    "get_default_summarization_config",
    
    # Constants
    "DEFAULT_MAX_TOKENS_BEFORE_SUMMARY",
    "DEFAULT_MESSAGES_TO_KEEP",
    "DEFAULT_SUMMARIZATION_MODEL",
    "DEFAULT_TRIM_TOKENS_FOR_SUMMARIZATION",
]

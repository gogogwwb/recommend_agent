"""
Short-Term Memory Management with SummarizationMiddleware

This module provides a thin wrapper around LangChain 1.x's SummarizationMiddleware
for conversation compression when token limits are approached.

Key Features:
- Automatic conversation summarization when exceeding 5000 tokens
- Preserve recent 10 turns of conversation messages (20 messages)
- Integration with existing PostgresSaver checkpointer
- Use small model (gpt-4o-mini) for compression to reduce costs
- Maintain AI/Tool message pair integrity

Architecture:
- SummarizationMiddleware: Handles all token counting, compression, and summarization
- PostgresSaver: Persists session state (messages, checkpoints)
- This module: Simple factory and configuration wrapper

Requirements: Short-term memory persistence with automatic compression

Note: LangChain 1.x SummarizationMiddleware already provides:
- Token counting (count_tokens_approximately)
- Compression trigger logic (_should_summarize)
- Message compression (_partition_messages, _build_new_messages)
- Summary generation (_create_summary, _acreate_summary)

We do NOT need to reimplement these - just configure and use the middleware.
"""
import logging
from typing import Optional

from langchain.agents.middleware import SummarizationMiddleware
from langchain_openai import ChatOpenAI

from config import get_settings

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Token threshold for triggering summarization
DEFAULT_MAX_TOKENS_BEFORE_SUMMARY = 5000

# Number of recent messages to keep verbatim (10 turns = 20 messages)
DEFAULT_MESSAGES_TO_KEEP = 20

# Small model for summarization (cost-effective)
DEFAULT_SUMMARIZATION_MODEL = "gpt-4o-mini"

# Maximum tokens for summarization prompt
DEFAULT_TRIM_TOKENS_FOR_SUMMARIZATION = 4000


# ==================== Summarization Middleware Factory ====================

def create_summarization_middleware(
    max_tokens_before_summary: int = DEFAULT_MAX_TOKENS_BEFORE_SUMMARY,
    messages_to_keep: int = DEFAULT_MESSAGES_TO_KEEP,
    summarization_model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> SummarizationMiddleware:
    """
    Create a SummarizationMiddleware instance for conversation compression.
    
    LangChain 1.x SummarizationMiddleware provides:
    - Automatic token counting using count_tokens_approximately
    - Compression trigger logic based on token/message thresholds
    - Message partitioning that preserves AI/Tool message pairs
    - Summary generation using the configured model
    
    Args:
        max_tokens_before_summary: Token threshold to trigger summarization (default: 5000)
        messages_to_keep: Number of recent messages to preserve (default: 20 = 10 turns)
        summarization_model: Model for summarization (default: gpt-4o-mini)
        api_key: OpenAI API key (default: from config)
        api_base: OpenAI API base URL (default: from config)
        
    Returns:
        Configured SummarizationMiddleware instance
        
    Example:
        # Create middleware
        middleware = create_summarization_middleware(
            max_tokens_before_summary=5000,
            messages_to_keep=20
        )
        
        # Use with LangChain agent
        from langchain.agents import create_agent
        agent = create_agent(
            model="gpt-4",
            tools=[...],
            middleware=[middleware],
            checkpointer=checkpointer
        )
        
        # The middleware will automatically:
        # 1. Count tokens in messages
        # 2. Trigger summarization when > 5000 tokens
        # 3. Keep last 20 messages verbatim
        # 4. Summarize older messages using gpt-4o-mini
        # 5. Preserve AI/Tool message pair integrity
    """
    settings = get_settings()
    
    # Use provided values or defaults from config
    model_name = summarization_model or DEFAULT_SUMMARIZATION_MODEL
    api_key = api_key or settings.OPENAI_API_KEY
    api_base = api_base or settings.OPENAI_API_BASE
    
    logger.info(
        f"Creating SummarizationMiddleware: "
        f"trigger=(tokens, {max_tokens_before_summary}), "
        f"keep=(messages, {messages_to_keep}), "
        f"model={model_name}"
    )
    
    # Create the summarization LLM (small model for cost efficiency)
    summarization_llm = ChatOpenAI(
        model=model_name,
        temperature=0.3,  # Lower temperature for consistent summaries
        api_key=api_key,
        base_url=api_base,
    )
    
    # Create SummarizationMiddleware using LangChain 1.x API
    # The middleware handles:
    # - Token counting: count_tokens_approximately
    # - Trigger logic: _should_summarize
    # - Message partitioning: _partition_messages
    # - Summary generation: _create_summary / _acreate_summary
    middleware = SummarizationMiddleware(
        model=summarization_llm,
        trigger=("tokens", max_tokens_before_summary),
        keep=("messages", messages_to_keep),
    )
    
    logger.info("SummarizationMiddleware created successfully")
    
    return middleware


# ==================== Convenience Functions ====================

def get_default_summarization_config() -> dict:
    """
    Get default summarization configuration from settings.
    
    Returns:
        Dict with default configuration values
    """
    settings = get_settings()
    
    return {
        "max_tokens_before_summary": settings.MAX_TOKENS_BEFORE_SUMMARY,
        "messages_to_keep": settings.MESSAGES_TO_KEEP,
        "summarization_model": settings.SUMMARIZATION_MODEL,
    }


# ==================== Module Exports ====================

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

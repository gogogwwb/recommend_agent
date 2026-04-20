"""
Short-Term Memory Integration Example

This example demonstrates how to use LangChain 1.x's SummarizationMiddleware
for automatic conversation compression.

Key Points:
- SummarizationMiddleware handles ALL token counting, compression, and summarization
- We only need to configure it with trigger threshold and keep count
- No need to implement custom token counting or compression logic

Usage:
    python examples/short_term_memory_example.py
"""
import asyncio
from langchain_core.messages import HumanMessage, AIMessage

from memory.short_term_memory import (
    create_summarization_middleware,
    get_default_summarization_config,
)
from config import get_settings


def example_middleware_creation():
    """Example: Create SummarizationMiddleware with default settings"""
    print("=" * 60)
    print("Example 1: Create SummarizationMiddleware")
    print("=" * 60)
    
    settings = get_settings()
    
    # Note: This requires OPENAI_API_KEY to be set
    if not settings.OPENAI_API_KEY:
        print("Skipping: OPENAI_API_KEY not set")
        print("To run this example, set OPENAI_API_KEY in .env file")
        return
    
    # Create middleware - LangChain handles everything:
    # - Token counting: count_tokens_approximately
    # - Trigger logic: _should_summarize
    # - Message partitioning: _partition_messages
    # - Summary generation: _create_summary / _acreate_summary
    middleware = create_summarization_middleware(
        max_tokens_before_summary=5000,
        messages_to_keep=20,  # 10 turns
        summarization_model="gpt-4o-mini"
    )
    
    print("SummarizationMiddleware created successfully!")
    print(f"Configuration:")
    print(f"  - Trigger: {middleware.trigger}")
    print(f"  - Keep: {middleware.keep}")
    print(f"  - Model: {middleware.model}")
    
    # The middleware has all required methods from LangChain 1.x
    print(f"\nMiddleware methods (from LangChain 1.x):")
    print(f"  - before_model: {hasattr(middleware, 'before_model')}")
    print(f"  - abefore_model: {hasattr(middleware, 'abefore_model')}")
    print(f"  - token_counter: {hasattr(middleware, 'token_counter')}")
    print(f"  - _should_summarize: {hasattr(middleware, '_should_summarize')}")
    print(f"  - _create_summary: {hasattr(middleware, '_create_summary')}")


def example_custom_configuration():
    """Example: Create middleware with custom configuration"""
    print("\n" + "=" * 60)
    print("Example 2: Custom Configuration")
    print("=" * 60)
    
    settings = get_settings()
    
    if not settings.OPENAI_API_KEY:
        print("Skipping: OPENAI_API_KEY not set")
        return
    
    # Custom configuration for different use cases
    
    # Case 1: Aggressive compression (lower threshold)
    print("\nCase 1: Aggressive compression")
    middleware_aggressive = create_summarization_middleware(
        max_tokens_before_summary=3000,
        messages_to_keep=10,
    )
    print(f"  Trigger: {middleware_aggressive.trigger}")
    print(f"  Keep: {middleware_aggressive.keep}")
    
    # Case 2: Conservative compression (higher threshold)
    print("\nCase 2: Conservative compression")
    middleware_conservative = create_summarization_middleware(
        max_tokens_before_summary=8000,
        messages_to_keep=30,
    )
    print(f"  Trigger: {middleware_conservative.trigger}")
    print(f"  Keep: {middleware_conservative.keep}")


def example_get_default_config():
    """Example: Get default configuration from settings"""
    print("\n" + "=" * 60)
    print("Example 3: Get Default Configuration")
    print("=" * 60)
    
    config = get_default_summarization_config()
    
    print("Default configuration from config.py:")
    for key, value in config.items():
        print(f"  - {key}: {value}")


def example_integration_with_agent():
    """Example: How to integrate with LangChain agent"""
    print("\n" + "=" * 60)
    print("Example 4: Integration with LangChain Agent")
    print("=" * 60)
    
    print("""
# How to use with LangChain agent:

from langchain.agents import create_agent
from memory.short_term_memory import create_summarization_middleware

# Create middleware
middleware = create_summarization_middleware(
    max_tokens_before_summary=5000,
    messages_to_keep=20
)

# Create agent with middleware
agent = create_agent(
    model="gpt-4",
    tools=[...],
    middleware=[middleware],
    checkpointer=checkpointer
)

# The middleware will automatically:
# 1. Count tokens using LangChain's count_tokens_approximately
# 2. Trigger summarization when > 5000 tokens
# 3. Keep last 20 messages verbatim
# 4. Summarize older messages using gpt-4o-mini
# 5. Preserve AI/Tool message pair integrity
# 6. Persist state via checkpointer
""")


def example_langchain_features():
    """Example: LangChain 1.x SummarizationMiddleware features"""
    print("\n" + "=" * 60)
    print("Example 5: LangChain 1.x SummarizationMiddleware Features")
    print("=" * 60)
    
    print("""
LangChain 1.x SummarizationMiddleware provides:

1. Token Counting (count_tokens_approximately):
   - Automatically counts tokens in messages
   - Uses model-specific scaling (e.g., 3.3 chars/token for Claude)
   - Uses usage_metadata from last AI message when available

2. Trigger Logic (_should_summarize):
   - Supports multiple trigger types:
     - ("tokens", 5000): Trigger at 5000 tokens
     - ("messages", 50): Trigger at 50 messages
     - ("fraction", 0.8): Trigger at 80% of model's max tokens
   - Can combine multiple triggers

3. Message Partitioning (_partition_messages):
   - Keeps recent messages verbatim
   - Preserves AI/Tool message pair integrity
   - Uses binary search for efficient token-based cutoff

4. Summary Generation (_create_summary / _acreate_summary):
   - Uses configured model (default: gpt-4o-mini)
   - Structured summary with sections:
     - SESSION INTENT
     - SUMMARY
     - ARTIFACTS
     - NEXT STEPS
   - Trims messages if too long for summarization

5. Integration with LangGraph:
   - Works with checkpointer for state persistence
   - Uses RemoveMessage for efficient state updates
   - Supports both sync and async operations
""")


def main():
    """Run all examples"""
    example_middleware_creation()
    example_custom_configuration()
    example_get_default_config()
    example_integration_with_agent()
    example_langchain_features()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

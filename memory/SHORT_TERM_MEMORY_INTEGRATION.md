# Short-Term Memory Integration Guide

## Overview

This document explains how to use LangChain 1.x's SummarizationMiddleware for automatic conversation compression.

**Key Point**: LangChain 1.x SummarizationMiddleware provides ALL the core functionality. We only need to configure it.

## What LangChain 1.x Provides

### Built-in Features

| Feature | Method | Description |
|---------|--------|-------------|
| Token Counting | `count_tokens_approximately` | Model-specific token estimation (e.g., 3.3 chars/token for Claude) |
| Trigger Logic | `_should_summarize` | Automatic detection when threshold exceeded |
| Message Partitioning | `_partition_messages` | Keeps recent messages, preserves AI/Tool pairs |
| Summary Generation | `_create_summary` | Structured summaries with SESSION INTENT, SUMMARY, ARTIFACTS, NEXT STEPS |
| Async Support | `_acreate_summary` | Async version of summary generation |
| State Updates | `before_model` / `abefore_model` | Uses RemoveMessage for efficient state updates |

### What We Do NOT Need to Implement

- ❌ Custom token counting - LangChain has `count_tokens_approximately`
- ❌ Custom compression trigger logic - LangChain has `_should_summarize`
- ❌ Custom message compression - LangChain has `_partition_messages`
- ❌ Custom summary generation - LangChain has `_create_summary`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Graph                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SummarizationMiddleware (LangChain 1.x built-in)    │   │
│  │                                                       │   │
│  │  Token Counting: count_tokens_approximately           │   │
│  │  Trigger Logic: _should_summarize                     │   │
│  │  Message Partitioning: _partition_messages            │   │
│  │  Summary Generation: _create_summary                  │   │
│  │                                                       │   │
│  │  Configuration:                                       │   │
│  │  - trigger: ("tokens", 5000)                          │   │
│  │  - keep: ("messages", 20)                             │   │
│  │  - model: gpt-4o-mini                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  PostgresSaver Checkpointer                           │   │
│  │  - Persists session state                             │   │
│  │  - Enables session recovery                           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Integration Steps

### Step 1: Create SummarizationMiddleware

```python
from memory.short_term_memory import create_summarization_middleware

# LangChain handles everything - we just configure it
middleware = create_summarization_middleware(
    max_tokens_before_summary=5000,
    messages_to_keep=20,  # 10 turns
    summarization_model="gpt-4o-mini"
)
```

### Step 2: Use with LangChain Agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-4",
    tools=[...],
    middleware=[middleware],
    checkpointer=checkpointer
)
```

### Step 3: That's It!

The middleware will automatically:
1. Count tokens using `count_tokens_approximately`
2. Trigger summarization when > 5000 tokens
3. Keep last 20 messages verbatim
4. Summarize older messages using gpt-4o-mini
5. Preserve AI/Tool message pair integrity
6. Persist state via checkpointer

## Configuration

Add to `config.py`:

```python
# Short-term memory settings
MAX_TOKENS_BEFORE_SUMMARY: int = 5000
MESSAGES_TO_KEEP: int = 20  # 10 turns = 20 messages
SUMMARIZATION_MODEL: str = "gpt-4o-mini"
MAX_TOKENS_FOR_SUMMARIZATION: int = 1000
```

## Trigger Types

LangChain 1.x supports multiple trigger types:

```python
# Token-based trigger
trigger=("tokens", 5000)

# Message-based trigger
trigger=("messages", 50)

# Fraction of model's max tokens
trigger=("fraction", 0.8)

# Multiple triggers (any one triggers summarization)
trigger=[("tokens", 5000), ("messages", 50)]
```

## Summary Structure

LangChain 1.x generates structured summaries:

```
## SESSION INTENT
What is the user's primary goal or request?

## SUMMARY
Important context, choices, conclusions, strategies.

## ARTIFACTS
Files created, modified, or accessed.

## NEXT STEPS
Tasks remaining to be completed.
```

## Performance Considerations

### Token Savings

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| 30 messages (15 turns) | ~6000 tokens | ~1500 tokens | 75% |
| 50 messages (25 turns) | ~10000 tokens | ~2000 tokens | 80% |
| 100 messages (50 turns) | ~20000 tokens | ~2500 tokens | 87.5% |

### Cost Impact

- Summarization uses gpt-4o-mini (~$0.15/1M tokens)
- Typical summarization: ~2000 input tokens + ~200 output tokens
- Cost per summarization: ~$0.0003

## Testing

Run the test suite:

```bash
pytest tests/unit/test_short_term_memory.py -v
```

Run the example:

```bash
python examples/short_term_memory_example.py
```

## Key Takeaways

1. **Don't reinvent the wheel** - LangChain 1.x SummarizationMiddleware provides everything
2. **Just configure it** - Set trigger threshold and keep count
3. **Trust the middleware** - It handles token counting, compression, and summarization
4. **Integrate with checkpointer** - For full session persistence

## References

- [LangChain Agent Middleware Blog](https://blog.langchain.com/agent-middleware/)
- [SummarizationMiddleware Source Code](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/middleware/summarization.py)

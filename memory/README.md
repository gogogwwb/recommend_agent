# Memory Management

## Current Implementation

The project uses a **two-layer memory architecture**:

1. **Short-Term Memory**: LangChain 1.x SummarizationMiddleware for conversation compression
2. **Session Persistence**: LangGraph's PostgresSaver for state persistence and recovery

### Architecture

```
User Message → Main Graph
                    ↓
         SummarizationMiddleware (LangChain 1.x built-in)
         - Token counting: count_tokens_approximately
         - Trigger logic: _should_summarize
         - Message partitioning: _partition_messages
         - Summary generation: _create_summary
                    ↓ (if > 5000 tokens)
         Compress old messages → Summary + Recent 20 messages
                    ↓
         PostgresSaver persists session state
                    ↓
         State recovered via thread_id on next request
```

### Key Features

#### Short-Term Memory (SummarizationMiddleware)

LangChain 1.x SummarizationMiddleware provides **all** of the following out-of-the-box:

- **Token Counting**: `count_tokens_approximately` - model-specific token estimation
- **Trigger Logic**: `_should_summarize` - automatic detection when threshold exceeded
- **Message Partitioning**: `_partition_messages` - keeps recent messages, preserves AI/Tool pairs
- **Summary Generation**: `_create_summary` / `_acreate_summary` - structured summaries

Configuration:
- **Trigger**: 5000 tokens (configurable)
- **Keep**: 20 messages = 10 turns (configurable)
- **Model**: gpt-4o-mini for cost-effective summarization

#### Session Persistence (PostgresSaver)
- **Session Persistence**: All conversation state is automatically persisted to PostgreSQL
- **Session Recovery**: State can be recovered using `thread_id` for multi-turn conversations
- **Time-Travel Debugging**: Supports checkpoint-based debugging and state rollback
- **Concurrent Sessions**: Thread-safe session management with isolation

### Implementation

#### Short-Term Memory (SummarizationMiddleware)

The short-term memory is a thin wrapper around LangChain 1.x's SummarizationMiddleware.
All core functionality is provided by LangChain - we only configure it.

```python
from memory.short_term_memory import create_summarization_middleware

# Create middleware - LangChain handles everything
middleware = create_summarization_middleware(
    max_tokens_before_summary=5000,
    messages_to_keep=20  # 10 turns
)

# Use with LangChain agent
from langchain.agents import create_agent
agent = create_agent(
    model="gpt-4",
    tools=[...],
    middleware=[middleware],
    checkpointer=checkpointer
)
```

**What LangChain 1.x SummarizationMiddleware provides:**

| Feature | Method | Description |
|---------|--------|-------------|
| Token Counting | `count_tokens_approximately` | Model-specific token estimation |
| Trigger Logic | `_should_summarize` | Detects when threshold exceeded |
| Message Partitioning | `_partition_messages` | Keeps recent messages, preserves AI/Tool pairs |
| Summary Generation | `_create_summary` | Structured summaries with SESSION INTENT, SUMMARY, ARTIFACTS, NEXT STEPS |
| Async Support | `_acreate_summary` | Async version of summary generation |

**We do NOT need to implement:**
- ❌ Custom token counting
- ❌ Custom compression trigger logic
- ❌ Custom message compression
- ❌ Custom summary generation

All of these are built into LangChain 1.x SummarizationMiddleware!

#### Session Persistence (PostgresSaver)

The session persistence is implemented in `utils/checkpointer.py`:

```python
from langgraph.checkpoint.postgres import PostgresSaver

# Get checkpointer
checkpointer = get_checkpointer()

# Use with LangGraph compilation
app = graph.compile(checkpointer=checkpointer)

# Invoke with thread_id for session management
config = {"configurable": {"thread_id": "session-123"}}
result = await app.ainvoke(input_state, config)

# Recover session state
state = await app.aget_state(config)
```

### Database Tables

PostgresSaver automatically creates the following tables:
- `checkpoint_writes`
- `checkpoints`
- `checkpoints_blobs`
- `checkpoints_writes`

## Architecture Decision

### Why PostgresSaver instead of Custom Memory Layers?

The project initially designed a three-layer memory architecture (Hot/Warm/Cold), but switched to PostgresSaver for the following reasons:

1. **Native LangGraph Integration**: No custom code needed, fully compatible with LangGraph's state management
2. **Built-in Features**: Automatic message persistence, session recovery, and time-travel debugging
3. **Simplified Architecture**: Avoids hand-written compression logic and maintains conversation coherence
4. **Production Ready**: Battle-tested solution with proper error handling and concurrency support

### Archived Implementation

The original three-layer memory implementation has been moved to `archived/memory/` for reference:
- `hot_data_layer.py` - Redis-based recent conversation storage
- `warm_data_layer.py` - PostgreSQL-based compressed history storage
- `context_filter.py` - Agent-specific context filtering

These implementations are no longer used in production but preserved for:
- Historical reference of architecture evolution
- Potential future use cases
- Educational purposes

## Related Documentation

- [State Partitioning Design](./STATE_PARTITIONING.md) - LangGraph State schema design
- [LangGraph Alternatives Analysis](./LANGGRAPH_ALTERNATIVES_ANALYSIS.md) - Framework comparison
- [Refactored Architecture](./REFACTORED_ARCHITECTURE.md) - Architecture evolution

## Usage Examples

### Basic Session Management with Summarization

```python
from agents.main_graph import create_main_graph_with_checkpointer
from memory.short_term_memory import create_summarization_middleware

# Create summarization middleware
# LangChain handles all token counting, compression, and summarization
middleware = create_summarization_middleware(
    max_tokens_before_summary=5000,
    messages_to_keep=20
)

# Create graph with checkpointer
graph = create_main_graph_with_checkpointer()

# Process user message with session persistence
result = await process_user_message(
    session_id="user-session-123",
    user_id="user-456",
    user_message="我想了解重疾险",
    checkpointer=checkpointer,
)
```

### Integration with LangChain Agent

```python
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

# The middleware automatically:
# 1. Counts tokens using count_tokens_approximately
# 2. Triggers summarization when > 5000 tokens
# 3. Keeps last 20 messages verbatim
# 4. Summarizes older messages using gpt-4o-mini
# 5. Preserves AI/Tool message pair integrity
```

### Session Recovery

```python
# Recover previous session state
config = {"configurable": {"thread_id": "user-session-123"}}
state = await graph.aget_state(config)

# Continue conversation
result = await graph.ainvoke(new_message, config)
```

### Time-Travel Debugging

```python
# Get all checkpoints
checkpoints = await graph.aget_state_history(config)

# Rollback to specific checkpoint
await graph.aupdate_state(config, checkpoint_id)
```

## Configuration

Memory management is configured through environment variables:

```bash
# PostgreSQL connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=insurance_db

# Short-term memory settings (in config.py)
TOKEN_BUDGET_PER_SESSION=6000  # Max tokens per session
MAX_CONVERSATION_TURNS=15      # Max conversation turns
```

### Short-Term Memory Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_tokens_before_summary` | 5000 | Token threshold to trigger summarization |
| `messages_to_keep` | 10 | Number of recent messages to preserve |
| `summarization_model` | gpt-4o-mini | Model for generating summaries |
| `max_tokens_for_summarization` | 1000 | Max tokens for summary output |

## Performance Considerations

- **Latency**: < 100ms for state persistence and recovery
- **Storage**: Automatic cleanup of old checkpoints (configurable retention)
- **Concurrency**: Thread-safe with connection pooling
- **Scalability**: Supports horizontal scaling with shared PostgreSQL instance

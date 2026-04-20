# Archived Memory Implementation

## Status: DEPRECATED

This directory contains the original three-layer memory implementation that has been **replaced by LangGraph's PostgresSaver**.

## Why Archived?

The project initially implemented a custom three-layer memory architecture:
- **Hot Layer (Redis)**: Recent 5 turns of conversation
- **Warm Layer (PostgreSQL)**: Compressed historical conversations
- **Cold Layer (FAISS + PostgreSQL)**: Archived sessions

However, this was replaced with **PostgresSaver** for the following reasons:

1. **Native LangGraph Integration**: PostgresSaver is built into LangGraph, requiring no custom code
2. **Simplified Architecture**: Avoids hand-written compression logic
3. **Better Features**: Built-in time-travel debugging and session recovery
4. **Production Ready**: Battle-tested with proper error handling

## Files in This Directory

### Implementation Files

- **`hot_data_layer.py`**: Redis-based storage for recent conversations (max 5 turns)
  - Fast access (< 10ms)
  - Automatic TTL (1 hour)
  - Message demotion to warm layer

- **`warm_data_layer.py`**: PostgreSQL-based compressed history storage
  - Token-based compression (3000 tokens threshold)
  - Asynchronous compression
  - Critical slot preservation

- **`context_filter.py`**: Agent-specific context filtering
  - Visibility rules per agent
  - Intent-based filtering
  - Token reduction (up to 40%)

### Example Files

- **`hot_data_layer_example.py`**: Usage example for HotDataLayer
- **`warm_data_layer_example.py`**: Usage example for WarmDataLayer
- **`context_isolation_example.py`**: Usage example for context filtering

### Test Files

- **`test_hot_data_layer.py`**: Unit tests for HotDataLayer (20 tests)
- **`test_warm_data_layer.py`**: Unit tests for WarmDataLayer (20 tests)

### Documentation

- **`README.md`**: Original three-layer architecture documentation
- **`CONTEXT_ISOLATION.md`**: Context isolation design document

## Current Implementation

The current memory management uses **PostgresSaver** from LangGraph. See `memory/README.md` in the project root for details.

## When to Reference This Code

This archived implementation may be useful for:

1. **Learning Purposes**: Understanding custom memory layer design
2. **Alternative Approaches**: When PostgresSaver doesn't meet specific requirements
3. **Migration Reference**: If needing to implement similar functionality
4. **Research**: Comparing different memory management strategies

## Key Differences from Current Implementation

| Feature | Archived (Hot/Warm) | Current (PostgresSaver) |
|---------|---------------------|-------------------------|
| **Integration** | Custom code | Native LangGraph |
| **Compression** | Manual (LLM-based) | Automatic |
| **Debugging** | Limited | Time-travel support |
| **Maintenance** | High | Low |
| **Code Complexity** | ~1000 lines | ~200 lines |

## Migration Notes

If you need to migrate back to the custom implementation:

1. Restore files to their original locations:
   - `hot_data_layer.py` → `memory/`
   - `warm_data_layer.py` → `memory/`
   - `context_filter.py` → `memory/`

2. Update imports in agents:
   ```python
   from memory.hot_data_layer import HotDataLayer
   from memory.warm_data_layer import WarmDataLayer
   ```

3. Remove PostgresSaver from graph compilation

4. Restore test files to `tests/unit/`

## Date Archived

April 20, 2026

## Reason for Archiving

Simplified architecture using LangGraph's native PostgresSaver, which provides all required functionality with less code and better integration.

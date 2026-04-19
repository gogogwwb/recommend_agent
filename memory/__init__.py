"""
Memory system for the insurance recommendation agent.

This module implements a three-layer memory architecture:
- Hot Data Layer (Redis): Recent 5 turns of conversation
- Warm Data Layer (PostgreSQL): Compressed historical conversations
- Cold Data Layer (FAISS + PostgreSQL): Archived sessions and user profiles
"""

from memory.hot_data_layer import HotDataLayer

__all__ = ["HotDataLayer"]

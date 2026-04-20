"""
Hot Data Layer - Redis-based storage for recent conversation data

This module implements the hot data layer of the three-layer memory architecture.
It stores the most recent 5 turns of conversation in Redis for fast access.

Key features:
- Stores recent 5 turns (10 messages) in Redis
- Automatic demotion to warm layer when exceeding 5 turns
- Fast read/write operations (<10ms)
- Automatic expiration after 1 hour of inactivity
- Slot management for user profile fields
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from models.conversation import Message
from utils.redis_client import RedisClient, RedisKeyNamespace

logger = logging.getLogger(__name__)


class HotDataLayer:
    """
    Hot Data Layer - Redis storage for recent 5 turns of conversation
    
    This layer provides fast access to the most recent conversation data,
    including messages, slots, and temporary context.
    
    Attributes:
        redis_client: Redis client instance
        session_id: Current session ID
        max_hot_turns: Maximum number of turns to keep in hot layer (default: 5)
        ttl_seconds: Time-to-live for hot data in seconds (default: 3600 = 1 hour)
    """
    
    def __init__(
        self,
        redis_client: RedisClient,
        session_id: str,
        max_hot_turns: int = 5,
        ttl_seconds: int = 3600
    ):
        """
        Initialize Hot Data Layer
        
        Args:
            redis_client: Redis client instance
            session_id: Session ID for this hot data layer
            max_hot_turns: Maximum number of turns to keep (default: 5)
            ttl_seconds: Time-to-live in seconds (default: 3600 = 1 hour)
        """
        self.redis_client = redis_client
        self.session_id = session_id
        self.max_hot_turns = max_hot_turns
        self.ttl_seconds = ttl_seconds
        
        # Key prefixes for this session
        self.key_prefix = f"hot:{session_id}"
        self.messages_key = RedisKeyNamespace.hot_messages(session_id)
        self.slots_key = RedisKeyNamespace.hot_slots(session_id)
        self.metadata_key = RedisKeyNamespace.hot_metadata(session_id)
        
        logger.debug(
            f"Initialized HotDataLayer for session {session_id}, "
            f"max_turns={max_hot_turns}, ttl={ttl_seconds}s"
        )
    
    async def add_message(self, message: Message, warm_layer=None) -> None:
        """
        Add a message to the hot data layer
        
        When the number of messages exceeds max_hot_turns * 2 (5 turns = 10 messages),
        the oldest messages are automatically demoted to the warm data layer.
        
        Args:
            message: Message object to add
            warm_layer: Optional WarmDataLayer instance for demotion
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            # 1. Serialize message to JSON
            message_json = message.model_dump_json()
            
            # 2. Add message to Redis list (right push - newest at the end)
            self.redis_client.client.rpush(self.messages_key, message_json)
            
            # 3. Check if we need to demote old messages
            message_count = self.redis_client.client.llen(self.messages_key)
            max_messages = self.max_hot_turns * 2  # 5 turns = 10 messages
            
            if message_count > max_messages:
                # Demote excess messages to warm layer
                await self._demote_to_warm(message_count, max_messages, warm_layer)
            
            # 4. Set/refresh expiration time
            self.redis_client.client.expire(self.messages_key, self.ttl_seconds)
            
            # 5. Update metadata
            await self._update_metadata()
            
            logger.debug(
                f"Added message to hot layer: session={self.session_id}, "
                f"role={message.role}, count={message_count}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to add message to hot layer: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def _demote_to_warm(
        self,
        current_count: int,
        max_messages: int,
        warm_layer=None
    ) -> None:
        """
        Demote excess messages from hot to warm layer
        
        Args:
            current_count: Current number of messages in hot layer
            max_messages: Maximum allowed messages
            warm_layer: Optional WarmDataLayer instance
        """
        try:
            # Calculate how many messages to demote
            excess_count = current_count - max_messages
            
            if excess_count <= 0:
                return
            
            # Get the oldest messages (from the left/start of the list)
            messages_to_demote_json = self.redis_client.client.lrange(
                self.messages_key,
                0,
                excess_count - 1
            )
            
            # If warm layer is provided, send messages to it
            if warm_layer is not None:
                for msg_json in messages_to_demote_json:
                    message = Message.model_validate_json(msg_json)
                    await warm_layer.append_message(message)
                
                logger.info(
                    f"Demoted {excess_count} messages from hot to warm layer: "
                    f"session={self.session_id}"
                )
            else:
                logger.warning(
                    f"No warm layer provided, {excess_count} messages will be lost: "
                    f"session={self.session_id}"
                )
            
            # Remove demoted messages from hot layer (keep only the recent ones)
            self.redis_client.client.ltrim(self.messages_key, excess_count, -1)
            
        except Exception as e:
            logger.error(
                f"Failed to demote messages to warm layer: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def get_hot_messages(self) -> List[Message]:
        """
        Get all messages from the hot data layer
        
        Returns:
            List of Message objects (most recent 5 turns)
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            # Get all messages from Redis list
            messages_json = self.redis_client.client.lrange(self.messages_key, 0, -1)
            
            # Parse JSON strings to Message objects
            messages = [
                Message.model_validate_json(msg_json)
                for msg_json in messages_json
            ]
            
            logger.debug(
                f"Retrieved {len(messages)} messages from hot layer: "
                f"session={self.session_id}"
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                f"Failed to get hot messages: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def update_slots(self, slots: Dict[str, Any]) -> None:
        """
        Update slot values in the hot data layer
        
        Slots are structured information extracted from user messages
        (e.g., age, occupation, income_range).
        
        Args:
            slots: Dictionary of slot key-value pairs
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            if not slots:
                logger.debug(f"No slots to update: session={self.session_id}")
                return
            
            # Get existing slots
            existing_slots_json = self.redis_client.client.get(self.slots_key)
            if existing_slots_json:
                existing_slots = json.loads(existing_slots_json)
            else:
                existing_slots = {}
            
            # Merge new slots with existing ones
            existing_slots.update(slots)
            
            # Save updated slots
            slots_json = json.dumps(existing_slots)
            self.redis_client.client.setex(
                self.slots_key,
                self.ttl_seconds,
                slots_json
            )
            
            logger.debug(
                f"Updated slots in hot layer: session={self.session_id}, "
                f"slots={list(slots.keys())}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to update slots: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def get_slots(self) -> Dict[str, Any]:
        """
        Get all slot values from the hot data layer
        
        Returns:
            Dictionary of slot key-value pairs
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            slots_json = self.redis_client.client.get(self.slots_key)
            
            if slots_json:
                slots = json.loads(slots_json)
                logger.debug(
                    f"Retrieved slots from hot layer: session={self.session_id}, "
                    f"count={len(slots)}"
                )
                return slots
            else:
                logger.debug(f"No slots found: session={self.session_id}")
                return {}
            
        except Exception as e:
            logger.error(
                f"Failed to get slots: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def get_hot_context(self) -> Dict[str, Any]:
        """
        Get complete hot data context for the session
        
        This includes messages, slots, and metadata.
        
        Returns:
            Dictionary containing:
                - hot_messages: List of recent messages
                - slots: Dictionary of slot values
                - metadata: Session metadata (turn_count, last_activity, etc.)
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            # Get all hot data components
            hot_messages = await self.get_hot_messages()
            slots = await self.get_slots()
            metadata = await self._get_metadata()
            
            context = {
                "hot_messages": hot_messages,
                "slots": slots,
                "metadata": metadata,
                "session_id": self.session_id,
            }
            
            logger.debug(
                f"Retrieved hot context: session={self.session_id}, "
                f"messages={len(hot_messages)}, slots={len(slots)}"
            )
            
            return context
            
        except Exception as e:
            logger.error(
                f"Failed to get hot context: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def _update_metadata(self) -> None:
        """
        Update session metadata in hot layer
        
        Metadata includes:
        - turn_count: Number of conversation turns
        - last_activity: Timestamp of last activity
        - message_count: Total number of messages in hot layer
        """
        try:
            # Get current metadata
            metadata_json = self.redis_client.client.get(self.metadata_key)
            if metadata_json:
                metadata = json.loads(metadata_json)
            else:
                metadata = {
                    "turn_count": 0,
                    "created_at": datetime.now().isoformat(),
                }
            
            # Update metadata
            message_count = self.redis_client.client.llen(self.messages_key)
            metadata.update({
                "last_activity": datetime.now().isoformat(),
                "message_count": message_count,
                "turn_count": message_count // 2,  # 2 messages per turn
            })
            
            # Save metadata
            metadata_json = json.dumps(metadata)
            self.redis_client.client.setex(
                self.metadata_key,
                self.ttl_seconds,
                metadata_json
            )
            
        except Exception as e:
            logger.error(
                f"Failed to update metadata: session={self.session_id}, "
                f"error={str(e)}"
            )
            # Don't raise - metadata update failure shouldn't break the flow
    
    async def _get_metadata(self) -> Dict[str, Any]:
        """
        Get session metadata from hot layer
        
        Returns:
            Dictionary containing session metadata
        """
        try:
            metadata_json = self.redis_client.client.get(self.metadata_key)
            
            if metadata_json:
                return json.loads(metadata_json)
            else:
                return {
                    "turn_count": 0,
                    "message_count": 0,
                    "created_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat(),
                }
            
        except Exception as e:
            logger.error(
                f"Failed to get metadata: session={self.session_id}, "
                f"error={str(e)}"
            )
            return {}
    
    async def clear(self) -> None:
        """
        Clear all hot data for the session
        
        This should be called when:
        - Session ends normally
        - Session is archived
        - Session needs to be reset
        
        Raises:
            Exception: If Redis operation fails
        """
        try:
            # Get all hot data keys for this session
            keys = RedisKeyNamespace.get_all_hot_keys(self.session_id)
            
            # Delete all keys
            if keys:
                deleted_count = self.redis_client.client.delete(*keys)
                logger.info(
                    f"Cleared hot data: session={self.session_id}, "
                    f"keys_deleted={deleted_count}"
                )
            else:
                logger.debug(f"No hot data to clear: session={self.session_id}")
            
        except Exception as e:
            logger.error(
                f"Failed to clear hot data: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def get_message_count(self) -> int:
        """
        Get the number of messages in hot layer
        
        Returns:
            Number of messages currently stored
        """
        try:
            count = self.redis_client.client.llen(self.messages_key)
            return count
        except Exception as e:
            logger.error(
                f"Failed to get message count: session={self.session_id}, "
                f"error={str(e)}"
            )
            return 0
    
    async def get_turn_count(self) -> int:
        """
        Get the number of conversation turns in hot layer
        
        Returns:
            Number of turns (message_count / 2)
        """
        message_count = await self.get_message_count()
        return message_count // 2
    
    async def is_empty(self) -> bool:
        """
        Check if hot layer is empty
        
        Returns:
            True if no messages in hot layer, False otherwise
        """
        count = await self.get_message_count()
        return count == 0
    
    async def refresh_ttl(self) -> None:
        """
        Refresh the TTL (time-to-live) for all hot data keys
        
        This extends the expiration time, useful when session is still active.
        """
        try:
            keys = RedisKeyNamespace.get_all_hot_keys(self.session_id)
            
            for key in keys:
                if self.redis_client.client.exists(key):
                    self.redis_client.client.expire(key, self.ttl_seconds)
            
            logger.debug(
                f"Refreshed TTL for hot data: session={self.session_id}, "
                f"ttl={self.ttl_seconds}s"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to refresh TTL: session={self.session_id}, "
                f"error={str(e)}"
            )
            # Don't raise - TTL refresh failure shouldn't break the flow

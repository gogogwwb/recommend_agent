"""
Warm Data Layer - PostgreSQL-based storage for compressed conversation history

This module implements the warm data layer of the three-layer memory architecture.
It stores conversation history beyond the recent 5 turns, with intelligent compression
based on token count rather than message count.

Key features:
- Token-based compression trigger (not message count)
- Asynchronous compression (non-blocking)
- Preserves critical user profile slots
- Automatic compression when token threshold exceeded
- Efficient context retrieval for agents
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import tiktoken

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.conversation import Message, MessageRole
from models.db_models import ConversationSession as ConversationSessionModel

logger = logging.getLogger(__name__)


class ConversationCompressor:
    """
    Conversation Compressor - Compresses conversation history using LLM
    
    This compressor intelligently summarizes conversation history while
    preserving critical information like user profile slots.
    """
    
    # Critical slots that must be preserved during compression
    CRITICAL_SLOTS = [
        "age",
        "income_range",
        "annual_income",
        "family_structure",
        "marital_status",
        "children_count",
        "dependents_count",
        "occupation",
        "risk_preference",
        "existing_coverage",
        "health_status",
    ]
    
    def __init__(self, llm_client=None, encoding_name: str = "cl100k_base"):
        """
        Initialize Conversation Compressor
        
        Args:
            llm_client: LLM client for compression (optional, can use rule-based fallback)
            encoding_name: Tiktoken encoding name for token counting
        """
        self.llm_client = llm_client
        self.encoding = tiktoken.get_encoding(encoding_name)
        
        logger.debug(f"Initialized ConversationCompressor with encoding={encoding_name}")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Failed to count tokens: {str(e)}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4
    
    def count_messages_tokens(self, messages: List[Message]) -> int:
        """
        Count total tokens in a list of messages
        
        Args:
            messages: List of Message objects
            
        Returns:
            Total token count
        """
        total_tokens = 0
        for message in messages:
            # Count content tokens
            total_tokens += self.count_tokens(message.content)
            
            # Add overhead for role and metadata (~10 tokens per message)
            total_tokens += 10
        
        return total_tokens
    
    def extract_slots_from_messages(self, messages: List[Message]) -> Dict[str, Any]:
        """
        Extract all slot values from messages
        
        Args:
            messages: List of Message objects
            
        Returns:
            Dictionary of extracted slots
        """
        all_slots = {}
        
        for message in messages:
            if message.extracted_slots:
                # Merge slots, later messages override earlier ones
                all_slots.update(message.extracted_slots)
        
        return all_slots
    
    async def compress_messages(
        self,
        messages: List[Message],
        preserve_slots: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Compress a list of messages into a summary
        
        Args:
            messages: List of Message objects to compress
            preserve_slots: Optional dictionary of slots to explicitly preserve
            
        Returns:
            Compressed summary string
        """
        try:
            # 1. Extract critical slots from messages
            extracted_slots = self.extract_slots_from_messages(messages)
            
            # Merge with explicitly provided slots
            if preserve_slots:
                extracted_slots.update(preserve_slots)
            
            # Filter to only critical slots
            critical_slots = {
                k: v for k, v in extracted_slots.items()
                if k in self.CRITICAL_SLOTS
            }
            
            # 2. If LLM client available, use LLM compression
            if self.llm_client:
                summary = await self._compress_with_llm(messages, critical_slots)
            else:
                # Fallback: rule-based compression
                summary = self._compress_rule_based(messages, critical_slots)
            
            # 3. Append preserved slots as structured data
            if critical_slots:
                slots_json = json.dumps(critical_slots, ensure_ascii=False, indent=2)
                summary += f"\n\n[保留的关键信息]\n{slots_json}"
            
            logger.info(
                f"Compressed {len(messages)} messages "
                f"(~{self.count_messages_tokens(messages)} tokens) "
                f"to summary (~{self.count_tokens(summary)} tokens)"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to compress messages: {str(e)}")
            # Fallback: return simple concatenation
            return self._compress_rule_based(messages, critical_slots)
    
    async def _compress_with_llm(
        self,
        messages: List[Message],
        critical_slots: Dict[str, Any]
    ) -> str:
        """
        Compress messages using LLM
        
        Args:
            messages: List of messages to compress
            critical_slots: Critical slots to preserve
            
        Returns:
            LLM-generated summary
        """
        # Build conversation text
        conversation_text = self._format_messages_for_compression(messages)
        
        # Build compression prompt
        prompt = f"""请将以下对话压缩成简洁的摘要，保留关键信息：

对话内容：
{conversation_text}

必须保留的关键信息：
{json.dumps(critical_slots, ensure_ascii=False, indent=2)}

要求：
1. 保留用户的核心需求和意图
2. 保留所有数字信息（年龄、收入、保额等）
3. 保留用户的偏好和限制条件
4. 使用第三人称描述（"用户表示..."）
5. 控制在200字以内

压缩摘要："""
        
        try:
            # Call LLM (assuming async interface)
            response = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=300,
                temperature=0.3
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"LLM compression failed: {str(e)}, falling back to rule-based")
            return self._compress_rule_based(messages, critical_slots)
    
    def _compress_rule_based(
        self,
        messages: List[Message],
        critical_slots: Dict[str, Any]
    ) -> str:
        """
        Rule-based compression fallback
        
        Args:
            messages: List of messages to compress
            critical_slots: Critical slots to preserve
            
        Returns:
            Rule-based summary
        """
        summary_parts = []
        
        # 1. Extract user messages (main information source)
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        
        if user_messages:
            # Concatenate user messages with ellipsis
            user_contents = [m.content[:100] for m in user_messages]  # Truncate long messages
            summary_parts.append(
                f"用户提供了以下信息：{' ... '.join(user_contents)}"
            )
        
        # 2. Extract assistant key points
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]
        
        if assistant_messages:
            # Just note that assistant responded
            summary_parts.append(
                f"系统进行了{len(assistant_messages)}次回复，收集了用户画像信息。"
            )
        
        # 3. Summarize critical slots
        if critical_slots:
            slot_summary = ", ".join([f"{k}={v}" for k, v in critical_slots.items()])
            summary_parts.append(f"关键信息：{slot_summary}")
        
        return "\n".join(summary_parts)
    
    def _format_messages_for_compression(self, messages: List[Message]) -> str:
        """
        Format messages for compression prompt
        
        Args:
            messages: List of messages
            
        Returns:
            Formatted conversation text
        """
        formatted = []
        
        for message in messages:
            role_label = "用户" if message.role == MessageRole.USER else "助手"
            formatted.append(f"{role_label}: {message.content}")
        
        return "\n".join(formatted)
    
    def decompress_for_context(
        self,
        compressed_history: str,
        recent_messages: List[Message]
    ) -> str:
        """
        Build context string from compressed history and recent messages
        
        Args:
            compressed_history: Compressed conversation history
            recent_messages: Recent uncompressed messages
            
        Returns:
            Formatted context string for agent
        """
        context_parts = []
        
        # 1. Add compressed history
        if compressed_history:
            context_parts.append("[历史对话摘要]")
            context_parts.append(compressed_history)
            context_parts.append("")
        
        # 2. Add recent messages
        if recent_messages:
            context_parts.append("[最近对话]")
            context_parts.append(self._format_recent_messages(recent_messages))
        
        return "\n".join(context_parts)
    
    def _format_recent_messages(self, messages: List[Message]) -> str:
        """
        Format recent messages for context
        
        Args:
            messages: List of recent messages
            
        Returns:
            Formatted message string
        """
        formatted = []
        
        for message in messages:
            role_label = "用户" if message.role == MessageRole.USER else "助手"
            timestamp = message.timestamp.strftime("%H:%M:%S")
            formatted.append(f"[{timestamp}] {role_label}: {message.content}")
        
        return "\n".join(formatted)


class WarmDataLayer:
    """
    Warm Data Layer - PostgreSQL storage for compressed conversation history
    
    This layer stores conversation history beyond the hot layer (recent 5 turns),
    with intelligent token-based compression to reduce context size.
    
    Key features:
    - Token-based compression trigger (default: 3000 tokens)
    - Asynchronous compression (non-blocking)
    - Preserves critical user profile slots
    - Efficient context retrieval
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        session_id: str,
        compressor: Optional[ConversationCompressor] = None,
        compression_token_threshold: int = 3000,
        enable_async_compression: bool = True
    ):
        """
        Initialize Warm Data Layer
        
        Args:
            db_session: Async SQLAlchemy session
            session_id: Session ID
            compressor: Optional ConversationCompressor instance
            compression_token_threshold: Token count threshold for compression (default: 3000)
            enable_async_compression: Enable async compression (default: True)
        """
        self.db = db_session
        self.session_id = session_id
        self.compressor = compressor or ConversationCompressor()
        self.compression_token_threshold = compression_token_threshold
        self.enable_async_compression = enable_async_compression
        
        # Track pending compression tasks
        self._compression_tasks: List[asyncio.Task] = []
        
        logger.debug(
            f"Initialized WarmDataLayer for session {session_id}, "
            f"token_threshold={compression_token_threshold}, "
            f"async={enable_async_compression}"
        )
    
    async def append_message(self, message: Message) -> None:
        """
        Append message to warm data layer
        
        This method:
        1. Immediately saves the message to database (non-blocking)
        2. Checks if token threshold exceeded
        3. Triggers async compression if needed (non-blocking)
        
        Args:
            message: Message object to append
            
        Raises:
            Exception: If database operation fails
        """
        try:
            # 1. Get or create session record
            session = await self._get_or_create_session()
            
            # 2. Append message to warm_messages list
            if not session.warm_messages:
                session.warm_messages = []
            
            session.warm_messages.append(message.model_dump())
            
            # 3. Update last activity timestamp
            session.last_activity_at = datetime.now()
            
            # 4. Commit immediately (non-blocking for user)
            await self.db.commit()
            
            logger.debug(
                f"Appended message to warm layer: session={self.session_id}, "
                f"role={message.role}, warm_count={len(session.warm_messages)}"
            )
            
            # 5. Check if compression needed (based on token count)
            await self._check_and_trigger_compression(session)
            
        except Exception as e:
            logger.error(
                f"Failed to append message to warm layer: session={self.session_id}, "
                f"error={str(e)}"
            )
            await self.db.rollback()
            raise
    
    async def _get_or_create_session(self) -> ConversationSessionModel:
        """
        Get existing session or create new one
        
        Returns:
            ConversationSessionModel instance
        """
        # Query existing session
        result = await self.db.execute(
            select(ConversationSessionModel).where(
                ConversationSessionModel.session_id == self.session_id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            # Create new session record
            session = ConversationSessionModel(
                session_id=self.session_id,
                warm_messages=[],
                compressed_history="",
                compression_count=0,
                created_at=datetime.now(),
                last_activity_at=datetime.now()
            )
            self.db.add(session)
            await self.db.commit()
            
            logger.info(f"Created new warm session record: session={self.session_id}")
        
        return session
    
    async def _check_and_trigger_compression(
        self,
        session: ConversationSessionModel
    ) -> None:
        """
        Check if compression needed and trigger if threshold exceeded
        
        IMPORTANT: Only counts tokens in UNCOMPRESSED warm_messages, not total history.
        This prevents repeated compression triggers after each message.
        
        Args:
            session: Session model instance
        """
        try:
            # Calculate current token count in UNCOMPRESSED warm_messages only
            if not session.warm_messages:
                return
            
            messages = [Message(**m) for m in session.warm_messages]
            uncompressed_token_count = self.compressor.count_messages_tokens(messages)
            
            logger.debug(
                f"Warm layer uncompressed token count: session={self.session_id}, "
                f"tokens={uncompressed_token_count}, threshold={self.compression_token_threshold}"
            )
            
            # Check if UNCOMPRESSED messages exceed threshold
            # After compression, warm_messages is cleared, so count resets to 0
            # This prevents repeated compression on every new message
            if uncompressed_token_count >= self.compression_token_threshold:
                logger.info(
                    f"Uncompressed token threshold exceeded, triggering compression: "
                    f"session={self.session_id}, uncompressed_tokens={uncompressed_token_count}"
                )
                
                if self.enable_async_compression:
                    # Trigger async compression (non-blocking)
                    task = asyncio.create_task(
                        self._compress_and_archive(session.session_id)
                    )
                    self._compression_tasks.append(task)
                    
                    # Clean up completed tasks
                    self._compression_tasks = [
                        t for t in self._compression_tasks if not t.done()
                    ]
                else:
                    # Synchronous compression (blocking)
                    await self._compress_and_archive(session.session_id)
            
        except Exception as e:
            logger.error(
                f"Failed to check compression trigger: session={self.session_id}, "
                f"error={str(e)}"
            )
            # Don't raise - compression check failure shouldn't break the flow
    
    async def _compress_and_archive(self, session_id: str) -> None:
        """
        Compress warm messages and archive to compressed_history
        
        This method runs asynchronously and:
        1. Loads current warm messages
        2. Compresses them using ConversationCompressor
        3. Appends to compressed_history
        4. Clears warm_messages
        
        Args:
            session_id: Session ID to compress
        """
        try:
            logger.info(f"Starting compression for session {session_id}")
            
            # Re-query session in this async context
            result = await self.db.execute(
                select(ConversationSessionModel).where(
                    ConversationSessionModel.session_id == session_id
                )
            )
            session = result.scalar_one_or_none()
            
            if not session or not session.warm_messages:
                logger.warning(f"No warm messages to compress: session={session_id}")
                return
            
            # 1. Parse messages
            messages = [Message(**m) for m in session.warm_messages]
            
            # 2. Extract critical slots
            critical_slots = self.compressor.extract_slots_from_messages(messages)
            
            # 3. Compress messages
            compressed_summary = await self.compressor.compress_messages(
                messages,
                preserve_slots=critical_slots
            )
            
            # 4. Append to compressed history
            if session.compressed_history:
                # Add batch separator
                batch_num = (session.compression_count or 0) + 1
                session.compressed_history += (
                    f"\n\n{'='*50}\n"
                    f"[压缩批次 {batch_num}]\n"
                    f"{'='*50}\n"
                    f"{compressed_summary}"
                )
            else:
                session.compressed_history = compressed_summary
            
            # 5. Update compression count
            session.compression_count = (session.compression_count or 0) + 1
            
            # 6. Clear warm messages (already compressed)
            original_count = len(session.warm_messages)
            session.warm_messages = []
            
            # 7. Update timestamp
            session.last_activity_at = datetime.now()
            
            # 8. Commit changes
            await self.db.commit()
            
            logger.info(
                f"Compression completed: session={session_id}, "
                f"batch={session.compression_count}, "
                f"compressed_messages={original_count}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to compress and archive: session={session_id}, "
                f"error={str(e)}"
            )
            await self.db.rollback()
            # Don't raise - compression failure shouldn't break the main flow
    
    async def get_warm_context(self) -> Dict[str, Any]:
        """
        Get warm data context for the session
        
        Returns:
            Dictionary containing:
                - compressed_history: Compressed conversation history
                - warm_messages: Uncompressed recent messages
                - compression_count: Number of compression batches
                - token_count: Estimated token count
        """
        try:
            session = await self._get_or_create_session()
            
            # Parse warm messages
            warm_messages = []
            if session.warm_messages:
                warm_messages = [Message(**m) for m in session.warm_messages]
            
            # Calculate token count
            token_count = 0
            if session.compressed_history:
                token_count += self.compressor.count_tokens(session.compressed_history)
            if warm_messages:
                token_count += self.compressor.count_messages_tokens(warm_messages)
            
            context = {
                "compressed_history": session.compressed_history or "",
                "warm_messages": warm_messages,
                "compression_count": session.compression_count or 0,
                "token_count": token_count,
                "session_id": self.session_id,
            }
            
            logger.debug(
                f"Retrieved warm context: session={self.session_id}, "
                f"compressed_batches={context['compression_count']}, "
                f"warm_messages={len(warm_messages)}, "
                f"tokens={token_count}"
            )
            
            return context
            
        except Exception as e:
            logger.error(
                f"Failed to get warm context: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def get_full_context_for_agent(
        self,
        hot_messages: List[Message],
        target_agent: Optional[str] = None
    ) -> str:
        """
        Build complete context for agent from warm + hot data
        
        This combines:
        1. Compressed history (from warm layer)
        2. Uncompressed warm messages (if any, filtered by agent)
        3. Recent hot messages (filtered by agent)
        
        Args:
            hot_messages: Recent messages from hot data layer
            target_agent: Optional target agent name for context filtering.
                         If None, returns all messages (no filtering).
            
        Returns:
            Formatted context string for agent consumption
        """
        try:
            warm_context = await self.get_warm_context()
            
            # Build layered context
            context_parts = []
            
            # 1. Add compressed history if exists
            # Note: Compressed history should ideally be pre-filtered during compression
            if warm_context["compressed_history"]:
                context_parts.append("[历史对话摘要]")
                context_parts.append(warm_context["compressed_history"])
                context_parts.append("")
            
            # 2. Add uncompressed warm messages (with optional filtering)
            if warm_context["warm_messages"]:
                warm_messages = warm_context["warm_messages"]
                
                # Apply filtering if target_agent specified
                if target_agent:
                    try:
                        from memory.context_filter import AgentContextScope
                        warm_messages = AgentContextScope.filter_messages(
                            warm_messages,
                            target_agent
                        )
                    except ImportError:
                        logger.warning(
                            "context_filter module not available, "
                            "skipping message filtering"
                        )
                
                if warm_messages:
                    context_parts.append("[温数据层对话]")
                    context_parts.append(
                        self.compressor._format_recent_messages(warm_messages)
                    )
                    context_parts.append("")
            
            # 3. Add hot messages (with optional filtering)
            if hot_messages:
                filtered_hot = hot_messages
                
                # Apply filtering if target_agent specified
                if target_agent:
                    try:
                        from memory.context_filter import AgentContextScope
                        filtered_hot = AgentContextScope.filter_messages(
                            hot_messages,
                            target_agent
                        )
                    except ImportError:
                        logger.warning(
                            "context_filter module not available, "
                            "skipping message filtering"
                        )
                
                if filtered_hot:
                    context_parts.append("[最近对话]")
                    context_parts.append(
                        self.compressor._format_recent_messages(filtered_hot)
                    )
            
            full_context = "\n".join(context_parts)
            
            logger.debug(
                f"Built full context for agent: session={self.session_id}, "
                f"target_agent={target_agent}, "
                f"total_tokens={self.compressor.count_tokens(full_context)}"
            )
            
            return full_context
            
        except Exception as e:
            logger.error(
                f"Failed to build full context: session={self.session_id}, "
                f"error={str(e)}"
            )
            raise
    
    async def wait_for_pending_compressions(self) -> None:
        """
        Wait for all pending compression tasks to complete
        
        This should be called before session archival or when you need
        to ensure all compressions are finished.
        """
        if self._compression_tasks:
            logger.info(
                f"Waiting for {len(self._compression_tasks)} pending compressions: "
                f"session={self.session_id}"
            )
            
            await asyncio.gather(*self._compression_tasks, return_exceptions=True)
            
            logger.info(f"All compressions completed: session={self.session_id}")
            
            # Clear completed tasks
            self._compression_tasks = []
    
    async def get_token_count(self) -> int:
        """
        Get total token count in warm layer (compressed + uncompressed)
        
        Returns:
            Total token count (compressed history + uncompressed warm messages)
        """
        try:
            warm_context = await self.get_warm_context()
            return warm_context["token_count"]
        except Exception as e:
            logger.error(
                f"Failed to get token count: session={self.session_id}, "
                f"error={str(e)}"
            )
            return 0
    
    async def get_uncompressed_token_count(self) -> int:
        """
        Get token count of uncompressed warm messages only
        
        This is useful for monitoring when next compression will trigger.
        
        Returns:
            Token count of uncompressed messages
        """
        try:
            session = await self._get_or_create_session()
            
            if not session.warm_messages:
                return 0
            
            messages = [Message(**m) for m in session.warm_messages]
            return self.compressor.count_messages_tokens(messages)
            
        except Exception as e:
            logger.error(
                f"Failed to get uncompressed token count: session={self.session_id}, "
                f"error={str(e)}"
            )
            return 0

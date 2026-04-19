"""
Context Filter - Agent-specific context filtering

This module provides context filtering capabilities for multi-agent architectures,
ensuring each agent only sees relevant conversation history.
"""

import logging
from typing import List, Set
from models.conversation import Message, MessageRole, IntentType

logger = logging.getLogger(__name__)


class AgentContextScope:
    """
    Agent Context Scope - Defines what each agent can see
    
    This class manages visibility rules for multi-agent architectures,
    ensuring context isolation and reducing token waste.
    """
    
    # Agent visibility configuration
    # Format: {agent_name: {visible_agents: [...], visible_intents: [...], exclude_intents: [...]}}
    AGENT_VISIBILITY = {
        "ProfileCollectionAgent": {
            "visible_agents": ["ProfileCollectionAgent"],
            "visible_intents": [
                IntentType.PROVIDE_INFO,
                IntentType.MODIFY_INFO,
                IntentType.ASK_QUESTION,
            ],
            "exclude_intents": [IntentType.CHITCHAT],
        },
        
        "RecommendationAgent": {
            "visible_agents": [
                "ProfileCollectionAgent",  # See profile collection
                "RecommendationAgent"  # See own conversations
            ],
            "visible_intents": [
                IntentType.CONSULT_COVERAGE,
                IntentType.COMPARE_PRODUCTS,
                IntentType.REQUEST_EXPLANATION,
                IntentType.PROVIDE_INFO,
            ],
            "exclude_intents": [IntentType.CHITCHAT],
        },
        
        "ComplianceAgent": {
            "visible_agents": [
                "ProfileCollectionAgent",  # See user profile
                "RecommendationAgent",  # See recommendations
                "ComplianceAgent"  # See own conversations
            ],
            "visible_intents": [
                IntentType.PROVIDE_INFO,
                IntentType.CONSULT_COVERAGE,
            ],
            "exclude_intents": [IntentType.CHITCHAT],
        }
    }
    
    @classmethod
    def should_include_message(
        cls,
        message: Message,
        target_agent: str
    ) -> bool:
        """
        Determine if a message should be included in target agent's context
        
        Args:
            message: Message to check
            target_agent: Target agent name
            
        Returns:
            True if message should be included, False otherwise
        """
        try:
            # Get visibility rules for target agent
            scope = cls.AGENT_VISIBILITY.get(target_agent)
            
            if not scope:
                # No rules defined, include by default
                logger.warning(
                    f"No visibility rules for agent {target_agent}, "
                    f"including message by default"
                )
                return True
            
            # 1. Check assistant messages (filter by agent_name)
            if message.role == MessageRole.ASSISTANT:
                if message.agent_name:
                    visible_agents = scope.get("visible_agents", [])
                    if message.agent_name not in visible_agents:
                        logger.debug(
                            f"Filtering out assistant message from {message.agent_name} "
                            f"for {target_agent}"
                        )
                        return False
            
            # 2. Check user messages (filter by intent)
            elif message.role == MessageRole.USER:
                # Check exclude list first (higher priority)
                exclude_intents = scope.get("exclude_intents", [])
                if message.intent in exclude_intents:
                    logger.debug(
                        f"Filtering out user message with intent {message.intent} "
                        f"for {target_agent} (excluded)"
                    )
                    return False
                
                # Check include list
                visible_intents = scope.get("visible_intents", [])
                if message.intent and message.intent not in visible_intents:
                    logger.debug(
                        f"Filtering out user message with intent {message.intent} "
                        f"for {target_agent} (not in visible list)"
                    )
                    return False
            
            # 3. System messages - always include
            elif message.role == MessageRole.SYSTEM:
                return True
            
            return True
            
        except Exception as e:
            logger.error(
                f"Error checking message visibility: {str(e)}, "
                f"including message by default"
            )
            return True
    
    @classmethod
    def filter_messages(
        cls,
        messages: List[Message],
        target_agent: str
    ) -> List[Message]:
        """
        Filter messages for target agent
        
        Args:
            messages: List of messages to filter
            target_agent: Target agent name
            
        Returns:
            Filtered list of messages
        """
        filtered = [
            msg for msg in messages
            if cls.should_include_message(msg, target_agent)
        ]
        
        original_count = len(messages)
        filtered_count = len(filtered)
        
        if original_count > filtered_count:
            logger.info(
                f"Filtered messages for {target_agent}: "
                f"{original_count} -> {filtered_count} "
                f"({100 * (original_count - filtered_count) / original_count:.1f}% reduction)"
            )
        
        return filtered
    
    @classmethod
    def get_visible_agents(cls, target_agent: str) -> Set[str]:
        """
        Get list of agents visible to target agent
        
        Args:
            target_agent: Target agent name
            
        Returns:
            Set of visible agent names
        """
        scope = cls.AGENT_VISIBILITY.get(target_agent, {})
        return set(scope.get("visible_agents", []))
    
    @classmethod
    def get_visible_intents(cls, target_agent: str) -> Set[IntentType]:
        """
        Get list of intents visible to target agent
        
        Args:
            target_agent: Target agent name
            
        Returns:
            Set of visible intent types
        """
        scope = cls.AGENT_VISIBILITY.get(target_agent, {})
        return set(scope.get("visible_intents", []))
    
    @classmethod
    def get_excluded_intents(cls, target_agent: str) -> Set[IntentType]:
        """
        Get list of intents excluded for target agent
        
        Args:
            target_agent: Target agent name
            
        Returns:
            Set of excluded intent types
        """
        scope = cls.AGENT_VISIBILITY.get(target_agent, {})
        return set(scope.get("exclude_intents", []))


class IntentBasedFilter:
    """
    Intent-based context filtering (alternative approach)
    
    This class provides intent-based filtering as an alternative
    to agent-based filtering.
    """
    
    # Intent filter configuration
    AGENT_INTENT_FILTER = {
        "ProfileCollectionAgent": [
            IntentType.PROVIDE_INFO,
            IntentType.MODIFY_INFO,
            IntentType.ASK_QUESTION,
        ],
        "RecommendationAgent": [
            IntentType.CONSULT_COVERAGE,
            IntentType.COMPARE_PRODUCTS,
            IntentType.REQUEST_EXPLANATION,
            IntentType.PROVIDE_INFO,
        ],
        "ComplianceAgent": [
            IntentType.PROVIDE_INFO,
            IntentType.CONSULT_COVERAGE,
        ]
    }
    
    @classmethod
    def filter_messages_by_intent(
        cls,
        messages: List[Message],
        target_agent: str
    ) -> List[Message]:
        """
        Filter messages by intent for target agent
        
        Args:
            messages: List of messages to filter
            target_agent: Target agent name
            
        Returns:
            Filtered list of messages
        """
        allowed_intents = cls.AGENT_INTENT_FILTER.get(target_agent, [])
        
        filtered = []
        for msg in messages:
            # Assistant messages: check agent_name
            if msg.role == MessageRole.ASSISTANT:
                if msg.agent_name == target_agent:
                    filtered.append(msg)
            
            # User messages: check intent
            elif msg.role == MessageRole.USER:
                if msg.intent in allowed_intents:
                    filtered.append(msg)
                elif msg.intent is None:
                    # No intent label, include by default
                    filtered.append(msg)
            
            # System messages: always include
            elif msg.role == MessageRole.SYSTEM:
                filtered.append(msg)
        
        return filtered

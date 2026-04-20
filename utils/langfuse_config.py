"""
Langfuse Integration for LLM Observability

This module provides Langfuse integration for tracing, monitoring, and debugging
the insurance recommendation agent system.

Key Features:
- Automatic tracing of LangGraph executions via LangChain Callbacks
- TTFT (Time-to-First-Token) tracking for streaming LLM calls
- Score reporting for quality evaluation
- Token and cost tracking (automatic)
- Sensitive data anonymization

Default Metrics Support:
- Token & Cost: ✅ Automatic
- Latency: ✅ Automatic
- TTFT: ❌ Requires manual tracking (implemented below)
- Score: ❌ Requires manual reporting (implemented below)

Usage:
    # Enable tracing via environment variables
    export LANGFUSE_SECRET_KEY=sk-lf-...
    export LANGFUSE_PUBLIC_KEY=pk-lf-...
    export LANGFUSE_HOST=https://cloud.langfuse.com

    # Or configure programmatically
    from utils.langfuse_config import configure_langfuse, get_langfuse_handler
    configure_langfuse()
    handler = get_langfuse_handler(user_id="user_123", session_id="session_456")
"""
import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

from config import get_settings

logger = logging.getLogger(__name__)


# ==================== Configuration ====================

def configure_langfuse(
    secret_key: Optional[str] = None,
    public_key: Optional[str] = None,
    host: Optional[str] = None,
    enabled: bool = True,
) -> None:
    """
    Configure Langfuse tracing for the application.
    
    This function sets the necessary environment variables for Langfuse.
    It can be called at application startup to enable tracing.
    
    Args:
        secret_key: Langfuse secret key (default: from config)
        public_key: Langfuse public key (default: from config)
        host: Langfuse host URL (default: from config)
        enabled: Enable/disable tracing
        
    Example:
        # Enable tracing at startup
        configure_langfuse(
            secret_key="sk-lf-...",
            public_key="pk-lf-...",
            host="https://cloud.langfuse.com"
        )
    """
    settings = get_settings()
    
    if not enabled:
        os.environ["LANGFUSE_ENABLED"] = "false"
        logger.debug("Langfuse tracing disabled")
        return
    
    # Set keys
    if secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
    elif settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    
    if public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    elif settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    
    # Set host
    if host:
        os.environ["LANGFUSE_HOST"] = host
    elif settings.LANGFUSE_HOST:
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST
    
    os.environ["LANGFUSE_ENABLED"] = "true"
    
    # Log configuration
    langfuse_host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    logger.info(f"Langfuse tracing enabled, host: {langfuse_host}")


def is_langfuse_enabled() -> bool:
    """
    Check if Langfuse tracing is currently enabled.
    
    Returns:
        True if tracing is enabled, False otherwise
    """
    return os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true"


# ==================== LangChain Callback Handler ====================

def get_langfuse_handler(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    trace_name: Optional[str] = None,
) -> Optional[Any]:
    """
    Get Langfuse CallbackHandler for LangChain/LangGraph integration.
    
    This handler automatically captures:
    - LLM calls with prompts and completions
    - Token usage and costs
    - Latency metrics
    - Tool calls
    - Errors
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        tags: List of tags for the trace
        metadata: Additional metadata
        trace_name: Name for the trace
        
    Returns:
        Langfuse CallbackHandler instance or None if not configured
        
    Example:
        from utils.langfuse_config import get_langfuse_handler
        
        handler = get_langfuse_handler(
            user_id="user_123",
            session_id="session_456",
            tags=["production", "recommendation"]
        )
        
        result = await graph.ainvoke(input_state, config={"callbacks": [handler]})
    """
    if not is_langfuse_enabled():
        logger.debug("Langfuse not enabled, skipping handler creation")
        return None
    
    try:
        from langfuse.langchain import CallbackHandler
        
        handler = CallbackHandler(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            metadata=metadata,
            trace_name=trace_name or "insurance-recommendation-agent",
        )
        
        logger.debug(f"Created Langfuse handler for session: {session_id}")
        return handler
        
    except ImportError:
        logger.warning("langfuse not installed, skipping handler creation")
        return None
    except Exception as e:
        logger.error(f"Failed to create Langfuse handler: {e}")
        return None


# ==================== TTFT Tracking ====================

@dataclass
class TTFTTracker:
    """
    Time-to-First-Token (TTFT) Tracker
    
    Langfuse does not automatically track TTFT for Python SDK.
    This class provides manual TTFT tracking for streaming LLM calls.
    
    Usage:
        tracker = TTFTTracker(trace_id="trace_123")
        
        # Start tracking before LLM call
        tracker.start()
        
        # Mark first token received
        async for chunk in llm.astream(prompt):
            if not tracker.first_token_received:
                tracker.mark_first_token()
            # process chunk...
        
        # Get TTFT in milliseconds
        ttft_ms = tracker.get_ttft_ms()
        
        # Report to Langfuse
        tracker.report_to_langfuse()
    """
    trace_id: str
    start_time: Optional[float] = None
    first_token_time: Optional[float] = None
    first_token_received: bool = False
    ttft_ms: Optional[float] = None
    
    def start(self) -> None:
        """Start tracking - call before LLM invocation"""
        self.start_time = time.time()
    
    def mark_first_token(self) -> None:
        """Mark when first token is received"""
        if not self.first_token_received and self.start_time:
            self.first_token_time = time.time()
            self.first_token_received = True
            self.ttft_ms = (self.first_token_time - self.start_time) * 1000
            logger.debug(f"TTFT for trace {self.trace_id}: {self.ttft_ms:.2f}ms")
    
    def get_ttft_ms(self) -> Optional[float]:
        """Get TTFT in milliseconds"""
        return self.ttft_ms
    
    def report_to_langfuse(self, trace_id: Optional[str] = None) -> None:
        """
        Report TTFT as a score to Langfuse.
        
        Args:
            trace_id: Optional trace ID to update (uses self.trace_id if not provided)
        """
        if not is_langfuse_enabled() or self.ttft_ms is None:
            return
        
        try:
            from langfuse import Langfuse
            
            client = Langfuse()
            actual_trace_id = trace_id or self.trace_id
            
            # Report TTFT as a score
            client.score(
                trace_id=actual_trace_id,
                name="ttft_ms",
                value=self.ttft_ms,
                comment="Time-to-First-Token in milliseconds"
            )
            
            logger.debug(f"Reported TTFT score: {self.ttft_ms:.2f}ms for trace {actual_trace_id}")
            
        except Exception as e:
            logger.warning(f"Failed to report TTFT to Langfuse: {e}")


def create_ttft_tracker(trace_id: str) -> TTFTTracker:
    """
    Create a TTFT tracker for a trace.
    
    Args:
        trace_id: Trace identifier
        
    Returns:
        TTFTTracker instance
    """
    return TTFTTracker(trace_id=trace_id)


# ==================== Score Reporting ====================

def report_score(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
    data_type: str = "NUMERIC",
) -> bool:
    """
    Report a score to Langfuse for a trace.
    
    Use this to report quality metrics, user feedback, or custom evaluations.
    
    Args:
        trace_id: Trace identifier
        name: Score name (e.g., "user_feedback", "accuracy", "relevance")
        value: Score value
        comment: Optional comment
        data_type: Score data type ("NUMERIC" or "CATEGORICAL")
        
    Returns:
        True if score was reported successfully
        
    Example:
        # Report user feedback
        report_score(
            trace_id="trace_123",
            name="user_feedback",
            value=0.9,
            comment="User rated response as helpful"
        )
        
        # Report LLM-as-Judge evaluation
        report_score(
            trace_id="trace_123",
            name="relevance",
            value=0.85,
            comment="LLM-as-Judge relevance score"
        )
    """
    if not is_langfuse_enabled():
        logger.debug("Langfuse not enabled, skipping score report")
        return False
    
    try:
        from langfuse import Langfuse
        
        client = Langfuse()
        
        client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
            data_type=data_type,
        )
        
        logger.debug(f"Reported score '{name}': {value} for trace {trace_id}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to report score to Langfuse: {e}")
        return False


def report_user_feedback(
    trace_id: str,
    rating: float,
    comment: Optional[str] = None,
) -> bool:
    """
    Report user feedback score.
    
    Args:
        trace_id: Trace identifier
        rating: User rating (0.0 to 1.0)
        comment: Optional user comment
        
    Returns:
        True if score was reported successfully
    """
    return report_score(
        trace_id=trace_id,
        name="user_feedback",
        value=rating,
        comment=comment,
    )


def report_llm_judge_score(
    trace_id: str,
    metric_name: str,
    score: float,
    reasoning: Optional[str] = None,
) -> bool:
    """
    Report LLM-as-Judge evaluation score.
    
    Args:
        trace_id: Trace identifier
        metric_name: Metric name (e.g., "relevance", "accuracy", "helpfulness")
        score: Score value (0.0 to 1.0)
        reasoning: Optional reasoning from the judge
        
    Returns:
        True if score was reported successfully
    """
    return report_score(
        trace_id=trace_id,
        name=f"llm_judge_{metric_name}",
        value=score,
        comment=reasoning,
    )


# ==================== Trace Configuration ====================

def get_trace_config(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    environment: str = "development",
    tags: Optional[List[str]] = None,
    trace_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get configuration for Langfuse tracing.
    
    This creates a config dict that includes:
    - Langfuse CallbackHandler for LangChain/LangGraph
    - Tags and metadata for trace organization
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        environment: Environment name (development, staging, production)
        tags: Additional tags for the trace
        trace_name: Name for the trace
        
    Returns:
        Config dict with callbacks, tags, and metadata
        
    Example:
        config = get_trace_config(
            user_id="user_123",
            session_id="session_456",
            environment="production",
            tags=["recommendation", "insurance"]
        )
        
        result = await graph.ainvoke(input_state, config=config)
    """
    config: Dict[str, Any] = {}
    
    # Build tags
    trace_tags = [environment]
    if tags:
        trace_tags.extend(tags)
    
    # Build metadata
    metadata = {
        "environment": environment,
    }
    
    if user_id:
        metadata["user_id"] = user_id
    
    if session_id:
        metadata["session_id"] = session_id
    
    # Get Langfuse handler
    handler = get_langfuse_handler(
        user_id=user_id,
        session_id=session_id,
        tags=trace_tags,
        metadata=metadata,
        trace_name=trace_name,
    )
    
    if handler:
        config["callbacks"] = [handler]
    
    config["tags"] = trace_tags
    config["metadata"] = metadata
    
    return config


# ==================== Sensitive Data Anonymization ====================

SENSITIVE_PATTERNS = [
    # Chinese ID card numbers (18 digits)
    (r"\b\d{17}[\dXx]\b", "<id_card>"),
    # Chinese phone numbers
    (r"\b1[3-9]\d{9}\b", "<phone>"),
    # Email addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "<email>"),
    # Social Security Numbers (US format)
    (r"\b\d{3}-?\d{2}-?\d{4}\b", "<ssn>"),
    # Bank card numbers (16 digits)
    (r"\b\d{16}\b", "<bank_card>"),
]


def anonymize_sensitive_data(text: str) -> str:
    """
    Anonymize sensitive data in text.
    
    This function redacts:
    - Chinese ID card numbers
    - Chinese phone numbers
    - Email addresses
    - US Social Security Numbers
    - Bank card numbers
    
    Args:
        text: Input text to anonymize
        
    Returns:
        Anonymized text
    """
    import re
    
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result)
    
    return result


# ==================== Low-level SDK Usage ====================

def create_trace(
    name: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
) -> Optional[Any]:
    """
    Create a trace using the Langfuse SDK.
    
    Use this for manual instrumentation when not using LangChain.
    
    Args:
        name: Trace name
        user_id: User identifier
        session_id: Session identifier
        metadata: Additional metadata
        tags: Tags for the trace
        
    Returns:
        Langfuse Trace object or None if not configured
        
    Example:
        trace = create_trace(
            name="custom-operation",
            user_id="user_123",
            session_id="session_456"
        )
        
        # Add a span
        span = trace.span(name="llm_call", input={"prompt": "..."})
        # ... do work ...
        span.end(output={"response": "..."})
        
        # Flush to ensure data is sent
        from langfuse import Langfuse
        Langfuse().flush()
    """
    if not is_langfuse_enabled():
        return None
    
    try:
        from langfuse import Langfuse
        
        client = Langfuse()
        
        trace = client.trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
        
        logger.debug(f"Created trace: {name}")
        return trace
        
    except Exception as e:
        logger.warning(f"Failed to create trace: {e}")
        return None


def flush_langfuse() -> None:
    """
    Flush all queued events to Langfuse.
    
    Call this before application exit to ensure all traces are sent.
    """
    if not is_langfuse_enabled():
        return
    
    try:
        from langfuse import Langfuse
        
        client = Langfuse()
        client.flush()
        logger.debug("Flushed Langfuse events")
        
    except Exception as e:
        logger.warning(f"Failed to flush Langfuse: {e}")


def shutdown_langfuse() -> None:
    """
    Shutdown Langfuse client.
    
    Call this before application exit.
    """
    if not is_langfuse_enabled():
        return
    
    try:
        from langfuse import Langfuse
        
        client = Langfuse()
        client.shutdown()
        logger.debug("Shutdown Langfuse client")
        
    except Exception as e:
        logger.warning(f"Failed to shutdown Langfuse: {e}")


# ==================== Module Exports ====================

__all__ = [
    # Configuration
    "configure_langfuse",
    "is_langfuse_enabled",
    
    # LangChain integration
    "get_langfuse_handler",
    "get_trace_config",
    
    # TTFT tracking
    "TTFTTracker",
    "create_ttft_tracker",
    
    # Score reporting
    "report_score",
    "report_user_feedback",
    "report_llm_judge_score",
    
    # Anonymization
    "anonymize_sensitive_data",
    
    # Low-level SDK
    "create_trace",
    "flush_langfuse",
    "shutdown_langfuse",
]

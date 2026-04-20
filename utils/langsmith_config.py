"""
LangSmith Integration for Monitoring and Debugging

This module provides LangSmith integration for tracing, monitoring, and debugging
the insurance recommendation agent system.

Key Features:
- Automatic tracing of LangGraph executions
- Custom metadata and tags for traces
- Selective tracing with tracing_context
- Sensitive data anonymization
- Project-based trace organization

Usage:
    # Enable tracing via environment variables
    export LANGSMITH_TRACING=true
    export LANGSMITH_API_KEY=<your-api-key>
    export LANGSMITH_PROJECT=insurance-recommendation-agent

    # Or configure programmatically
    from utils.langsmith_config import configure_langsmith, trace_context
    configure_langsmith(tracing=True, project="my-project")
"""
import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from config import get_settings

logger = logging.getLogger(__name__)


# ==================== Configuration ====================

def configure_langsmith(
    tracing: Optional[bool] = None,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> None:
    """
    Configure LangSmith tracing for the application.
    
    This function sets the necessary environment variables for LangSmith.
    It can be called at application startup to enable tracing.
    
    Args:
        tracing: Enable/disable tracing (default: from config)
        api_key: LangSmith API key (default: from config)
        project: Project name for organizing traces (default: from config)
        workspace_id: Workspace ID for multi-workspace accounts (default: from config)
        
    Example:
        # Enable tracing at startup
        configure_langsmith(
            tracing=True,
            api_key="lsv2_pt_...",
            project="insurance-agent-prod"
        )
        
        # Or use environment variables
        # export LANGSMITH_TRACING=true
        # export LANGSMITH_API_KEY=lsv2_pt_...
        # export LANGSMITH_PROJECT=insurance-agent-prod
    """
    settings = get_settings()
    
    # Set tracing flag
    if tracing is not None:
        os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"
    elif settings.LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "true"
    
    # Set API key
    if api_key:
        os.environ["LANGSMITH_API_KEY"] = api_key
    elif settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    
    # Set project name
    if project:
        os.environ["LANGSMITH_PROJECT"] = project
    elif settings.LANGSMITH_PROJECT:
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    
    # Set workspace ID (for multi-workspace accounts)
    if workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = workspace_id
    elif settings.LANGSMITH_WORKSPACE_ID:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.LANGSMITH_WORKSPACE_ID
    
    # Log configuration
    is_enabled = os.environ.get("LANGSMITH_TRACING", "false").lower() == "true"
    project_name = os.environ.get("LANGSMITH_PROJECT", "default")
    
    if is_enabled:
        logger.info(f"LangSmith tracing enabled for project: {project_name}")
    else:
        logger.debug("LangSmith tracing not enabled")


def is_tracing_enabled() -> bool:
    """
    Check if LangSmith tracing is currently enabled.
    
    Returns:
        True if tracing is enabled, False otherwise
    """
    return os.environ.get("LANGSMITH_TRACING", "false").lower() == "true"


# ==================== Tracing Context ====================

@contextmanager
def trace_context(
    enabled: bool = True,
    project_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for selective tracing.
    
    Use this to trace specific invocations or parts of your application.
    
    Args:
        enabled: Whether to enable tracing for this context
        project_name: Project name for this trace (optional)
        tags: List of tags to attach to the trace
        metadata: Dictionary of metadata to attach to the trace
        
    Yields:
        None
        
    Example:
        from utils.langsmith_config import trace_context
        
        # Trace a specific invocation
        with trace_context(
            project_name="recommendation-test",
            tags=["production", "recommendation"],
            metadata={"user_id": "user_123", "session_id": "session_456"}
        ):
            result = await agent.ainvoke(input_state)
        
        # Skip tracing for specific invocations
        with trace_context(enabled=False):
            result = await agent.ainvoke(input_state)  # Not traced
    """
    try:
        import langsmith as ls
    except ImportError:
        logger.warning("langsmith not installed, skipping trace context")
        yield
        return
    
    # Build kwargs for tracing_context
    kwargs = {"enabled": enabled}
    
    if project_name:
        kwargs["project_name"] = project_name
    
    if tags:
        kwargs["tags"] = tags
    
    if metadata:
        kwargs["metadata"] = metadata
    
    # Use langsmith's tracing_context
    with ls.tracing_context(**kwargs):
        yield


# ==================== Trace Metadata ====================

def get_trace_config(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    environment: str = "development",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Get configuration for attaching metadata to traces.
    
    Use this to create a config dict for agent.invoke() calls.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        environment: Environment name (development, staging, production)
        tags: Additional tags for the trace
        
    Returns:
        Config dict with tags and metadata
        
    Example:
        config = get_trace_config(
            user_id="user_123",
            session_id="session_456",
            environment="production",
            tags=["recommendation", "insurance"]
        )
        
        result = await agent.ainvoke(input_state, config=config)
    """
    config: Dict[str, Any] = {}
    
    # Build tags
    trace_tags = [environment]
    if tags:
        trace_tags.extend(tags)
    config["tags"] = trace_tags
    
    # Build metadata
    metadata = {
        "environment": environment,
    }
    
    if user_id:
        metadata["user_id"] = user_id
    
    if session_id:
        metadata["session_id"] = session_id
    
    config["metadata"] = metadata
    
    return config


# ==================== Sensitive Data Anonymization ====================

def create_sensitive_data_anonymizer():
    """
    Create an anonymizer to prevent logging sensitive data to LangSmith.
    
    This creates patterns to redact:
    - Social Security Numbers (XXX-XX-XXXX)
    - Phone numbers (Chinese format)
    - Email addresses
    - ID card numbers (Chinese format)
    
    Returns:
        Anonymizer instance or None if langsmith not installed
        
    Example:
        from utils.langsmith_config import create_sensitive_data_anonymizer
        from langchain_core.tracers.langchain import LangChainTracer
        
        anonymizer = create_sensitive_data_anonymizer()
        tracer = LangChainTracer(client=Client(anonymizer=anonymizer))
        
        graph = graph.with_config({'callbacks': [tracer]})
    """
    try:
        from langsmith import Client
        from langsmith.anonymizer import create_anonymizer
    except ImportError:
        logger.warning("langsmith not installed, cannot create anonymizer")
        return None
    
    anonymizer = create_anonymizer([
        # Chinese ID card numbers (18 digits)
        {
            "pattern": r"\b\d{17}[\dXx]\b",
            "replace": "<id_card>"
        },
        # Chinese phone numbers
        {
            "pattern": r"\b1[3-9]\d{9}\b",
            "replace": "<phone>"
        },
        # Email addresses
        {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "replace": "<email>"
        },
        # Social Security Numbers (US format)
        {
            "pattern": r"\b\d{3}-?\d{2}-?\d{4}\b",
            "replace": "<ssn>"
        },
        # Bank card numbers (16 digits)
        {
            "pattern": r"\b\d{16}\b",
            "replace": "<bank_card>"
        },
    ])
    
    return anonymizer


def get_tracer_with_anonymizer():
    """
    Get a LangChain tracer with sensitive data anonymization.
    
    Returns:
        LangChainTracer instance with anonymizer, or None if not configured
        
    Example:
        from utils.langsmith_config import get_tracer_with_anonymizer
        
        tracer = get_tracer_with_anonymizer()
        if tracer:
            graph = graph.with_config({'callbacks': [tracer]})
    """
    try:
        from langchain_core.tracers.langchain import LangChainTracer
        from langsmith import Client
    except ImportError:
        logger.warning("langsmith not installed, cannot create tracer")
        return None
    
    anonymizer = create_sensitive_data_anonymizer()
    
    if anonymizer:
        client = Client(anonymizer=anonymizer)
        tracer = LangChainTracer(client=client)
        logger.info("Created LangChain tracer with sensitive data anonymization")
        return tracer
    
    return None


# ==================== Helper Functions ====================

def log_run_info(
    run_name: str,
    run_type: str = "chain",
    inputs: Optional[Dict[str, Any]] = None,
    outputs: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log information about a run for debugging purposes.
    
    This is useful for logging custom runs that aren't automatically traced.
    
    Args:
        run_name: Name of the run
        run_type: Type of run (chain, llm, tool, etc.)
        inputs: Input data
        outputs: Output data
        error: Error message if any
        metadata: Additional metadata
    """
    if not is_tracing_enabled():
        return
    
    try:
        import langsmith as ls
        
        client = ls.Client()
        
        # Create a run
        run = client.create_run(
            name=run_name,
            run_type=run_type,
            inputs=inputs or {},
            outputs=outputs or {},
            error=error,
            extra={"metadata": metadata or {}},
        )
        
        logger.debug(f"Logged run: {run_name} (id: {run.id})")
        
    except Exception as e:
        logger.warning(f"Failed to log run to LangSmith: {e}")


# ==================== Module Exports ====================

__all__ = [
    # Configuration
    "configure_langsmith",
    "is_tracing_enabled",
    
    # Tracing context
    "trace_context",
    
    # Trace metadata
    "get_trace_config",
    
    # Anonymization
    "create_sensitive_data_anonymizer",
    "get_tracer_with_anonymizer",
    
    # Helper functions
    "log_run_info",
]

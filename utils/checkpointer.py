"""
PostgresSaver Checkpointer Manager for LangGraph Session State Management

This module provides PostgresSaver-based checkpointer for LangGraph,
enabling session state persistence and recovery.

Key Features:
- PostgresSaver initialization with connection string
- Automatic table setup for checkpoint storage
- Thread-safe singleton pattern
- Session state persistence and recovery
- Time-travel debugging support

Architecture Decision:
Using PostgresSaver to replace HotDataLayer and WarmDataLayer because:
1. Native LangGraph integration - no custom code needed
2. Built-in message persistence and session recovery
3. Time-travel debugging support
4. Concurrent session control
"""
import logging
import threading
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver

from config import get_settings

logger = logging.getLogger(__name__)


class CheckpointerError(Exception):
    """Base exception for checkpointer operations"""
    pass


class CheckpointerNotInitializedError(CheckpointerError):
    """Raised when checkpointer is accessed before initialization"""
    pass


class CheckpointerSetupError(CheckpointerError):
    """Raised when checkpointer setup fails"""
    pass


class CheckpointerManager:
    """
    PostgresSaver Checkpointer Manager for LangGraph
    
    Manages session state persistence using LangGraph's PostgresSaver.
    Provides automatic table setup and thread-safe access.
    
    Attributes:
        connection_string: PostgreSQL connection string
        checkpointer: PostgresSaver instance
        _is_setup: Whether tables have been created
    
    Usage:
        # Get checkpointer instance
        checkpointer = get_checkpointer()
        
        # Use with LangGraph compilation
        app = graph.compile(checkpointer=checkpointer)
        
        # Invoke with thread_id for session management
        config = {"configurable": {"thread_id": "session-123"}}
        result = await app.ainvoke(input_state, config)
        
        # Recover session state
        state = await app.aget_state(config)
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize Checkpointer Manager
        
        Args:
            connection_string: PostgreSQL connection string (default: from config)
        """
        settings = get_settings()
        self.connection_string = connection_string or settings.database_url
        self.checkpointer: Optional[PostgresSaver] = None
        self._is_setup = False
        self._lock = threading.RLock()
        
        logger.info(f"CheckpointerManager initialized with database: {settings.POSTGRES_DB}")
    
    def initialize(self) -> PostgresSaver:
        """
        Initialize the PostgresSaver checkpointer
        
        Creates the PostgresSaver instance using from_conn_string method.
        Does NOT automatically call setup() - call setup() separately if needed.
        
        Returns:
            PostgresSaver instance
            
        Raises:
            CheckpointerSetupError: If initialization fails
        """
        with self._lock:
            if self.checkpointer is not None:
                logger.debug("Checkpointer already initialized, returning existing instance")
                return self.checkpointer
            
            try:
                logger.info("Initializing PostgresSaver checkpointer...")
                
                # Create PostgresSaver using from_conn_string
                # Note: from_conn_string returns an async context manager in newer versions
                # We use the synchronous version for compatibility
                self.checkpointer = PostgresSaver.from_conn_string(self.connection_string)
                
                logger.info("PostgresSaver checkpointer initialized successfully")
                return self.checkpointer
                
            except Exception as e:
                logger.error(f"Failed to initialize PostgresSaver: {e}")
                raise CheckpointerSetupError(f"Failed to initialize PostgresSaver: {e}") from e
    
    def setup(self) -> None:
        """
        Create necessary tables for checkpoint storage
        
        Calls checkpointer.setup() to create the checkpoint tables in PostgreSQL.
        This includes:
        - checkpoint_writes
        - checkpoints
        - checkpoints_blobs
        - checkpoints_writes
        
        This method is idempotent - safe to call multiple times.
        
        Raises:
            CheckpointerNotInitializedError: If checkpointer not initialized
            CheckpointerSetupError: If setup fails
        """
        with self._lock:
            if self.checkpointer is None:
                raise CheckpointerNotInitializedError(
                    "Checkpointer not initialized. Call initialize() first."
                )
            
            if self._is_setup:
                logger.debug("Checkpointer tables already set up, skipping")
                return
            
            try:
                logger.info("Setting up checkpointer tables...")
                self.checkpointer.setup()
                self._is_setup = True
                logger.info("Checkpointer tables created successfully")
                
            except Exception as e:
                logger.error(f"Failed to setup checkpointer tables: {e}")
                raise CheckpointerSetupError(f"Failed to setup checkpointer tables: {e}") from e
    
    def get_checkpointer(self) -> PostgresSaver:
        """
        Get the PostgresSaver instance
        
        Returns the initialized checkpointer. Initializes if not already done.
        
        Returns:
            PostgresSaver instance
            
        Raises:
            CheckpointerSetupError: If initialization fails
        """
        with self._lock:
            if self.checkpointer is None:
                self.initialize()
            return self.checkpointer
    
    def is_ready(self) -> bool:
        """
        Check if checkpointer is ready for use
        
        Returns:
            True if checkpointer is initialized and tables are set up
        """
        with self._lock:
            return self.checkpointer is not None and self._is_setup
    
    def reset(self) -> None:
        """
        Reset the checkpointer (for testing)
        
        Clears the checkpointer instance and setup flag.
        Does NOT drop tables - use with caution.
        """
        with self._lock:
            self.checkpointer = None
            self._is_setup = False
            logger.info("Checkpointer reset")
    
    def __repr__(self) -> str:
        return (
            f"CheckpointerManager("
            f"initialized={self.checkpointer is not None}, "
            f"setup={self._is_setup})"
        )


# Global instance (lazy initialization)
_checkpointer_manager: Optional[CheckpointerManager] = None
_checkpointer_lock = threading.Lock()


def get_checkpointer_manager(
    connection_string: Optional[str] = None,
    force_new: bool = False
) -> CheckpointerManager:
    """
    Get the global checkpointer manager instance (singleton pattern)
    
    Args:
        connection_string: PostgreSQL connection string (default: from config)
        force_new: Force create a new instance (for testing)
        
    Returns:
        CheckpointerManager instance
    """
    global _checkpointer_manager
    
    with _checkpointer_lock:
        if _checkpointer_manager is None or force_new:
            _checkpointer_manager = CheckpointerManager(connection_string)
        return _checkpointer_manager


def get_checkpointer(
    connection_string: Optional[str] = None,
    auto_setup: bool = True
) -> PostgresSaver:
    """
    Factory method to get the PostgresSaver checkpointer
    
    This is the primary entry point for obtaining a checkpointer instance.
    It initializes the checkpointer and optionally sets up the tables.
    
    Args:
        connection_string: PostgreSQL connection string (default: from config)
        auto_setup: Automatically call setup() to create tables (default: True)
        
    Returns:
        PostgresSaver instance ready for use with LangGraph
        
    Raises:
        CheckpointerSetupError: If initialization or setup fails
        
    Example:
        # Get checkpointer for LangGraph compilation
        checkpointer = get_checkpointer()
        
        # Compile graph with checkpointer
        app = graph.compile(checkpointer=checkpointer)
        
        # Use with thread_id for session management
        config = {"configurable": {"thread_id": "user-session-123"}}
        result = await app.ainvoke(input_state, config)
    """
    manager = get_checkpointer_manager(connection_string)
    checkpointer = manager.get_checkpointer()
    
    if auto_setup and not manager.is_ready():
        manager.setup()
    
    return checkpointer


def reset_checkpointer() -> None:
    """
    Reset the global checkpointer manager (for testing)
    
    Clears the global instance. Does NOT drop database tables.
    """
    global _checkpointer_manager
    
    with _checkpointer_lock:
        if _checkpointer_manager is not None:
            _checkpointer_manager.reset()
        _checkpointer_manager = None


def get_db_session():
    """
    Get a database session for direct database operations
    
    Creates a SQLAlchemy session for operations that need direct database access
    (e.g., logging compliance checks, storing recommendations).
    
    Returns:
        SQLAlchemy Session instance
        
    Usage:
        session = get_db_session()
        try:
            # Use session
            session.add(some_object)
            session.commit()
        finally:
            session.close()
            
    Note:
        The caller is responsible for closing the session.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    settings = get_settings()
    
    # Create engine
    engine = create_engine(
        settings.database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Return session
    return SessionLocal()


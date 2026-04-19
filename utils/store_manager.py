"""
Store API Manager for LangGraph Cross-Session Data Persistence

This module provides PostgresStore-based Store API management for LangGraph,
enabling cross-session persistence of user profiles and key slots.

Key Features:
- PostgresStore initialization with connection string
- Automatic table setup for store storage
- Thread-safe singleton pattern
- User profile CRUD operations with namespace isolation
- Session metadata management

Architecture Decision:
Using Store API to manage user profiles because:
1. Cross-session persistence - user data persists across different sessions
2. Namespace isolation - clean separation of user data by user_id
3. Native LangGraph integration - works seamlessly with subgraphs
4. Simple key-value interface - easy to use and understand
"""
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any

from langgraph.store.postgres import PostgresStore

from config import get_settings

logger = logging.getLogger(__name__)


class StoreError(Exception):
    """Base exception for store operations"""
    pass


class StoreNotInitializedError(StoreError):
    """Raised when store is accessed before initialization"""
    pass


class StoreSetupError(StoreError):
    """Raised when store setup fails"""
    pass


class StoreManager:
    """
    PostgresStore Manager for LangGraph Store API
    
    Manages cross-session data persistence using LangGraph's PostgresStore.
    Provides automatic table setup and thread-safe access.
    
    Attributes:
        connection_string: PostgreSQL connection string
        store: PostgresStore instance
        _is_setup: Whether tables have been created
    
    Usage:
        # Get store instance
        store_manager = get_store_manager()
        store = store_manager.get_store()
        
        # Store user profile
        store_manager.put_user_profile(
            user_id="user_123",
            profile={"age": 30, "income_range": "medium_high"}
        )
        
        # Get user profile
        profile = store_manager.get_user_profile(user_id="user_123")
        
        # Update user profile (merge)
        store_manager.update_user_profile(
            user_id="user_123",
            updates={"risk_preference": "balanced"}
        )
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize Store Manager
        
        Args:
            connection_string: PostgreSQL connection string (default: from config)
        """
        settings = get_settings()
        self.connection_string = connection_string or settings.database_url
        self.store: Optional[PostgresStore] = None
        self._is_setup = False
        self._lock = threading.RLock()
        
        logger.info(f"StoreManager initialized with database: {settings.POSTGRES_DB}")
    
    def initialize(self) -> PostgresStore:
        """
        Initialize the PostgresStore
        
        Creates the PostgresStore instance using from_conn_string method.
        Does NOT automatically call setup() - call setup() separately if needed.
        
        Returns:
            PostgresStore instance
            
        Raises:
            StoreSetupError: If initialization fails
        """
        with self._lock:
            if self.store is not None:
                logger.debug("Store already initialized, returning existing instance")
                return self.store
            
            try:
                logger.info("Initializing PostgresStore...")
                
                # Create PostgresStore using from_conn_string
                self.store = PostgresStore.from_conn_string(self.connection_string)
                
                logger.info("PostgresStore initialized successfully")
                return self.store
                
            except Exception as e:
                logger.error(f"Failed to initialize PostgresStore: {e}")
                raise StoreSetupError(f"Failed to initialize PostgresStore: {e}") from e
    
    def setup(self) -> None:
        """
        Create necessary tables for store storage
        
        Calls store.setup() to create the store tables in PostgreSQL.
        This method is idempotent - safe to call multiple times.
        
        Raises:
            StoreNotInitializedError: If store not initialized
            StoreSetupError: If setup fails
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            if self._is_setup:
                logger.debug("Store tables already set up, skipping")
                return
            
            try:
                logger.info("Setting up store tables...")
                self.store.setup()
                self._is_setup = True
                logger.info("Store tables created successfully")
                
            except Exception as e:
                logger.error(f"Failed to setup store tables: {e}")
                raise StoreSetupError(f"Failed to setup store tables: {e}") from e
    
    def get_store(self) -> PostgresStore:
        """
        Get the PostgresStore instance
        
        Returns the initialized store. Initializes if not already done.
        
        Returns:
            PostgresStore instance
            
        Raises:
            StoreSetupError: If initialization fails
        """
        with self._lock:
            if self.store is None:
                self.initialize()
            return self.store
    
    def is_ready(self) -> bool:
        """
        Check if store is ready for use
        
        Returns:
            True if store is initialized and tables are set up
        """
        with self._lock:
            return self.store is not None and self._is_setup
    
    # ==================== User Profile Operations ====================
    
    def put_user_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        """
        Store user profile to Store API
        
        Stores the user profile in namespace=("users", user_id) with key="profile".
        This overwrites any existing profile data.
        
        Args:
            user_id: User identifier
            profile: User profile data (dict)
            
        Raises:
            StoreNotInitializedError: If store not initialized
            
        Example:
            store_manager.put_user_profile(
                user_id="user_123",
                profile={
                    "age": 30,
                    "income_range": "medium_high",
                    "risk_preference": "balanced"
                }
            )
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Storing user profile for user_id={user_id}")
                
                # Add timestamp for tracking
                profile_with_timestamp = {
                    **profile,
                    "updated_at": datetime.now().isoformat()
                }
                
                self.store.put(
                    namespace=("users", user_id),
                    key="profile",
                    value=profile_with_timestamp
                )
                
                logger.debug(f"User profile stored successfully for user_id={user_id}")
                
            except Exception as e:
                logger.error(f"Failed to store user profile: {e}")
                raise StoreError(f"Failed to store user profile: {e}") from e
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from Store API
        
        Retrieves the user profile from namespace=("users", user_id) with key="profile".
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile data (dict) or None if not found
            
        Raises:
            StoreNotInitializedError: If store not initialized
            
        Example:
            profile = store_manager.get_user_profile(user_id="user_123")
            if profile:
                print(f"User age: {profile.get('age')}")
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Retrieving user profile for user_id={user_id}")
                
                item = self.store.get(
                    namespace=("users", user_id),
                    key="profile"
                )
                
                if item:
                    logger.debug(f"User profile found for user_id={user_id}")
                    return item.value
                else:
                    logger.debug(f"No user profile found for user_id={user_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to get user profile: {e}")
                raise StoreError(f"Failed to get user profile: {e}") from e
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user profile with merge
        
        Merges the updates with existing profile data and stores the result.
        If no existing profile exists, creates a new one with the updates.
        
        Args:
            user_id: User identifier
            updates: Profile fields to update (dict)
            
        Returns:
            Updated user profile data (dict)
            
        Raises:
            StoreNotInitializedError: If store not initialized
            
        Example:
            updated_profile = store_manager.update_user_profile(
                user_id="user_123",
                updates={
                    "risk_preference": "aggressive",
                    "health_status": "good"
                }
            )
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Updating user profile for user_id={user_id}")
                
                # Get existing profile
                existing_profile = self.get_user_profile(user_id) or {}
                
                # Merge updates
                updated_profile = {**existing_profile, **updates}
                
                # Store updated profile
                self.put_user_profile(user_id, updated_profile)
                
                logger.debug(f"User profile updated successfully for user_id={user_id}")
                return updated_profile
                
            except StoreError:
                # Re-raise StoreError from put/get operations
                raise
            except Exception as e:
                logger.error(f"Failed to update user profile: {e}")
                raise StoreError(f"Failed to update user profile: {e}") from e
    
    def delete_user_profile(self, user_id: str) -> bool:
        """
        Delete user profile from Store API
        
        Removes the user profile from namespace=("users", user_id).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if profile was deleted, False if profile didn't exist
            
        Raises:
            StoreNotInitializedError: If store not initialized
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Deleting user profile for user_id={user_id}")
                
                # Check if profile exists
                existing = self.get_user_profile(user_id)
                if not existing:
                    logger.debug(f"No profile to delete for user_id={user_id}")
                    return False
                
                # Delete by storing None or using delete if available
                # Note: PostgresStore may not have a delete method, so we use put with empty
                self.store.put(
                    namespace=("users", user_id),
                    key="profile",
                    value=None
                )
                
                logger.debug(f"User profile deleted for user_id={user_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete user profile: {e}")
                raise StoreError(f"Failed to delete user profile: {e}") from e
    
    # ==================== Session Metadata Operations ====================
    
    def put_session_metadata(
        self, 
        session_id: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """
        Store session metadata to Store API
        
        Stores session metadata in namespace=("sessions", session_id) with key="metadata".
        This is useful for tracking session-level information across sessions.
        
        Args:
            session_id: Session identifier
            metadata: Session metadata (dict)
            
        Raises:
            StoreNotInitializedError: If store not initialized
            
        Example:
            store_manager.put_session_metadata(
                session_id="session_456",
                metadata={
                    "user_id": "user_123",
                    "started_at": "2024-01-15T10:00:00",
                    "status": "active"
                }
            )
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Storing session metadata for session_id={session_id}")
                
                # Add timestamp for tracking
                metadata_with_timestamp = {
                    **metadata,
                    "updated_at": datetime.now().isoformat()
                }
                
                self.store.put(
                    namespace=("sessions", session_id),
                    key="metadata",
                    value=metadata_with_timestamp
                )
                
                logger.debug(f"Session metadata stored for session_id={session_id}")
                
            except Exception as e:
                logger.error(f"Failed to store session metadata: {e}")
                raise StoreError(f"Failed to store session metadata: {e}") from e
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata from Store API
        
        Retrieves session metadata from namespace=("sessions", session_id) with key="metadata".
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session metadata (dict) or None if not found
            
        Raises:
            StoreNotInitializedError: If store not initialized
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Retrieving session metadata for session_id={session_id}")
                
                item = self.store.get(
                    namespace=("sessions", session_id),
                    key="metadata"
                )
                
                if item:
                    logger.debug(f"Session metadata found for session_id={session_id}")
                    return item.value
                else:
                    logger.debug(f"No session metadata found for session_id={session_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to get session metadata: {e}")
                raise StoreError(f"Failed to get session metadata: {e}") from e
    
    def update_session_metadata(
        self, 
        session_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update session metadata with merge
        
        Merges the updates with existing session metadata and stores the result.
        
        Args:
            session_id: Session identifier
            updates: Metadata fields to update (dict)
            
        Returns:
            Updated session metadata (dict)
            
        Raises:
            StoreNotInitializedError: If store not initialized
        """
        with self._lock:
            if self.store is None:
                raise StoreNotInitializedError(
                    "Store not initialized. Call initialize() first."
                )
            
            try:
                logger.debug(f"Updating session metadata for session_id={session_id}")
                
                # Get existing metadata
                existing_metadata = self.get_session_metadata(session_id) or {}
                
                # Merge updates
                updated_metadata = {**existing_metadata, **updates}
                
                # Store updated metadata
                self.put_session_metadata(session_id, updated_metadata)
                
                logger.debug(f"Session metadata updated for session_id={session_id}")
                return updated_metadata
                
            except StoreError:
                # Re-raise StoreError from put/get operations
                raise
            except Exception as e:
                logger.error(f"Failed to update session metadata: {e}")
                raise StoreError(f"Failed to update session metadata: {e}") from e
    
    # ==================== Utility Methods ====================
    
    def reset(self) -> None:
        """
        Reset the store manager (for testing)
        
        Clears the store instance and setup flag.
        Does NOT drop tables - use with caution.
        """
        with self._lock:
            self.store = None
            self._is_setup = False
            logger.info("Store manager reset")
    
    def __repr__(self) -> str:
        return (
            f"StoreManager("
            f"initialized={self.store is not None}, "
            f"setup={self._is_setup})"
        )


# Global instance (lazy initialization)
_store_manager: Optional[StoreManager] = None
_store_lock = threading.Lock()


def get_store_manager(
    connection_string: Optional[str] = None,
    force_new: bool = False
) -> StoreManager:
    """
    Get the global store manager instance (singleton pattern)
    
    Args:
        connection_string: PostgreSQL connection string (default: from config)
        force_new: Force create a new instance (for testing)
        
    Returns:
        StoreManager instance
    """
    global _store_manager
    
    with _store_lock:
        if _store_manager is None or force_new:
            _store_manager = StoreManager(connection_string)
        return _store_manager


def get_store(
    connection_string: Optional[str] = None,
    auto_setup: bool = True
) -> PostgresStore:
    """
    Factory method to get the PostgresStore instance
    
    This is the primary entry point for obtaining a store instance.
    It initializes the store and optionally sets up the tables.
    
    Args:
        connection_string: PostgreSQL connection string (default: from config)
        auto_setup: Automatically call setup() to create tables (default: True)
        
    Returns:
        PostgresStore instance ready for use with LangGraph
        
    Raises:
        StoreSetupError: If initialization or setup fails
        
    Example:
        # Get store for LangGraph subgraphs
        store = get_store()
        
        # Use in Profile Subgraph to store slots
        store.put(
            namespace=("users", user_id),
            key="profile",
            value={"age": 30, "risk_preference": "balanced"}
        )
        
        # Use in Recommendation Subgraph to load profile
        item = store.get(namespace=("users", user_id), key="profile")
        profile = item.value if item else {}
    """
    manager = get_store_manager(connection_string)
    store = manager.get_store()
    
    if auto_setup and not manager.is_ready():
        manager.setup()
    
    return store


def reset_store_manager() -> None:
    """
    Reset the global store manager (for testing)
    
    Clears the global instance. Does NOT drop database tables.
    """
    global _store_manager
    
    with _store_lock:
        if _store_manager is not None:
            _store_manager.reset()
        _store_manager = None

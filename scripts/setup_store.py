"""
Setup script for LangGraph Store API tables

This script initializes the PostgresStore tables required for
cross-session user profile persistence.

Usage:
    python scripts/setup_store.py [--verify-only]

Options:
    --verify-only    Only verify existing tables, don't create new ones
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from config import get_settings
from utils.store_manager import get_store_manager, reset_store_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_existing_tables(engine) -> set:
    """Get set of existing tables in the database"""
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def verify_store_tables_compatibility(engine) -> dict:
    """
    Verify that Store tables are compatible with existing schema
    
    Returns:
        dict with verification results
    """
    results = {
        "existing_tables": [],
        "store_tables": [],
        "conflicts": [],
        "compatible": True
    }
    
    # Get existing tables
    existing_tables = get_existing_tables(engine)
    results["existing_tables"] = sorted(list(existing_tables))
    
    # LangGraph PostgresStore creates these tables:
    # - store (main storage table)
    # Note: The actual table name may vary based on LangGraph version
    expected_store_tables = ["store"]
    
    # Check for conflicts
    for table in expected_store_tables:
        if table in existing_tables:
            # Table already exists - check if it's a Store table
            results["store_tables"].append(table)
            logger.info(f"Store table '{table}' already exists")
        else:
            results["store_tables"].append(f"{table} (to be created)")
    
    # Check for potential naming conflicts
    # Store uses 'store' table which shouldn't conflict with our schema
    conflicting_tables = [t for t in expected_store_tables if t in existing_tables]
    
    if conflicting_tables:
        # Verify these are actually Store tables by checking columns
        with engine.connect() as conn:
            for table in conflicting_tables:
                try:
                    result = conn.execute(text(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position
                    """))
                    columns = {row[0]: row[1] for row in result}
                    
                    # Store table should have these columns:
                    # namespace, key, value, created_at, updated_at
                    expected_columns = {"namespace", "key", "value", "created_at", "updated_at"}
                    actual_columns = set(columns.keys())
                    
                    if expected_columns.issubset(actual_columns):
                        logger.info(f"Table '{table}' has expected Store columns")
                    else:
                        logger.warning(
                            f"Table '{table}' exists but may not be a Store table. "
                            f"Missing columns: {expected_columns - actual_columns}"
                        )
                        results["conflicts"].append(table)
                        results["compatible"] = False
                        
                except Exception as e:
                    logger.error(f"Error checking table '{table}': {e}")
                    results["conflicts"].append(table)
                    results["compatible"] = False
    
    return results


def setup_store_tables(verify_only: bool = False) -> bool:
    """
    Set up Store tables in the database
    
    Args:
        verify_only: If True, only verify without creating tables
        
    Returns:
        True if setup successful or verification passed
    """
    settings = get_settings()
    
    logger.info(f"Connecting to database: {settings.POSTGRES_DB}")
    logger.info(f"Database host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    
    # Create engine for verification
    engine = create_engine(settings.database_url)
    
    # Verify compatibility first
    logger.info("Verifying Store table compatibility...")
    verification = verify_store_tables_compatibility(engine)
    
    print("\n" + "=" * 60)
    print("Store Table Verification Results")
    print("=" * 60)
    print(f"\nExisting tables ({len(verification['existing_tables'])}):")
    for table in verification['existing_tables'][:10]:  # Show first 10
        print(f"  - {table}")
    if len(verification['existing_tables']) > 10:
        print(f"  ... and {len(verification['existing_tables']) - 10} more")
    
    print(f"\nStore tables: {verification['store_tables']}")
    
    if verification['conflicts']:
        print(f"\n⚠️  Conflicts detected: {verification['conflicts']}")
        print("   Please resolve conflicts before proceeding.")
        return False
    
    if not verification['compatible']:
        print("\n❌ Store tables are NOT compatible with existing schema")
        return False
    
    print("\n✅ Store tables are compatible with existing schema")
    
    if verify_only:
        logger.info("Verify-only mode: skipping table creation")
        return True
    
    # Now set up the Store tables
    logger.info("\nSetting up Store tables...")
    
    try:
        # Reset any existing store manager
        reset_store_manager()
        
        # Get store manager and initialize
        store_manager = get_store_manager()
        
        # Initialize the store
        logger.info("Initializing PostgresStore...")
        store = store_manager.initialize()
        logger.info("PostgresStore initialized successfully")
        
        # Setup tables
        logger.info("Creating Store tables...")
        store_manager.setup()
        logger.info("Store tables created successfully")
        
        # Verify setup
        if store_manager.is_ready():
            print("\n✅ Store setup completed successfully!")
            print(f"   Store is ready: {store_manager}")
            return True
        else:
            print("\n❌ Store setup failed - store not ready")
            return False
            
    except Exception as e:
        logger.error(f"Failed to setup Store tables: {e}")
        print(f"\n❌ Store setup failed: {e}")
        return False
    finally:
        # Clean up
        engine.dispose()


def test_store_operations() -> bool:
    """
    Test basic Store operations to verify functionality
    
    Returns:
        True if all tests pass
    """
    logger.info("\nTesting Store operations...")
    
    try:
        from utils.store_manager import get_store
        
        # Get store with auto_setup=False (should already be set up)
        store = get_store(auto_setup=False)
        
        # Test data
        test_user_id = "test_user_setup_script"
        test_profile = {
            "age": 30,
            "income_range": "medium_high",
            "risk_preference": "balanced",
            "family_structure": "married_with_children"
        }
        
        # Test put
        logger.info("Testing store.put()...")
        store.put(
            namespace=("users", test_user_id),
            key="profile",
            value=test_profile
        )
        logger.info("✅ store.put() successful")
        
        # Test get
        logger.info("Testing store.get()...")
        item = store.get(
            namespace=("users", test_user_id),
            key="profile"
        )
        
        if item and item.value:
            logger.info(f"✅ store.get() successful: {item.value}")
            
            # Verify data integrity
            if item.value.get("age") == test_profile["age"]:
                logger.info("✅ Data integrity verified")
            else:
                logger.error("❌ Data integrity check failed")
                return False
        else:
            logger.error("❌ store.get() returned None")
            return False
        
        # Clean up test data
        logger.info("Cleaning up test data...")
        store.put(
            namespace=("users", test_user_id),
            key="profile",
            value=None
        )
        
        print("\n✅ All Store operations tested successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Store operation test failed: {e}")
        print(f"\n❌ Store operation test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup LangGraph Store API tables"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing tables, don't create new ones"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run Store operation tests after setup"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("LangGraph Store API Setup")
    print("=" * 60)
    
    # Setup tables
    success = setup_store_tables(verify_only=args.verify_only)
    
    if not success:
        sys.exit(1)
    
    # Run tests if requested
    if args.test and not args.verify_only:
        test_success = test_store_operations()
        if not test_success:
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Setup completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

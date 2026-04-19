# Database Setup Guide

## Overview

This document describes the PostgreSQL database schema for the Insurance Recommendation Agent system.

## Database Schema

The system uses PostgreSQL as the primary relational database with the following tables:

### User Management Tables

#### 1. `users`
Stores basic user information.

**Columns:**
- `user_id` (VARCHAR(50), PK): Unique user identifier
- `username` (VARCHAR(100)): Username
- `email` (VARCHAR(255), UNIQUE): Email address
- `phone` (VARCHAR(20)): Phone number
- `created_at` (TIMESTAMP): Account creation time
- `updated_at` (TIMESTAMP): Last update time
- `last_login_at` (TIMESTAMP): Last login time

**Indexes:**
- `idx_users_email` on `email`
- `idx_users_phone` on `phone`

#### 2. `user_profiles`
Stores detailed user profile information.

**Columns:**
- `profile_id` (VARCHAR(50), PK): Profile identifier
- `user_id` (VARCHAR(50), FK): References `users.user_id`
- `age` (INTEGER): User age
- `occupation` (VARCHAR(100)): Occupation
- `marital_status` (ENUM): Marital status (single, married, divorced, widowed)
- `has_children` (BOOLEAN): Whether user has children
- `children_count` (INTEGER): Number of children
- `has_dependents` (BOOLEAN): Whether user has dependents
- `dependents_count` (INTEGER): Number of dependents
- `family_size` (INTEGER): Family size
- `income_range` (ENUM): Income range (low, medium_low, medium, medium_high, high)
- `annual_income` (FLOAT): Specific annual income
- `risk_preference` (ENUM): Risk preference (conservative, balanced, aggressive)
- `risk_score` (FLOAT): Risk assessment score
- `health_status` (ENUM): Health status (excellent, good, fair, poor)
- `has_medical_history` (BOOLEAN): Whether user has medical history
- `medical_conditions` (ARRAY): List of medical conditions
- `city` (VARCHAR(50)): City
- `province` (VARCHAR(50)): Province
- `created_at` (TIMESTAMP): Creation time
- `updated_at` (TIMESTAMP): Last update time

**Indexes:**
- `idx_user_profiles_user_id` on `user_id`
- `idx_user_profiles_age` on `age`
- `idx_user_profiles_income_range` on `income_range`

#### 3. `existing_coverage`
Stores user's existing insurance coverage.

**Columns:**
- `coverage_id` (VARCHAR(50), PK): Coverage identifier
- `profile_id` (VARCHAR(50), FK): References `user_profiles.profile_id`
- `product_id` (VARCHAR(50)): Product identifier
- `product_name` (VARCHAR(200)): Product name
- `product_type` (VARCHAR(50)): Product type
- `coverage_amount` (FLOAT): Coverage amount
- `premium` (FLOAT): Premium amount
- `coverage_scope` (ARRAY): Coverage scope
- `purchase_date` (TIMESTAMP): Purchase date
- `coverage_start_date` (TIMESTAMP): Coverage start date
- `coverage_end_date` (TIMESTAMP): Coverage end date
- `is_active` (BOOLEAN): Whether coverage is active
- `created_at` (TIMESTAMP): Creation time
- `updated_at` (TIMESTAMP): Last update time

**Indexes:**
- `idx_existing_coverage_profile_id` on `profile_id`
- `idx_existing_coverage_product_type` on `product_type`
- `idx_existing_coverage_is_active` on `is_active`

### Conversation Tables

#### 4. `conversation_sessions`
Stores conversation session information.

**Columns:**
- `session_id` (VARCHAR(50), PK): Session identifier
- `user_id` (VARCHAR(50), FK): References `users.user_id`
- `status` (ENUM): Session status (active, background, completed, abandoned, archived)
- `background_mode` (BOOLEAN): Whether session is running in background
- `created_at` (TIMESTAMP): Creation time
- `last_activity_at` (TIMESTAMP): Last activity time
- `completed_at` (TIMESTAMP): Completion time
- `turn_count` (INTEGER): Number of conversation turns
- `total_messages` (INTEGER): Total message count
- `slots` (JSON): Extracted slot data
- `user_preferences` (JSON): User preferences

**Indexes:**
- `idx_conversation_sessions_user_id` on `user_id`
- `idx_conversation_sessions_status` on `status`
- `idx_conversation_sessions_created_at` on `created_at`
- `idx_conversation_sessions_last_activity` on `last_activity_at`

#### 5. `conversation_messages`
Stores individual conversation messages.

**Columns:**
- `message_id` (VARCHAR(50), PK): Message identifier
- `session_id` (VARCHAR(50), FK): References `conversation_sessions.session_id`
- `role` (ENUM): Message role (user, assistant, system)
- `content` (TEXT): Message content
- `intent` (VARCHAR(50)): User intent
- `extracted_slots` (JSON): Extracted slots from message
- `agent_name` (VARCHAR(50)): Agent that generated the message
- `thinking_process` (TEXT): Agent's thinking process
- `timestamp` (TIMESTAMP): Message timestamp

**Indexes:**
- `idx_conversation_messages_session_id` on `session_id`
- `idx_conversation_messages_timestamp` on `timestamp`
- `idx_conversation_messages_role` on `role`

### Product Tables

#### 6. `insurance_products`
Stores insurance product information.

**Columns:**
- `product_id` (VARCHAR(50), PK): Product identifier
- `product_name` (VARCHAR(200)): Product name
- `product_type` (VARCHAR(50)): Product type
- `provider` (VARCHAR(100)): Insurance provider
- `coverage_scope` (ARRAY): Coverage scope
- `coverage_amount_min` (FLOAT): Minimum coverage amount
- `coverage_amount_max` (FLOAT): Maximum coverage amount
- `exclusions` (ARRAY): Exclusions
- `premium_min` (FLOAT): Minimum premium
- `premium_max` (FLOAT): Maximum premium
- `payment_period` (ARRAY): Payment period options
- `coverage_period` (ARRAY): Coverage period options
- `age_min` (INTEGER): Minimum age
- `age_max` (INTEGER): Maximum age
- `occupation_restrictions` (ARRAY): Occupation restrictions
- `health_requirements` (ARRAY): Health requirements
- `region_restrictions` (ARRAY): Region restrictions
- `features` (ARRAY): Product features
- `advantages` (ARRAY): Product advantages
- `suitable_for` (ARRAY): Suitable for
- `claim_process` (TEXT): Claim process
- `waiting_period_days` (INTEGER): Waiting period in days
- `deductible` (FLOAT): Deductible amount
- `is_available` (BOOLEAN): Whether product is available
- `is_featured` (BOOLEAN): Whether product is featured
- `embedding` (ARRAY): Product embedding vector for RAG
- `created_at` (TIMESTAMP): Creation time
- `updated_at` (TIMESTAMP): Last update time
- `version` (INTEGER): Version number

**Indexes:**
- `idx_insurance_products_product_type` on `product_type`
- `idx_insurance_products_provider` on `provider`
- `idx_insurance_products_is_available` on `is_available`
- `idx_insurance_products_age_range` on `age_min, age_max`
- `idx_insurance_products_premium_range` on `premium_min, premium_max`

### Recommendation Tables

#### 7. `recommendations`
Stores recommendation records.

**Columns:**
- `recommendation_id` (VARCHAR(50), PK): Recommendation identifier
- `session_id` (VARCHAR(50), FK): References `conversation_sessions.session_id`
- `product_id` (VARCHAR(50), FK): References `insurance_products.product_id`
- `rank` (INTEGER): Recommendation rank
- `match_score` (FLOAT): Match score
- `confidence_score` (FLOAT): Confidence score
- `explanation` (TEXT): Recommendation explanation
- `match_dimensions` (JSON): Match scores by dimension
- `why_suitable` (ARRAY): Why suitable for user
- `key_benefits` (ARRAY): Key benefits
- `compliance_passed` (BOOLEAN): Whether compliance check passed
- `compliance_issues` (ARRAY): Compliance issues
- `recommended_at` (TIMESTAMP): Recommendation time

**Indexes:**
- `idx_recommendations_session_id` on `session_id`
- `idx_recommendations_product_id` on `product_id`
- `idx_recommendations_recommended_at` on `recommended_at`
- `idx_recommendations_match_score` on `match_score`

#### 8. `user_feedback`
Stores user feedback on recommendations.

**Columns:**
- `feedback_id` (VARCHAR(50), PK): Feedback identifier
- `recommendation_id` (VARCHAR(50), FK): References `recommendations.recommendation_id`
- `satisfaction` (VARCHAR(20)): Satisfaction level (positive/negative/neutral)
- `reason` (TEXT): Feedback reason
- `rating` (INTEGER): Rating (1-5)
- `helpful` (BOOLEAN): Whether helpful
- `meets_needs` (BOOLEAN): Whether meets needs
- `comments` (TEXT): Additional comments
- `created_at` (TIMESTAMP): Creation time

**Indexes:**
- `idx_user_feedback_recommendation_id` on `recommendation_id`
- `idx_user_feedback_satisfaction` on `satisfaction`
- `idx_user_feedback_created_at` on `created_at`

### Compliance and Monitoring Tables

#### 9. `compliance_logs`
Stores compliance check logs.

**Columns:**
- `log_id` (VARCHAR(50), PK): Log identifier
- `session_id` (VARCHAR(50)): Session identifier
- `product_id` (VARCHAR(50)): Product identifier
- `user_id` (VARCHAR(50)): User identifier
- `check_type` (VARCHAR(50)): Check type
- `check_result` (ENUM): Check result (passed, failed, warning, manual_review)
- `eligible` (BOOLEAN): Whether eligible
- `check_description` (TEXT): Check description
- `reason` (TEXT): Failure reason
- `checked_value` (VARCHAR(200)): Checked value
- `expected_value` (VARCHAR(200)): Expected value
- `checks_detail` (JSON): Detailed checks
- `failed_checks` (ARRAY): Failed checks
- `recommendations` (ARRAY): Recommendations
- `checked_at` (TIMESTAMP): Check time

**Indexes:**
- `idx_compliance_logs_session_id` on `session_id`
- `idx_compliance_logs_product_id` on `product_id`
- `idx_compliance_logs_user_id` on `user_id`
- `idx_compliance_logs_check_result` on `check_result`
- `idx_compliance_logs_checked_at` on `checked_at`

#### 10. `quality_metrics`
Stores quality metrics for sessions.

**Columns:**
- `metric_id` (VARCHAR(50), PK): Metric identifier
- `session_id` (VARCHAR(50)): Session identifier
- `intent_recognition_accuracy` (FLOAT): Intent recognition accuracy
- `slot_fill_rate` (FLOAT): Slot fill rate
- `conversation_completion_rate` (FLOAT): Conversation completion rate
- `recommendation_confidence` (FLOAT): Recommendation confidence
- `recommendation_diversity` (FLOAT): Recommendation diversity
- `compliance_pass_rate` (FLOAT): Compliance pass rate
- `total_turns` (INTEGER): Total conversation turns
- `total_tokens` (INTEGER): Total tokens used
- `response_time_ms` (INTEGER): Response time in milliseconds
- `user_satisfaction` (VARCHAR(20)): User satisfaction
- `quality_score` (FLOAT): Overall quality score
- `created_at` (TIMESTAMP): Creation time

**Indexes:**
- `idx_quality_metrics_session_id` on `session_id`
- `idx_quality_metrics_created_at` on `created_at`
- `idx_quality_metrics_quality_score` on `quality_score`

#### 11. `archived_sessions`
Stores archived session data.

**Columns:**
- `archive_id` (VARCHAR(50), PK): Archive identifier
- `session_id` (VARCHAR(50)): Original session identifier
- `user_id` (VARCHAR(50)): User identifier
- `session_summary` (TEXT): Session summary
- `key_intents` (ARRAY): Key intents
- `extracted_profile` (JSON): Extracted user profile
- `recommended_products` (ARRAY): Recommended product IDs
- `user_feedback_summary` (TEXT): User feedback summary
- `full_conversation` (JSON): Full conversation data
- `final_state` (JSON): Final state
- `session_embedding` (ARRAY): Session embedding vector
- `session_created_at` (TIMESTAMP): Session creation time
- `session_completed_at` (TIMESTAMP): Session completion time
- `archived_at` (TIMESTAMP): Archive time

**Indexes:**
- `idx_archived_sessions_session_id` on `session_id`
- `idx_archived_sessions_user_id` on `user_id`
- `idx_archived_sessions_archived_at` on `archived_at`

## Setup Instructions

### Prerequisites

- PostgreSQL 14 or higher
- Python 3.11 or higher
- uv package manager

### Step 1: Install PostgreSQL

Install PostgreSQL on your system:

**Windows:**
```bash
# Download and install from https://www.postgresql.org/download/windows/
```

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install postgresql-14
sudo systemctl start postgresql
```

### Step 2: Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE insurance_agent;

# Create user (optional)
CREATE USER insurance_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE insurance_agent TO insurance_user;

# Exit
\q
```

### Step 3: Configure Environment Variables

Copy `.env.example` to `.env` and update the database settings:

```bash
cp .env.example .env
```

Edit `.env`:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=insurance_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### Step 4: Run Migrations

```bash
# Run Alembic migrations to create tables
uv run alembic upgrade head
```

### Step 5: Verify Setup

```bash
# Connect to database
psql -U postgres -d insurance_agent

# List tables
\dt

# You should see all 11 tables listed
```

## Migration Management

### Create a New Migration

```bash
uv run alembic revision -m "description_of_changes"
```

### Apply Migrations

```bash
# Upgrade to latest
uv run alembic upgrade head

# Upgrade to specific revision
uv run alembic upgrade <revision_id>
```

### Rollback Migrations

```bash
# Downgrade one revision
uv run alembic downgrade -1

# Downgrade to specific revision
uv run alembic downgrade <revision_id>

# Downgrade all
uv run alembic downgrade base
```

### View Migration History

```bash
uv run alembic history
uv run alembic current
```

## Database Maintenance

### Backup

```bash
# Backup database
pg_dump -U postgres insurance_agent > backup.sql

# Backup with compression
pg_dump -U postgres insurance_agent | gzip > backup.sql.gz
```

### Restore

```bash
# Restore from backup
psql -U postgres insurance_agent < backup.sql

# Restore from compressed backup
gunzip -c backup.sql.gz | psql -U postgres insurance_agent
```

### Vacuum and Analyze

```bash
# Connect to database
psql -U postgres -d insurance_agent

# Vacuum and analyze
VACUUM ANALYZE;
```

## Troubleshooting

### Connection Issues

If you can't connect to PostgreSQL:

1. Check if PostgreSQL is running:
   ```bash
   # Windows
   Get-Service postgresql*
   
   # macOS/Linux
   sudo systemctl status postgresql
   ```

2. Check `pg_hba.conf` for authentication settings

3. Verify firewall settings allow connections on port 5432

### Migration Errors

If migrations fail:

1. Check database connection settings in `.env`
2. Verify user has necessary permissions
3. Check Alembic logs for specific errors
4. Try rolling back and reapplying migrations

### Performance Issues

If queries are slow:

1. Check if indexes are created properly
2. Run `VACUUM ANALYZE` to update statistics
3. Monitor query performance with `EXPLAIN ANALYZE`
4. Consider adding additional indexes for frequently queried columns

## LangGraph Store API Tables

The system uses LangGraph's Store API for cross-session user profile persistence. The Store API creates its own tables separate from the application schema.

### Store Table

**Table Name:** `store`

**Purpose:** Cross-session persistence of user profiles and key slots using LangGraph's PostgresStore.

**Columns:**
- `namespace` (TEXT[]): Namespace tuple for organizing data (e.g., `["users", "user_123"]`)
- `key` (TEXT): Key within the namespace (e.g., `"profile"`)
- `value` (JSONB): Stored data as JSON
- `created_at` (TIMESTAMP): Creation timestamp
- `updated_at` (TIMESTAMP): Last update timestamp

**Namespace Structure:**
- User profiles: `namespace=("users", user_id)`, `key="profile"`
- Session metadata: `namespace=("sessions", session_id)`, `key="metadata"`

**Setup:**

The Store tables are created automatically by the `setup_store.py` script:

```bash
# Setup Store tables
uv run python scripts/setup_store.py

# Verify Store tables only (without creating)
uv run python scripts/setup_store.py --verify-only

# Setup and test Store operations
uv run python scripts/setup_store.py --test
```

**Compatibility:**

The Store table (`store`) does not conflict with existing application tables:
- Uses separate table name
- Uses namespace-based isolation
- Provides key-value interface for cross-session data
- Complements (not replaces) the existing `user_profiles` table

**Usage Example:**

```python
from utils.store_manager import get_store

# Get store instance
store = get_store()

# Store user profile
store.put(
    namespace=("users", "user_123"),
    key="profile",
    value={
        "age": 30,
        "income_range": "medium_high",
        "risk_preference": "balanced"
    }
)

# Retrieve user profile
item = store.get(namespace=("users", "user_123"), key="profile")
if item:
    profile = item.value
```

## LangGraph Checkpointer Tables

The system uses LangGraph's PostgresSaver for session state persistence. The Checkpointer creates its own tables for managing conversation state.

### Checkpointer Tables

**Tables Created:**
- `checkpoint_writes`
- `checkpoints`
- `checkpoints_blobs`

**Purpose:** Session state persistence and recovery, time-travel debugging support.

**Setup:**

The Checkpointer tables are created automatically when initializing the checkpointer:

```python
from utils.checkpointer import get_checkpointer

# Get checkpointer (auto-setup enabled by default)
checkpointer = get_checkpointer()
```

Or manually:

```bash
# Run the checkpointer setup
uv run python -c "from utils.checkpointer import get_checkpointer; get_checkpointer()"
```

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [LangGraph Store API Documentation](https://langchain-ai.github.io/langgraph/reference/store/)
- [LangGraph Checkpointer Documentation](https://langchain-ai.github.io/langgraph/reference/checkpoints/)

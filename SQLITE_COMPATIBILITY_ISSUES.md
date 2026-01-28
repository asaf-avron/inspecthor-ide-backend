# SQLite Compatibility Issues

This document identifies potential issues when switching from PostgreSQL to SQLite.

## ✅ Fixed Issues

1. **UUID String Conversion in Auth** (`api/auth.py`)
   - **Issue**: JWT tokens contain UUIDs as strings, but SQLite requires UUID objects for queries
   - **Status**: ✅ Fixed in `get_current_user()` and `refresh_access_token()`
   - **Solution**: Convert string UUIDs to `uuid.UUID` objects before database queries

## ⚠️ Remaining Issues

### 1. **PostgreSQL-Specific Partial Indexes** (`api/database.py`)

**Location**: Lines 130 and 138

**Problem**: 
```python
Index(
    'ix_projects_user_id_name_lower',
    user_id,
    func.lower(name),
    unique=True,
    postgresql_where=Column('user_id').isnot(None)  # ❌ PostgreSQL-specific
)
```

**Impact**: SQLite doesn't support `postgresql_where` parameter. This will cause an error when creating the database schema.

**Solution Options**:
- Option A: Remove `postgresql_where` for SQLite compatibility (loses partial index optimization)
- Option B: Use SQLAlchemy's dialect-specific index creation
- Option C: Create separate index definitions for PostgreSQL vs SQLite

**Recommended Fix**:
```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Create indexes conditionally based on database type
if DATABASE_URL.startswith('sqlite'):
    # SQLite: Create regular unique index (no WHERE clause)
    __table_args__ = (
        Index('ix_projects_user_id_name_lower', user_id, func.lower(name), unique=True),
        Index('ix_projects_api_key_hash_name_lower', api_key_hash, func.lower(name), unique=True),
        Index('ix_projects_updated_at', updated_at.desc()),
    )
else:
    # PostgreSQL: Use partial indexes
    __table_args__ = (
        Index(
            'ix_projects_user_id_name_lower',
            user_id,
            func.lower(name),
            unique=True,
            postgresql_where=Column('user_id').isnot(None)
        ),
        Index(
            'ix_projects_api_key_hash_name_lower',
            api_key_hash,
            func.lower(name),
            unique=True,
            postgresql_where=Column('api_key_hash').isnot(None)
        ),
        Index('ix_projects_updated_at', updated_at.desc()),
    )
```

### 2. **String UUID Parameters in Route Handlers**

**Locations**:
- `api/files.py` line 197: `DBFile.file_id == file_id` (file_id is str from path param)
- `api/files.py` line 302: `DBFile.file_id == file_id` (file_id is str from path param)
- `api/files.py` line 383: `DBFile.file_id == file_id` (file_id is str from path param)
- `api/projects.py` line 228: `DBProject.project_id == project_id` (project_id is str from path param)

**Problem**: Path parameters come as strings, but SQLite UUID columns require UUID objects for queries.

**Impact**: Same `AttributeError: 'str' object has no attribute 'hex'` error as auth.py had.

**Solution**: Convert string UUIDs to UUID objects before queries:
```python
import uuid

# In route handlers, convert before querying
try:
    file_id_uuid = uuid.UUID(file_id) if isinstance(file_id, str) else file_id
except ValueError:
    raise HTTPException(status_code=400, detail="Invalid file ID format")

db_file = db.query(DBFile).filter(DBFile.file_id == file_id_uuid).first()
```

**Files to Fix**:
- `api/files.py`: Lines 197, 302, 383
- `api/projects.py`: Line 228 (and check `project_service.py` line 228)
- `api/services/project_service.py`: Check all `project_id` usages

### 3. **Enum Types**

**Status**: ✅ Should be fine
- SQLAlchemy automatically converts PostgreSQL enums to VARCHAR in SQLite
- No action needed unless issues arise

### 4. **Index with DESC Ordering**

**Location**: `api/database.py` line 141

**Status**: ✅ Should be fine
- SQLAlchemy handles `updated_at.desc()` correctly for SQLite
- No action needed

### 5. **CASCADE Deletes**

**Status**: ✅ Should be fine
- SQLite supports CASCADE deletes
- No action needed

## Testing Recommendations

1. **Create Integration Test for Index Creation**:
   ```python
   def test_database_schema_creation_with_sqlite():
       """Test that database schema can be created with SQLite"""
       from api.database import init_db, DATABASE_URL
       import os
       
       # Temporarily switch to SQLite
       original_url = os.environ.get('DATABASE_URL')
       os.environ['DATABASE_URL'] = 'sqlite:///./test_schema.db'
       
       try:
           init_db()  # Should not raise exception
       finally:
           if original_url:
               os.environ['DATABASE_URL'] = original_url
           else:
               os.environ.pop('DATABASE_URL', None)
   ```

2. **Test UUID String Conversion**:
   - Test all route handlers that accept UUID path parameters
   - Verify they work with SQLite

3. **Test Partial Index Behavior**:
   - Verify that unique constraints work correctly without partial indexes
   - Test that NULL values are handled correctly

## Priority

1. **High**: Fix `postgresql_where` indexes (will prevent database creation)
2. **High**: Fix string UUID queries in route handlers (will cause runtime errors)
3. **Low**: Monitor enum behavior (should work but verify)

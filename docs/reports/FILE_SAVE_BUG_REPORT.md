# Bug Report: File Save Fails with icontract ViolationError

## Date: 2026-01-29

## Summary

When saving a file via POST `/api/files/save`, the request fails with a 500 Internal Server Error and an `icontract.ViolationError` instead of a proper 404 "Project not found" error.

## Error Message

```
ViolationError: Preconditions: Valid state, non-empty filename, unique ID, project exists and owned...
_check_ownership(state, project_id, owner_id) was False
state was SystemState(projects={}, files={})
project_id was '1cefb1ae-6325-4de0-b318-3218b8636e11'
```

## Root Cause

The Imperative Shell (`api/files.py:save_file`) fails to validate that the project exists BEFORE calling the Functional Core (`file_operations.save_file_core`).

### Flow Analysis

1. Frontend sends `POST /api/files/save` with `project_id=1cefb1ae-...`
2. Shell calls `adapters.build_scoped_state(project_id, owner_filter, db)`
3. `build_scoped_state` queries database but finds no matching project
4. Returns empty `SystemState(projects={}, files={})`
5. Shell passes empty state to Core function `file_operations.save_file_core(...)`
6. Core function's icontract precondition fails: `project_id in state.projects` is False
7. icontract raises `ViolationError` which bubbles up as 500 Internal Server Error

### The Design Flaw

The Functional Core / Imperative Shell pattern requires:
- **Shell**: Handle I/O, validation, and error mapping
- **Core**: Pure business logic with preconditions that SHOULD be satisfied

The preconditions on Core functions are **defensive contracts** - they should never fail in production because the Shell is responsible for validating inputs BEFORE calling the Core.

**Current Bug**: The Shell doesn't check if `state.projects` contains the requested project before calling the Core function.

## Why This Was Missed in Testing

### 1. Test Scope Gap

Our test suite (`test_files.py`) doesn't exist! We only have:
- `test_auth.py` - Authentication tests
- `test_crypto.py` - Crypto tests  
- `test_database_schema.py` - Schema tests
- `test_projects.py` - Project CRUD tests
- `test_verification.py` - Dafny verification tests

**Missing**: File endpoint integration tests

### 2. Manual Testing Sequence

During manual testing, we always:
1. Created a project first
2. Then saved files to that project

We never tested the **negative case**: saving a file to a non-existent project.

### 3. icontract Preconditions Give False Confidence

The icontract decorators on both Shell and Core functions made us believe validation was covered:

```python
# files.py Shell precondition
@icontract.require(
    lambda request, ...: request.project_id is not None ...
)
```

This checks that `project_id` is provided, but NOT that the project EXISTS.

```python
# file_operations.py Core precondition
@icontract.require(
    lambda state, ...: project_id in state.projects ...
)
```

This checks that project exists in state, but state can be empty!

### 4. The DROP_EXISTING_TABLES Default

The default `DROP_EXISTING_TABLES=true` means every container restart wipes the database. This creates a situation where:
- Frontend has stale project IDs from localStorage
- Backend has empty database
- File save fails with cryptic error

### 5. Frontend-Backend Integration Gap

No end-to-end test validates that:
1. Frontend creates a project → gets project_id
2. Backend stores project
3. Frontend saves file with project_id
4. Backend creates file

We tested backend endpoints in isolation, not the full integration flow.

## The Fix

### Immediate Fix (in Shell)

Add explicit project existence check before calling Core:

```python
# In api/files.py save_file()

state = adapters.build_scoped_state(...)

# MISSING: Validate project exists before calling Core
if request.project_id not in state.projects:
    raise HTTPException(
        status_code=404, 
        detail=f"Project {request.project_id} not found or not owned by you"
    )

# Now safe to call Core
new_state, result = file_operations.save_file_core(...)
```

### Why Not Rely on Core's icontract?

1. **Wrong error type**: icontract raises `ViolationError` → 500 Internal Server Error
2. **Poor UX**: User sees "Internal server error" instead of "Project not found"
3. **Violates Shell responsibility**: Shell should translate I/O errors to HTTP errors
4. **Contract violations indicate bugs**: Precondition failures should be developer bugs, not user input errors

## Lessons Learned

1. **Shell must validate BEFORE Core**: Don't rely on Core preconditions for user input validation
2. **Test negative cases**: "What happens when project doesn't exist?"
3. **Integration tests needed**: Frontend → Backend full flow tests
4. **Database persistence matters**: `DROP_EXISTING_TABLES` should default to `false`
5. **Error mapping responsibility**: Shell must map ALL error cases to HTTP responses

## Test Cases to Add

```python
def test_save_file_nonexistent_project():
    """Saving a file to non-existent project should return 404."""
    response = client.post("/api/files/save", json={
        "project_id": "00000000-0000-0000-0000-nonexistent",
        "filename": "test.md",
        "content": "test",
        "file_type": "md"
    })
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_save_file_wrong_owner():
    """Saving a file to project owned by another user should return 403."""
    # Create project with user A
    # Try to save file with user B
    assert response.status_code == 403

def test_database_persistence_across_restarts():
    """Projects should persist across container restarts."""
    # Create project
    # Restart container
    # Verify project still exists
```

## Affected Files

- `api/files.py` - Missing project existence check in Shell
- `api/core/adapters.py` - Returns empty state instead of raising error (by design, but Shell must handle)
- `docker-compose.yml` - `DROP_EXISTING_TABLES` was defaulting to `true`

## Priority

**HIGH** - This is a user-facing bug that causes 500 errors instead of helpful 404 messages.

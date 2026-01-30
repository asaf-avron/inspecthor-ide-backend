# FileOperations Specification

**Dafny Spec:** [`api/verification/file_operations.dfy`](../../api/verification/file_operations.dfy)  
**Python Implementation:** [`api/core/file_operations.py`](../../api/core/file_operations.py)

## Purpose

Formally verified file operations: create, update, and delete files within projects. All operations maintain relational integrity and ownership constraints.

## Key Functions

### `SaveFile`
Creates a new file in a project.

**Preconditions:**
- Valid system state
- Unique filename within project
- Project exists and ownership verified
- Content size limits respected

**Postconditions:**
- File added to system state
- Project's fileIds updated
- ValidState maintained

### `UpdateFile`
Updates file content and optionally renames it.

**Preconditions:**
- File exists
- Ownership verified
- New filename unique (if renaming)

**Postconditions:**
- File content/size updated
- Rename flag set if changed
- ValidState maintained

### `DeleteFile`
Removes a file from a project.

**Preconditions:**
- File exists
- Ownership verified

**Postconditions:**
- File removed from system state
- Project's fileIds updated
- ValidState maintained

## Verification Status

✅ Verified with Dafny compiler in CI (`.github/workflows/verify-dafny.yml`)

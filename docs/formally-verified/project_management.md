# ProjectManagement Specification

**Dafny Spec:** [`api/verification/project_management.dfy`](../../api/verification/project_management.dfy)  
**Python Implementation:** [`api/core/project_management.py`](../../api/core/project_management.py)

## Purpose

Formally verified project lifecycle operations: create and delete projects with cascade deletion of associated files.

## Key Functions

### `CreateProject`
Creates a new project for an owner.

**Preconditions:**
- Valid system state
- Unique project name per owner (case-insensitive)
- Name length constraints (1-255 chars)
- Description length constraints (≤1000 chars)

**Postconditions:**
- Project added to system state
- ValidState maintained

### `DeleteProject`
Deletes a project and all its files (cascade deletion).

**Preconditions:**
- Project exists
- Ownership verified

**Postconditions:**
- Project removed from system state
- All project files removed (cascade)
- ValidState maintained

## Verification Status

✅ Verified with Dafny compiler in CI (`.github/workflows/verify-dafny.yml`)

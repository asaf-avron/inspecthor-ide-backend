# ProjectMigration Specification

**Dafny Spec:** [`api/verification/project_migration.dfy`](../../api/verification/project_migration.dfy)  
**Python Implementation:** [`api/core/migration.py`](../../api/core/migration.py)

## Purpose

Formally verified migration of anonymous projects to authenticated users. Ensures isolation: only projects owned by the current session hash are migrated.

## Key Function

### `MigrateAnonymousProjects`
Transitions anonymous projects to authenticated ownership.

**Preconditions:**
- Valid system state

**Postconditions:**
- Projects owned by `currentSessionHash` transition to `Authenticated(userId)`
- All other projects unchanged (isolation property)
- ValidState maintained

## Security Property

**Theorem_Isolation**: Projects not owned by the current session hash remain unchanged. This prevents accidental migration of other users' anonymous projects.

## Verification Status

✅ Verified with Dafny compiler in CI (`.github/workflows/verify-dafny.yml`)

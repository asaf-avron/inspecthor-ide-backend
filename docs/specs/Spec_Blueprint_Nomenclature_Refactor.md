# Blueprint Nomenclature Refactor Specification

> **Phase:** 1 - Foundation (The Cleanup)  
> **Priority:** P0 - Must complete before other phases  
> **Estimated Effort:** 2 sprints

---

## 1. Logic Model (State)

### Entities
- **Blueprint** (formerly Project) - Container for formal specifications and proofs
- **Claim** (formerly File with type .md) - English requirements document
- **Contract** (formerly File with type .dfy) - Dafny formal specification
- **Proof** - Verification result with certificate

### Key State Variables
- `Blueprint.blueprint_id`: UUID (primary key)
- `Blueprint.name`: String (unique per user)
- `Blueprint.user_id`: UUID (owner reference)
- `Claim.content`: Text (English specification)
- `Contract.content`: Text (Dafny code)

### Invariants
- A Blueprint must have at least one Claim OR one Contract
- A Contract must be linked to its source Claim (traceability)
- Blueprint names are unique per user (case-insensitive)

---

## 2. Capabilities (Functional Core)

### Function: RenameProjectToBlueprint

**Description:** Database migration to rename `projects` table to `blueprints` and all related columns.

**Inputs:**
- None (migration script)

**Preconditions:**
- Database connection is valid
- No active transactions on `projects` table
- Backup has been created

**Postconditions:**
- Table `projects` renamed to `blueprints`
- Column `project_id` renamed to `blueprint_id` in all tables
- All foreign key constraints updated
- All indexes recreated with new naming

**Edge Cases:**
- If migration fails midway, rollback to backup state
- If table already named `blueprints`, skip (idempotent)

---

### Function: UpdateAPIRoutes

**Description:** Change all API endpoints from `/api/projects/*` to `/api/blueprints/*`

**Inputs:**
- None (code refactor)

**Preconditions:**
- All tests passing with current naming
- API versioning in place (v1)

**Postconditions:**
- `/api/v1/blueprints/` endpoints active
- `/api/projects/` returns 301 redirect (backward compat)
- OpenAPI schema updated
- Frontend API client updated

---

## 3. Files to Modify

### Backend (23 files)

| File | Changes |
|------|---------|
| `api/database.py` | Rename `Project` class to `Blueprint`, update all columns |
| `api/projects.py` → `api/blueprints.py` | Rename router, endpoints, functions |
| `api/models.py` | Rename all `Project*` Pydantic models to `Blueprint*` |
| `api/services/project_service.py` → `blueprint_service.py` | Rename class and methods |
| `api/files.py` | Update `project_id` references to `blueprint_id` |
| `api/main.py` | Update router imports |
| `tests/test_projects.py` → `test_blueprints.py` | Rename and update tests |

### Frontend (26 files)

| File | Changes |
|------|---------|
| `lib/types.ts` | Rename `Project*` types to `Blueprint*` |
| `lib/project-context.tsx` → `blueprint-context.tsx` | Rename context |
| `components/ide/project-explorer.tsx` → `blueprint-navigator.tsx` | Rename component |
| `components/project/` → `components/blueprint/` | Rename folder |
| `app/app/[projectId]/` → `app/app/[blueprintId]/` | Rename route |

### Database Migration

```sql
-- Alembic migration: rename_project_to_blueprint.py

ALTER TABLE projects RENAME TO blueprints;
ALTER TABLE blueprints RENAME COLUMN project_id TO blueprint_id;

ALTER TABLE files RENAME COLUMN project_id TO blueprint_id;
ALTER TABLE anchors RENAME COLUMN project_id TO blueprint_id;
ALTER TABLE repositories RENAME COLUMN project_id TO blueprint_id;

-- Update indexes
DROP INDEX ix_projects_user_id_name_lower;
CREATE UNIQUE INDEX ix_blueprints_user_id_name_lower 
    ON blueprints (user_id, lower(name)) 
    WHERE user_id IS NOT NULL;
```

---

## 4. Verification Plan

### Automated Tests
1. Run existing test suite (expect failures due to naming)
2. Update tests to use new naming
3. Run migration on test database
4. All tests green with new naming

### Manual Verification
1. Create new blueprint via UI
2. Verify URL uses `/blueprints/` path
3. Check database has `blueprints` table
4. Verify backward compat redirects work

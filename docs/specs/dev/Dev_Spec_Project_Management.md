# Feature Spec: Project Management System

## 1. The Logic Model

A project management system that enables users to create, organize, and manage multiple formal verification projects, each containing specification files, Dafny code, and verification results.

### Dependencies
- **Database:** PostgreSQL with SQLAlchemy ORM
- **Authentication:** API Key middleware (existing)
- **File System:** File management API (existing)

### Definitions
- **Project:** A container for related specification files, Dafny code, and verification artifacts
- **Project ID:** UUID v4 identifier unique per project
- **API Key Hash:** SHA-256 hash of user's API key (for ownership)
- **Project Ownership:** Projects are scoped to API keys (users)

### State Space
- `project_id: UUID | null`
- `project_name: String`
- `project_description: String | null`
- `created_at: DateTime`
- `updated_at: DateTime`
- `api_key_hash: String` (ownership)
- `file_count: Integer` (derived)

### Database Schema
```python
class Project(Base):
    __tablename__ = "projects"
    
    project_id: str (UUID, primary key)
    api_key_hash: str (indexed, foreign key constraint)
    name: str (not null, max 255)
    description: str | null (text)
    created_at: datetime (not null, default now)
    updated_at: datetime (not null, default now, onupdate now)
    
    # Relationships
    files: List[File] (cascade delete)
```

---

## 2. Capabilities

### Capability 2.1: Create Project

**Goal:** Allow users to create a new project with a name and optional description.

**Input:**
```python
class ProjectCreateRequest(BaseModel):
    name: str (min_length=1, max_length=255)
    description: Optional[str] (max_length=1000)
```

**Logic:**
1. Extract API key from request header
2. Hash API key using SHA-256
3. Generate UUID v4 for project_id
4. Create Project record in database
5. Set created_at and updated_at to current timestamp

**Validation:**
- Project name must be non-empty (1-255 characters)
- Project name must be unique per API key (case-insensitive)
- API key must be valid (middleware handles this)

**Decision:**
- If validation fails: Return 400 Bad Request with error details
- If successful: Return 201 Created with project details

**Result:**
```python
class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    created_at: str (ISO 8601)
    updated_at: str (ISO 8601)
    file_count: int (default 0)
```

**Postconditions:**
1. Project exists in database with unique project_id
2. Project is owned by the requesting API key
3. Project has zero files initially
4. created_at and updated_at are set correctly

---

### Capability 2.2: List Projects

**Goal:** Retrieve all projects owned by the requesting API key.

**Input:**
- Query parameters (optional):
  - `limit: int` (default 100, max 1000)
  - `offset: int` (default 0)
  - `sort: str` (default "updated_at", options: "created_at", "updated_at", "name")
  - `order: str` (default "desc", options: "asc", "desc")

**Logic:**
1. Extract API key from request header
2. Hash API key
3. Query projects WHERE api_key_hash = hash
4. Apply sorting and pagination
5. Count total files per project (subquery or join)
6. Return paginated results

**Validation:**
- API key must be valid (middleware)
- Limit must be between 1 and 1000
- Offset must be >= 0
- Sort field must be valid

**Decision:**
- If validation fails: Return 400 Bad Request
- If successful: Return 200 OK with project list

**Result:**
```python
class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    limit: int
    offset: int
```

**Postconditions:**
1. Only projects owned by API key are returned
2. Results are sorted and paginated correctly
3. File counts are accurate
4. Total count reflects all matching projects (not just page)

---

### Capability 2.3: Get Project

**Goal:** Retrieve a specific project by ID.

**Input:**
- Path parameter: `project_id: UUID`

**Logic:**
1. Extract API key from request header
2. Hash API key
3. Query project WHERE project_id = id AND api_key_hash = hash
4. Count files for project
5. Return project details

**Validation:**
- project_id must be valid UUID format
- API key must be valid (middleware)
- Project must exist
- Project must be owned by API key

**Decision:**
- If project not found: Return 404 Not Found
- If unauthorized: Return 404 Not Found (don't reveal existence)
- If successful: Return 200 OK with project details

**Result:**
```python
ProjectResponse  # Same as 2.1
```

**Postconditions:**
1. Only project owner can access project
2. File count is accurate
3. Project details are complete

---

### Capability 2.4: Update Project

**Goal:** Update project name and/or description.

**Input:**
- Path parameter: `project_id: UUID`
- Body:
```python
class ProjectUpdateRequest(BaseModel):
    name: Optional[str] (min_length=1, max_length=255)
    description: Optional[str] (max_length=1000)
```

**Logic:**
1. Extract API key and hash
2. Find project (with ownership check)
3. Update provided fields only (partial update)
4. Set updated_at to current timestamp
5. Save changes

**Validation:**
- project_id must be valid UUID
- Project must exist and be owned by API key
- If name provided: must be unique per API key (case-insensitive)
- At least one field must be provided

**Decision:**
- If validation fails: Return 400 Bad Request
- If not found/unauthorized: Return 404 Not Found
- If successful: Return 200 OK with updated project

**Result:**
```python
ProjectResponse
```

**Postconditions:**
1. Only provided fields are updated
2. updated_at timestamp is refreshed
3. Name uniqueness is maintained per API key
4. Other fields remain unchanged

---

### Capability 2.5: Delete Project

**Goal:** Delete a project and all associated files (cascade delete).

**Input:**
- Path parameter: `project_id: UUID`

**Logic:**
1. Extract API key and hash
2. Find project (with ownership check)
3. Delete all files associated with project (cascade)
4. Delete project record
5. Commit transaction

**Validation:**
- project_id must be valid UUID
- Project must exist
- Project must be owned by API key

**Decision:**
- If not found/unauthorized: Return 404 Not Found
- If successful: Return 200 OK with confirmation

**Result:**
```python
class ProjectDeleteResponse(BaseModel):
    deleted: bool
    project_id: str
    files_deleted: int
```

**Postconditions:**
1. Project is deleted from database
2. All associated files are deleted (cascade)
3. No orphaned file records remain
4. Operation is atomic (transaction)

---

## 3. API Endpoints

### Endpoint Specifications

**Base Path:** `/api/projects`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/projects` | Create project | Yes |
| GET | `/api/projects` | List projects | Yes |
| GET | `/api/projects/{project_id}` | Get project | Yes |
| PUT | `/api/projects/{project_id}` | Update project | Yes |
| DELETE | `/api/projects/{project_id}` | Delete project | Yes |

### Request/Response Examples

**Create Project:**
```http
POST /api/projects
X-API-Key: dev_key_1
Content-Type: application/json

{
  "name": "Token Contract",
  "description": "ERC-20 token with minting limits"
}

Response: 201 Created
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Token Contract",
  "description": "ERC-20 token with minting limits",
  "created_at": "2026-01-26T12:00:00Z",
  "updated_at": "2026-01-26T12:00:00Z",
  "file_count": 0
}
```

**List Projects:**
```http
GET /api/projects?limit=10&offset=0&sort=updated_at&order=desc
X-API-Key: dev_key_1

Response: 200 OK
{
  "projects": [
    {
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Token Contract",
      "description": "ERC-20 token with minting limits",
      "created_at": "2026-01-26T12:00:00Z",
      "updated_at": "2026-01-26T12:00:00Z",
      "file_count": 5
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

## 4. Database Migration

### Migration Script

```python
# Migration: Add projects table
def upgrade():
    op.create_table(
        'projects',
        sa.Column('project_id', sa.String(36), primary_key=True),
        sa.Column('api_key_hash', sa.String(64), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Add foreign key constraint to files table
    op.add_column('files', sa.Column('project_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_files_project', 'files', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_files_project_id', 'files', ['project_id'])

def downgrade():
    op.drop_constraint('fk_files_project', 'files', type_='foreignkey')
    op.drop_index('ix_files_project_id', 'files')
    op.drop_column('files', 'project_id')
    op.drop_table('projects')
```

---

## 5. Postconditions (Global)

1. **Ownership Isolation:** Projects are completely isolated by API key. Users cannot access projects owned by other API keys.

2. **Data Integrity:** 
   - Project names are unique per API key (case-insensitive)
   - Cascade delete ensures no orphaned files
   - Timestamps are automatically maintained

3. **Idempotency:** 
   - Creating a project with the same name (same API key) returns 400
   - Deleting a non-existent project returns 404 (not an error)

4. **Performance:**
   - List queries use indexes on api_key_hash and updated_at
   - File counts use efficient subqueries or joins
   - Pagination limits prevent large result sets

5. **Security:**
   - All endpoints require valid API key
   - Ownership checks prevent unauthorized access
   - No information leakage (404 for unauthorized access)

---

## 6. Testing Requirements

### Unit Tests
- [ ] Project creation with valid/invalid names
- [ ] Name uniqueness enforcement per API key
- [ ] Project retrieval with ownership checks
- [ ] Update with partial fields
- [ ] Cascade delete of files
- [ ] Pagination and sorting

### Integration Tests
- [ ] Full CRUD workflow
- [ ] Multiple projects per API key
- [ ] File association with projects
- [ ] Concurrent access handling

### Success Criteria
- ✅ All endpoints return correct status codes
- ✅ Ownership isolation works correctly
- ✅ Cascade delete removes all files
- ✅ Pagination and sorting work as expected
- ✅ No SQL injection vulnerabilities
- ✅ Performance: List 1000 projects < 500ms

---

## 7. Implementation Checklist

### Backend
- [ ] Create `api/projects.py` router
- [ ] Add Project model to `api/database.py`
- [ ] Create migration script
- [ ] Implement all 5 endpoints
- [ ] Add request/response models to `api/models.py`
- [ ] Include router in `api/main.py`
- [ ] Write unit tests
- [ ] Write integration tests

### Frontend (Phase 1.2)
- [ ] Add project API functions to `lib/api-client.ts`
- [ ] Add project state to `lib/project-context.tsx`
- [ ] Create project selector component
- [ ] Create project creation dialog
- [ ] Update file operations to use project_id

---

**Status:** Ready for Implementation  
**Priority:** High (Foundation for all other features)  
**Estimated Effort:** 2-3 days

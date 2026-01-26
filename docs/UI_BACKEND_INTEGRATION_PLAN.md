# UI-Backend Integration Plan

**Status:** Planning Phase  
**Last Updated:** 2026-01-26  
**Goal:** Connect all UI flows to working backend endpoints, implement missing features

---

## Overview

This document outlines the step-by-step plan to fully integrate the Guardian Gateway IDE frontend with the FastAPI backend. We'll go flow-by-flow, ensuring each user interaction is properly connected to backend services.

---

## Current State Analysis

### ✅ Backend Endpoints Available

1. **Health Check** - `/api/health` ✅
2. **Generate Spec** - `/api/generate/spec` ✅
3. **Chat Assistant** - `/api/assistant/chat` ✅
4. **File Operations:**
   - Save - `/api/files/save` ✅
   - Get - `/api/files/{file_id}` ✅
   - List - `/api/files` ✅
   - Delete - `/api/files/{file_id}` ✅
5. **Verification** - `/api/verify` ✅

### ❌ Missing Backend Endpoints

1. **Deconstruct to Units** - `/api/deconstruct` (not implemented)
2. **Project Management:**
   - Create Project - `/api/projects` POST
   - List Projects - `/api/projects` GET
   - Get Project - `/api/projects/{project_id}` GET
   - Delete Project - `/api/projects/{project_id}` DELETE
3. **File Operations:**
   - Update File - `/api/files/{file_id}` PUT/PATCH (currently only save creates new)

### ⚠️ Frontend Gaps

1. **Project Management:**
   - No project creation UI
   - No project switching
   - No project list view
   - Project ID not properly managed

2. **File Operations:**
   - File loading not fully connected
   - File deletion not implemented in UI
   - File update/overwrite logic unclear
   - File selection state management

3. **Deconstruct to Units:**
   - UI exists but backend endpoint missing
   - No unit file creation logic
   - No unit-to-dfy linking

4. **Error Handling:**
   - Limited error feedback to users
   - No retry mechanisms for failed operations
   - No offline/connection status indicators

---

## Implementation Plan

### Phase 1: Project Management Foundation

**Goal:** Enable users to create, list, and switch between projects.

#### Step 1.1: Backend - Project Management API

**Files to Create/Modify:**
- `api/projects.py` (new)
- `api/database.py` (add Project model)
- `api/main.py` (include projects router)

**Endpoints to Implement:**
```python
POST   /api/projects              # Create new project
GET    /api/projects              # List all projects for API key
GET    /api/projects/{project_id} # Get project details
DELETE /api/projects/{project_id} # Delete project (and all files)
```

**Database Schema:**
```python
class Project(Base):
    project_id: str (UUID, primary key)
    api_key_hash: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
```

**Tasks:**
- [ ] Create `api/projects.py` router
- [ ] Add Project model to database
- [ ] Implement CRUD operations
- [ ] Add project_id foreign key to File model
- [ ] Update File endpoints to require project_id
- [ ] Add migration script

**Success Criteria:**
- Can create project via API
- Can list all projects
- Can delete project (cascades to files)
- Files are properly scoped to projects

#### Step 1.2: Frontend - Project Management UI

**Files to Modify:**
- `lib/api-client.ts` (add project functions)
- `lib/project-context.tsx` (add project management)
- `components/ide/header.tsx` (add project selector)
- `app/page.tsx` (add project creation flow)

**New Components:**
- `components/ide/project-selector.tsx` (new)
- `components/ide/project-dialog.tsx` (new)

**Tasks:**
- [ ] Add project API client functions
- [ ] Add project state to ProjectContext
- [ ] Create project selector dropdown in header
- [ ] Create "New Project" dialog
- [ ] Update createProject to use backend
- [ ] Add project switching logic
- [ ] Update file loading to filter by project_id
- [ ] Show project name in UI

**Success Criteria:**
- User can create new project from UI
- User can switch between projects
- Files are filtered by selected project
- Project name displayed in header

---

### Phase 2: File Operations Enhancement

**Goal:** Complete file CRUD operations with proper state management.

#### Step 2.1: Backend - File Update Endpoint

**Files to Modify:**
- `api/files.py`

**Endpoints to Add:**
```python
PUT    /api/files/{file_id}       # Update existing file
PATCH  /api/files/{file_id}       # Partial update
```

**Tasks:**
- [ ] Add PUT endpoint for full file update
- [ ] Add PATCH endpoint for partial updates
- [ ] Validate file ownership
- [ ] Update updated_at timestamp
- [ ] Return updated file response

**Success Criteria:**
- Can update file content via API
- File versioning/timestamps work correctly
- Ownership validation prevents unauthorized updates

#### Step 2.2: Frontend - File Operations UI

**Files to Modify:**
- `lib/api-client.ts` (add updateFile function)
- `lib/project-context.tsx` (enhance file operations)
- `components/ide/project-explorer.tsx` (add delete, rename)
- `components/ide/markdown-editor.tsx` (auto-save, save indicator)
- `components/ide/code-editor.tsx` (auto-save, save indicator)

**Tasks:**
- [ ] Add updateFile to API client
- [ ] Implement file loading on selection
- [ ] Add file deletion with confirmation
- [ ] Add file rename functionality
- [ ] Implement auto-save (debounced)
- [ ] Add save status indicator (saved/unsaved/saving)
- [ ] Handle file conflicts (concurrent edits)
- [ ] Add file creation (new .md, new .dfy)
- [ ] Update file list after operations

**Success Criteria:**
- Files load when selected
- Files save automatically after edits
- Can delete files with confirmation
- Can rename files
- Save status clearly indicated
- File list updates in real-time

---

### Phase 3: Deconstruct to Units

**Goal:** Implement specification deconstruction into verifiable units.

#### Step 3.1: Backend - Deconstruct Endpoint

**Files to Create/Modify:**
- `api/deconstruct.py` (new)
- `core/workflow.py` (add deconstruct logic)
- `api/main.py` (include deconstruct router)

**Endpoints to Implement:**
```python
POST   /api/deconstruct           # Deconstruct spec into units
```

**Request Model:**
```python
class DeconstructRequest(BaseModel):
    project_id: str
    source_file_id: str           # The root spec file
    strategy: Literal["auto", "manual"] = "auto"
    max_units: Optional[int] = None
```

**Response Model:**
```python
class DeconstructResponse(BaseModel):
    units: List[UnitFile]
    links: List[UnitLink]         # Unit -> Dafny file mappings
    statistics: DeconstructStats
```

**Tasks:**
- [ ] Create deconstruct router
- [ ] Implement deconstruction algorithm:
  - Parse markdown structure
  - Identify logical units (requirements, functions, methods)
  - Create unit files (.unit.md)
  - Generate corresponding Dafny files (.dfy)
  - Create traceability links
- [ ] Save unit files to database
- [ ] Return unit list with metadata

**Success Criteria:**
- Can deconstruct root spec into units
- Units are saved as separate files
- Unit-to-dfy links are created
- Traceability maintained

#### Step 3.2: Frontend - Deconstruct UI

**Files to Modify:**
- `lib/api-client.ts` (add deconstruct function)
- `lib/project-context.tsx` (add deconstructToUnits)
- `components/ide/markdown-editor.tsx` (enhance deconstruct button)
- `components/ide/project-explorer.tsx` (show unit files)
- `app/page.tsx` (connect deconstruct handler)

**Tasks:**
- [ ] Add deconstruct API client function
- [ ] Implement deconstructToUnits in context
- [ ] Add loading state during deconstruction
- [ ] Show progress/status during deconstruction
- [ ] Refresh file list after deconstruction
- [ ] Highlight unit files in explorer
- [ ] Show unit-to-dfy links in traceability view
- [ ] Add "Deconstruct" button to root files only

**Success Criteria:**
- Deconstruct button works end-to-end
- Units appear in file explorer
- Unit files are properly linked
- Progress feedback during operation

---

### Phase 4: Enhanced User Flows

**Goal:** Polish user experience with better error handling and feedback.

#### Step 4.1: Error Handling & Feedback

**Files to Modify:**
- `lib/api-client.ts` (enhance error handling)
- `lib/project-context.tsx` (add error recovery)
- `components/ide/*` (add error states)
- `components/ui/toast.tsx` (if exists, enhance)

**Tasks:**
- [ ] Add connection status indicator
- [ ] Implement retry logic for failed requests
- [ ] Add user-friendly error messages
- [ ] Show loading states for all async operations
- [ ] Add success/error toasts
- [ ] Handle network errors gracefully
- [ ] Add offline mode detection
- [ ] Implement request queuing for offline

**Success Criteria:**
- Users see clear error messages
- Failed operations can be retried
- Loading states visible everywhere
- Network issues handled gracefully

#### Step 4.2: File Edit/View Flow

**Files to Modify:**
- `components/ide/markdown-editor.tsx`
- `components/ide/code-editor.tsx`
- `app/page.tsx`

**Tasks:**
- [ ] Implement proper file loading on selection
- [ ] Add file content caching
- [ ] Implement edit mode toggle
- [ ] Add syntax validation for Dafny
- [ ] Add markdown preview
- [ ] Handle large files (virtualization)
- [ ] Add file tabs for multiple open files
- [ ] Implement unsaved changes warning

**Success Criteria:**
- Files load instantly when selected
- Edit/view modes work smoothly
- Large files don't freeze UI
- Unsaved changes are tracked

#### Step 4.3: Verification Flow Enhancement

**Files to Modify:**
- `components/ide/verification-panel.tsx`
- `lib/project-context.tsx`

**Tasks:**
- [ ] Show verification progress
- [ ] Display proof obligations clearly
- [ ] Link errors to code lines
- [ ] Add "Fix with AI" suggestions
- [ ] Show verification history
- [ ] Add re-verify on save option

**Success Criteria:**
- Verification results clearly displayed
- Errors linked to source code
- AI suggestions actionable

---

### Phase 5: Advanced Features

**Goal:** Add polish and advanced functionality.

#### Step 5.1: Project Templates

**Tasks:**
- [ ] Create project template system
- [ ] Add template selection on project creation
- [ ] Pre-populate files from templates

#### Step 5.2: File Search & Filtering

**Tasks:**
- [ ] Add file search in project explorer
- [ ] Filter by file type
- [ ] Sort by name/date/size

#### Step 5.3: Collaboration Features

**Tasks:**
- [ ] Add file sharing (future)
- [ ] Add comments/annotations (future)
- [ ] Add version history (future)

---

## Implementation Order

### Week 1: Foundation
1. ✅ Phase 1.1: Backend Project Management
2. ✅ Phase 1.2: Frontend Project Management
3. ✅ Phase 2.1: Backend File Update

### Week 2: Core Features
4. ✅ Phase 2.2: Frontend File Operations
5. ✅ Phase 3.1: Backend Deconstruct
6. ✅ Phase 3.2: Frontend Deconstruct

### Week 3: Polish
7. ✅ Phase 4.1: Error Handling
8. ✅ Phase 4.2: File Edit/View Flow
9. ✅ Phase 4.3: Verification Enhancement

### Week 4: Advanced
10. ✅ Phase 5: Advanced Features (as needed)

---

## Testing Checklist

For each phase, verify:

- [ ] Backend endpoints return correct responses
- [ ] Frontend calls backend correctly
- [ ] Error cases handled gracefully
- [ ] Loading states shown appropriately
- [ ] State updates correctly
- [ ] UI reflects backend changes
- [ ] No console errors
- [ ] Works in both light/dark mode
- [ ] Responsive on mobile (if applicable)

---

## Notes

- **Project ID Management:** Currently project_id is optional in File model. We should make it required after Phase 1.
- **File Versioning:** Consider adding file versioning in future phases.
- **Real-time Updates:** Consider WebSocket for real-time collaboration (future).
- **Offline Support:** Service worker for offline file editing (future).

---

## Success Metrics

- ✅ All user flows work end-to-end
- ✅ No broken features
- ✅ Clear error messages
- ✅ Fast response times (< 500ms for most operations)
- ✅ Zero data loss
- ✅ Smooth user experience

---

**Next Steps:** Start with Phase 1.1 - Backend Project Management API.

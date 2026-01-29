# UI-Backend Integration Plan

**Status:** Planning Phase  
**Last Updated:** 2026-01-26  
**Goal:** Connect all UI flows to working backend endpoints, implement missing features

---

## Overview

This document provides a high-level roadmap for integrating the Guardian Gateway IDE frontend with the FastAPI backend. Each major feature has a detailed specification document following a provable approach with tightly defined requirements, postconditions, and success criteria.

**Related Specifications:**
- [Project Management](./specs/dev/Dev_Spec_Project_Management.md) - Phase 1
- [File Operations](./specs/dev/Dev_Spec_File_Operations.md) - Phase 2
- [Deconstruct to Units](./specs/dev/Dev_Spec_Deconstruct_To_Units.md) - Phase 3

---

## Current State Analysis

### ✅ Backend Endpoints Available

1. **Health Check** - `/api/health` ✅
2. **Project Management:**
   - Create Project - `POST /api/projects` ✅
   - List Projects - `GET /api/projects` ✅
   - Get Project - `GET /api/projects/{project_id}` ✅
   - Get Project Structure - `GET /api/projects/{project_id}/structure` ✅
   - Update Project - `PUT /api/projects/{project_id}` ✅
   - Delete Project - `DELETE /api/projects/{project_id}` ✅
3. **File Operations:**
   - Save - `POST /api/files/save` ✅
   - Get - `GET /api/files/{file_id}` ✅
   - Update - `PUT /api/files/{file_id}` ✅
   - List - `GET /api/files` ✅
   - Delete - `DELETE /api/files/{file_id}` ✅
4. **Generate Spec** - `/api/generate/spec` ✅
5. **Verification** - `/api/verify` ✅
6. **Chat Assistant** - `/api/assistant/chat` ✅

### ❌ Missing Backend Endpoints

1. **Deconstruct to Units** - `/api/deconstruct` (not implemented)

### ⚠️ Frontend Gaps

1. **Project Management:**
   - ✅ Project creation UI (dashboard)
   - ✅ Project switching (project explorer dropdown)
   - ✅ Project list view (dashboard)
   - ✅ URL-based state recovery (`/app/[projectId]`)
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

**Detailed Specification:** [Dev_Spec_Project_Management.md](./specs/dev/Dev_Spec_Project_Management.md)

**Summary:**
- Backend: Full CRUD API for projects with ownership isolation
- Frontend: Project selector, creation dialog, switching logic
- Database: Project model with cascade delete to files

**Key Endpoints:**
- `POST /api/projects` - Create project
- `GET /api/projects` - List projects (paginated)
- `GET /api/projects/{project_id}` - Get project
- `PUT /api/projects/{project_id}` - Update project
- `DELETE /api/projects/{project_id}` - Delete project (cascade)

**Implementation Checklist:**
- [ ] Backend: Project model and migration
- [ ] Backend: All 5 endpoints implemented
- [ ] Backend: Tests written
- [ ] Frontend: API client functions
- [ ] Frontend: Project selector component
- [ ] Frontend: Project creation dialog
- [ ] Frontend: Project switching logic
- [ ] Integration: End-to-end testing

---

### Phase 2: File Operations Enhancement

**Goal:** Complete file CRUD operations with proper state management.

**Detailed Specification:** [Dev_Spec_File_Operations.md](./specs/dev/Dev_Spec_File_Operations.md)

**Summary:**
- Backend: File update endpoint (PUT/PATCH)
- Frontend: Auto-save, file loading, delete, rename, create
- State Management: Save state indicators, error handling, retry logic

**Key Features:**
- Auto-save with 2-second debounce
- Save state indicator (saved/unsaved/saving/error)
- File loading on selection with caching
- Delete with confirmation dialog
- Rename functionality
- Create new files (markdown or Dafny)

**Implementation Checklist:**
- [ ] Backend: PUT /api/files/{file_id} endpoint
- [ ] Backend: Filename uniqueness validation
- [ ] Frontend: updateFile API client function
- [ ] Frontend: Auto-save with debounce
- [ ] Frontend: Save state indicator component
- [ ] Frontend: File loading on selection
- [ ] Frontend: Delete with confirmation
- [ ] Frontend: Rename functionality
- [ ] Frontend: Create new file flow
- [ ] Integration: End-to-end testing

---

### Phase 3: Deconstruct to Units

**Goal:** Implement specification deconstruction into verifiable units.

**Detailed Specification:** [Dev_Spec_Deconstruct_To_Units.md](./specs/dev/Dev_Spec_Deconstruct_To_Units.md)

**Summary:**
- Backend: Deconstruction algorithm, unit identification, Dafny generation
- Frontend: Deconstruct button, progress feedback, unit file display
- Database: Unit links table, file metadata enhancements

**Key Features:**
- Automatic unit identification from markdown structure
- Unit file creation (.unit.md)
- Dafny code generation for each unit
- Unit-to-Dafny file linking
- Traceability maintenance

**Implementation Checklist:**
- [ ] Backend: Markdown parsing and unit identification
- [ ] Backend: Unit file generation logic
- [ ] Backend: Dafny code generation per unit
- [ ] Backend: Unit links table and model
- [ ] Backend: POST /api/deconstruct endpoint
- [ ] Frontend: deconstruct API client function
- [ ] Frontend: deconstructToUnits in context
- [ ] Frontend: Progress indicator
- [ ] Frontend: Unit file highlighting
- [ ] Integration: End-to-end testing

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
1. **Phase 1: Project Management** (See [Dev_Spec_Project_Management.md](./specs/dev/Dev_Spec_Project_Management.md))
   - Backend: Project CRUD API
   - Frontend: Project management UI
   - **Estimated:** 2-3 days

### Week 2: Core Features
2. **Phase 2: File Operations** (See [Dev_Spec_File_Operations.md](./specs/dev/Dev_Spec_File_Operations.md))
   - Backend: File update endpoint
   - Frontend: Auto-save, delete, rename, create
   - **Estimated:** 3-4 days

### Week 3: Enhancement
3. **Phase 3: Deconstruct to Units** (See [Dev_Spec_Deconstruct_To_Units.md](./specs/dev/Dev_Spec_Deconstruct_To_Units.md))
   - Backend: Deconstruction algorithm and endpoint
   - Frontend: Deconstruct UI flow
   - **Estimated:** 4-5 days

### Week 4: Polish
4. **Phase 4: Enhanced User Flows**
   - Error handling & feedback
   - File edit/view improvements
   - Verification flow enhancements
   - **Estimated:** 2-3 days

### Future
5. **Phase 5: Advanced Features** (as needed)
   - Project templates
   - File search & filtering
   - Collaboration features

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

## Next Steps

1. **Review Specifications:** Read the detailed spec documents for each phase
2. **Start Implementation:** Begin with Phase 1 - Project Management
3. **Follow Provable Approach:** Each spec defines:
   - Logic Model (definitions, state space, dependencies)
   - Capabilities (goals, inputs, logic, validation, decisions, results)
   - Postconditions (global invariants)
   - Testing Requirements (unit, integration, success criteria)

**First Task:** Implement [Dev_Spec_Project_Management.md](./specs/dev/Dev_Spec_Project_Management.md) - Backend Project Management API

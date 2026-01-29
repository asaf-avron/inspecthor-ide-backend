# UI Functionality to API Mapping

This document details every functionality exposed by the UI, the APIs used, whether they exist, and whether they're backend or 3rd party APIs.

## Overview

The UI is a Next.js application (`v0-guardian-gateway-ide`) that communicates with a FastAPI backend (`guardian-gateway/api`). Some features also integrate with GitHub (3rd party).

---

## 1. Authentication & User Management

### 1.1 GitHub OAuth Login
**UI Component:** `LoginModal`, `Header` (Sign in button)  
**Functionality:** User authentication via GitHub OAuth  
**API Used:**
- `GET /api/auth/github` - **EXISTS** - Backend API (returns GitHub OAuth URL)
- `GET /api/auth/github/callback` - **EXISTS** - Backend API (OAuth callback handler)
- `GET /api/auth/me` - **EXISTS** - Backend API (get current user)
- `POST /api/auth/refresh` - **EXISTS** - Backend API (refresh JWT token)
- `POST /api/auth/logout` - **EXISTS** - Backend API (logout user)

**3rd Party:** GitHub OAuth API (via backend proxy)

**Status:** ✅ Fully implemented

---

### 1.2 User Profile Display
**UI Component:** `UserMenu`  
**Functionality:** Display logged-in user info  
**API Used:**
- `GET /api/auth/me` - **EXISTS** - Backend API

**Status:** ✅ Fully implemented

---

## 2. Project Management

### 2.1 Create Project
**UI Component:** `CreateProjectModal`, `ProjectsDashboard`, `ProjectExplorer`  
**Functionality:** Create a new project with bootstrap README.md  
**API Used:**
- `POST /api/projects/` - **EXISTS** - Backend API
  - Creates project and automatically creates README.md file
  - Returns `ProjectResponse` with `redirect_url`

**Status:** ✅ Fully implemented

---

### 2.2 List Projects
**UI Component:** `ProjectsDashboard`, `ProjectExplorer` (project switcher)  
**Functionality:** Display all user projects with pagination/sorting  
**API Used:**
- `GET /api/projects?limit={limit}&offset={offset}&sort={sort}&order={order}` - **EXISTS** - Backend API
  - Supports pagination (`limit`, `offset`)
  - Supports sorting (`sort`: `created_at`, `updated_at`, `name`)
  - Supports ordering (`order`: `asc`, `desc`)

**Status:** ✅ Fully implemented

---

### 2.3 Get Project Details
**UI Component:** `ProjectExplorer` (project switcher)  
**Functionality:** Get single project metadata  
**API Used:**
- `GET /api/projects/{project_id}` - **EXISTS** - Backend API

**Status:** ✅ Fully implemented

---

### 2.4 Get Project Structure
**UI Component:** `ProjectExplorer`, `ProjectContext`  
**Functionality:** Get project + file tree in one request  
**API Used:**
- `GET /api/projects/{project_id}/structure` - **EXISTS** - Backend API
  - Returns `ProjectStructureResponse` with project metadata and `FileMetadata[]`

**Status:** ✅ Fully implemented

---

### 2.5 Update Project
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Update project name/description  
**API Used:**
- `PUT /api/projects/{project_id}` - **EXISTS** - Backend API

**Status:** ⚠️ API exists but not exposed in UI

---

### 2.6 Delete Project
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Delete project (cascade deletes all files)  
**API Used:**
- `DELETE /api/projects/{project_id}` - **EXISTS** - Backend API

**Status:** ⚠️ API exists but not exposed in UI

---

### 2.7 Switch Project
**UI Component:** `ProjectExplorer` (dropdown switcher)  
**Functionality:** Navigate to different project  
**API Used:**
- `GET /api/projects/{project_id}/structure` - **EXISTS** - Backend API (called when switching)

**Status:** ✅ Fully implemented

---

## 3. File Management

### 3.1 Create New File
**UI Component:** `ProjectExplorer` (New File dialog)  
**Functionality:** Create empty markdown or Dafny file  
**API Used:**
- `POST /api/files/save` - **EXISTS** - Backend API
  - Creates file with empty content
  - Requires `project_id`, `filename`, `content`, `file_type` (`md` or `dfy`)

**Status:** ✅ Fully implemented

---

### 3.2 Save File
**UI Component:** `CodeEditor`, `MarkdownEditor` (auto-save + manual save)  
**Functionality:** Save file content (auto-save on debounce + manual save button)  
**API Used:**
- `POST /api/files/save` - **EXISTS** - Backend API (for new files)
- `PUT /api/files/{file_id}` - **EXISTS** - Backend API (for existing files)
  - Updates file content atomically
  - Optional `filename` parameter for renaming

**Status:** ✅ Fully implemented

---

### 3.3 Load File
**UI Component:** `ProjectExplorer` (file selection), `CodeEditor`, `MarkdownEditor`  
**Functionality:** Load file content into editor  
**API Used:**
- `GET /api/files/{file_id}` - **EXISTS** - Backend API
  - Returns `FileResponse` with `content`, `filename`, `file_type`, etc.
  - Frontend caches file content (5-minute TTL)

**Status:** ✅ Fully implemented

---

### 3.4 List Files
**UI Component:** `ProjectExplorer` (file tree)  
**Functionality:** List all files in project (filtered by project_id)  
**API Used:**
- `GET /api/files?project_id={project_id}` - **EXISTS** - Backend API
  - Optional `file_type` filter

**Status:** ✅ Fully implemented (but typically uses `/api/projects/{project_id}/structure` instead)

---

### 3.5 Update File Content
**UI Component:** `CodeEditor`, `MarkdownEditor` (onChange handler)  
**Functionality:** Update file content in editor (triggers auto-save)  
**API Used:**
- `PUT /api/files/{file_id}` - **EXISTS** - Backend API (called by auto-save hook)

**Status:** ✅ Fully implemented

---

### 3.6 Rename File
**UI Component:** `ProjectExplorer` (double-click to rename)  
**Functionality:** Rename file  
**API Used:**
- `PUT /api/files/{file_id}` - **EXISTS** - Backend API
  - Passes `filename` parameter in `FileUpdateRequest`

**Status:** ✅ Fully implemented

---

### 3.7 Delete File
**UI Component:** `ProjectExplorer` (context menu)  
**Functionality:** Delete file  
**API Used:**
- `DELETE /api/files/{file_id}` - **EXISTS** - Backend API

**Status:** ✅ Fully implemented

---

## 4. Specification Generation

### 4.1 Generate Formal Spec from Markdown
**UI Component:** `MarkdownEditor` ("Generate Formal Spec" button)  
**Functionality:** Transform English requirements into Dafny specification  
**API Used:**
- `POST /api/generate/spec` - **EXISTS** - Backend API
  - Request: `english_spec`, `rigor_level`, `current_filename`, `project_id`, `source_file_id`
  - Response: `GenerateSpecResponse` with:
    - `triage` (doc type classification)
    - `structured_spec` (formatted markdown)
    - `dafny_skeleton` (generated Dafny code)
    - `traceability_matrix` (requirement-to-code mappings)
    - `statistics` (coverage metrics)
    - `suggested_filename` (AI-suggested filename)
    - `units_created` (if units were auto-created)
    - `subfolder_name` (if units subfolder was created)

**3rd Party:** Google Gemini API (via backend `SpecAuditor`)

**Status:** ✅ Fully implemented

---

### 4.2 Find Gaps in Specification
**UI Component:** `MarkdownEditor` ("Refine Spec" button), `SpecRefinementView`  
**Functionality:** Identify gaps and ambiguities in specification before generating Dafny  
**API Used:**
- `POST /api/generate/find-gaps` - **EXISTS** - Backend API
  - Request: `spec`, `project_id`, `source_file_id`
  - Response: `FindGapsResponse` with:
    - `gaps[]` (with severity, category, description, suggestion)
    - `ambiguities[]`
    - `statistics` (coverage, gap counts)

**3rd Party:** Google Gemini API (via backend `SpecAuditor`)

**Status:** ✅ Fully implemented

---

### 4.3 Refine Specification
**UI Component:** `SpecRefinementView` (gap selection and apply)  
**Functionality:** Apply gap suggestions to refine specification text  
**API Used:**
- `POST /api/generate/refine-spec` - **EXISTS** - Backend API
  - Request: `spec`, `gaps[]`, `apply_gap_ids[]` (optional filter)
  - Response: `RefineSpecResponse` with:
    - `refined_spec` (updated markdown)
    - `applied_gaps[]` (which gaps were applied)

**3rd Party:** Google Gemini API (via backend `SpecAuditor`)

**Status:** ✅ Fully implemented

---

### 4.4 Apply Refinement
**UI Component:** `SpecRefinementView` ("Accept Refinement" button)  
**Functionality:** Save refined specification back to file  
**API Used:**
- `PUT /api/files/{file_id}` - **EXISTS** - Backend API (updates file with refined content)

**Status:** ✅ Fully implemented

---

## 5. Verification

### 5.1 Run Dafny Verification
**UI Component:** `Header` ("Run Verification" button), `VerificationPanel` ("Run" button)  
**Functionality:** Statically verify Dafny specification code (does NOT execute code)  
**API Used:**
- `POST /api/verify` - **EXISTS** - Backend API
  - Request: `dafny_code`, `timeout_seconds`, `solver` (`z3` or `cvc5`), `verbosity`
  - Response: `VerifyResponse` with:
    - `verified` (boolean)
    - `verification_time_ms`
    - `results[]` (verification results per method/function)
    - `errors[]` (syntax/type/verification errors)
    - `warnings[]`
    - `solver_output` (raw Dafny output)

**What it verifies:**
- ✅ **Syntax correctness** - Valid Dafny syntax
- ✅ **Type checking** - Type safety (no type errors)
- ✅ **Proof obligations** - Mathematical proofs of:
  - Preconditions (requirements before method call)
  - Postconditions (guarantees after method execution)
  - Loop invariants (properties maintained during loops)
  - Termination (loops decrease and terminate)
  - Assertions (properties hold at specific points)
- ❌ **Does NOT execute code** - No runtime execution or test cases
- ❌ **Does NOT need implementation** - Only verifies the specification itself

**How it works:**
1. Writes Dafny code to temporary `.dfy` file
2. Runs `dafny verify <file>` command (static analysis)
3. Uses SMT solver (Z3/CVC5) to mathematically prove properties
4. Parses output to extract verification results

**3rd Party:** Dafny compiler + SMT solver (Z3/CVC5) via backend subprocess

**Status:** ✅ Fully implemented

---

### 5.2 Display Verification Results
**UI Component:** `VerificationPanel`, `CodeEditor` (error highlighting)  
**Functionality:** Show proof obligations, errors, warnings  
**API Used:**
- Uses data from `POST /api/verify` response

**Status:** ✅ Fully implemented

---

## 6. Traceability

### 6.1 View Traceability Links
**UI Component:** `TraceabilityView`  
**Functionality:** Show bidirectional mapping between requirements and Dafny code  
**API Used:**
- `GET /api/files/{file_id}/traceability` - **EXISTS** - Backend API
  - Returns `TraceabilityResponse` with:
    - `source_file_id`
    - `links[]` (unit links with line ranges, verification status)

**Status:** ✅ Fully implemented

---

### 6.2 Navigate to Linked Unit
**UI Component:** `MarkdownEditor` (unit link badges), `TraceabilityView`  
**Functionality:** Click traceability link to open corresponding Dafny file  
**API Used:**
- `GET /api/files/{file_id}` - **EXISTS** - Backend API (loads linked Dafny file)

**Status:** ✅ Fully implemented

---

## 7. Deconstruction (Units)

### 7.1 Deconstruct Spec to Units
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Break down specification into verifiable units  
**API Used:**
- `POST /api/deconstruct` - **EXISTS** - Backend API
  - Request: `project_id`, `source_file_id`, `strategy` (`auto` or `manual`), `max_units`, `unit_boundaries`
  - Response: `DeconstructResponse` with:
    - `units[]` (unit info with Dafny code)
    - `links[]` (unit-to-source traceability links)
    - `statistics` (success/failure counts)
    - `errors[]`

**3rd Party:** Google Gemini API (via backend `UnitIdentifier`)

**Status:** ⚠️ API exists but not exposed in UI (units are auto-created during spec generation)

---

## 8. AI Assistant (Chat)

### 8.1 Chat with Verification Assistant
**UI Component:** `GeminiInsightPanel`  
**Functionality:** Ask questions about verification errors, Dafny syntax, proof obligations  
**API Used:**
- `POST /api/assistant/chat` - **EXISTS** - Backend API
  - Request: `message`, `context` (optional: code, location, error), `history[]` (optional)
  - Response: `ChatResponse` with:
    - `content` (assistant response)
    - `suggestions[]` (follow-up suggestions)

**3rd Party:** Google Gemini API (via backend `SpecAuditor`)

**Status:** ⚠️ Partially implemented (placeholder response, full conversation not implemented)

---

## 9. GitHub Integration

### 9.1 List GitHub Installations
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Get GitHub App installations for user  
**API Used:**
- `GET /api/github/installations` - **DOES NOT EXIST** - Frontend expects this but backend doesn't implement it
  - Frontend code in `github-context.tsx` calls this endpoint

**3rd Party:** GitHub API (via backend)

**Status:** ❌ Not implemented (frontend expects it but backend missing)

---

### 9.2 List Repositories for Installation
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Get repositories for a GitHub App installation  
**API Used:**
- `GET /api/github/installations/{installation_id}/repositories` - **DOES NOT EXIST** - Frontend expects this but backend doesn't implement it

**3rd Party:** GitHub API (via backend)

**Status:** ❌ Not implemented (frontend expects it but backend missing)

---

### 9.3 Import Repository
**UI Component:** (Not currently exposed in UI, but API exists)  
**Functionality:** Import GitHub repository as project  
**API Used:**
- `POST /api/github/repositories/import` - **DOES NOT EXIST** - Frontend expects this but backend doesn't implement it

**3rd Party:** GitHub API (via backend)

**Status:** ❌ Not implemented (frontend expects it but backend missing)

---

### 9.4 Create Pull Request
**UI Component:** `PRCreator`  
**Functionality:** Submit verified changes to GitHub as PR  
**API Used:**
- `POST /api/github/pull-requests` - **DOES NOT EXIST** - Frontend expects this but backend doesn't implement it
  - Request: `repository_id`, `files[]`, `title`, `body`, `draft`

**3rd Party:** GitHub API (via backend)

**Status:** ❌ Not implemented (frontend expects it but backend missing)

---

### 9.5 GitHub Webhook Handler
**UI Component:** N/A (backend endpoint)  
**Functionality:** Handle GitHub webhook events (PR checks, etc.)  
**API Used:**
- `POST /api/webhooks` - **EXISTS** - Backend API (GitHub webhook receiver)

**Status:** ✅ Backend implemented (not directly used by UI)

---

## 10. Health & Status

### 10.1 Health Check
**UI Component:** `ProjectContext` (on mount)  
**Functionality:** Check backend health and service availability  
**API Used:**
- `GET /api/health` - **EXISTS** - Backend API
  - Response: `HealthResponse` with:
    - `status` (`ok`)
    - `gemini_configured` (boolean)
    - `dafny_available` (boolean)

**Status:** ✅ Fully implemented

---

## 11. UI-Only Features (No API)

### 11.1 Theme Toggle
**UI Component:** `ThemeToggle`, `Header`  
**Functionality:** Switch between light/dark theme  
**API Used:** None (localStorage)

**Status:** ✅ Fully implemented

---

### 11.2 View Mode Toggle
**UI Component:** `Header` (Trace/Edit toggle)  
**Functionality:** Switch between Traceability view and Edit view  
**API Used:** None (local state)

**Status:** ✅ Fully implemented

---

### 11.3 File Explorer Collapse/Expand
**UI Component:** `ProjectExplorer`  
**Functionality:** Collapse/expand sidebar  
**API Used:** None (local state)

**Status:** ✅ Fully implemented

---

### 11.4 Terminal Panel
**UI Component:** `TerminalPanel`  
**Functionality:** Display logs and terminal output  
**API Used:** None (displays logs from `ProjectContext` state)

**Status:** ✅ Fully implemented

---

## Summary

### Backend APIs (FastAPI)
- **Total Endpoints:** 20+
- **Fully Implemented:** 18
- **Partially Implemented:** 1 (`/api/assistant/chat` - placeholder)
- **Missing:** 4 (GitHub integration endpoints)

### 3rd Party APIs
- **Google Gemini API:** Used via backend for:
  - Specification generation
  - Gap detection
  - Specification refinement
  - Unit identification
  - Chat assistant (placeholder)
- **GitHub API:** Used via backend for:
  - OAuth authentication ✅
  - Webhook handling ✅
  - Installations ❌ (not implemented)
  - Repositories ❌ (not implemented)
  - Pull requests ❌ (not implemented)
- **Dafny Compiler:** Used via backend subprocess for verification ✅

### Formally Verifiable Components

The following components are good candidates for formal verification:

1. **File Operations** (`/api/files/*`)
   - Atomic file updates
   - Project ownership verification
   - File uniqueness constraints

2. **Project Management** (`/api/projects/*`)
   - Project ownership isolation
   - Cascade deletion semantics
   - Project structure consistency

3. **Verification Pipeline** (`/api/verify`)
   - Input validation
   - Timeout handling
   - Error parsing correctness

4. **Traceability Links** (`/api/files/{file_id}/traceability`)
   - Link consistency (source ranges match file content)
   - Unit-to-source mapping correctness

5. **Specification Generation** (`/api/generate/spec`)
   - Unit creation consistency
   - Traceability matrix correctness
   - File naming uniqueness

---

## Notes

- Most UI functionality is fully implemented and working
- GitHub integration features are partially implemented (frontend exists but backend endpoints missing)
- AI chat assistant is a placeholder (returns static response)
- File operations use caching (5-minute TTL) for performance
- Auto-save uses debouncing (2-second delay) to reduce API calls
- Project ownership is enforced via API key hash or user_id (supports anonymous + authenticated users)

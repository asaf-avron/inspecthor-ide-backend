# Project Structure Analysis

## Overview

This document provides a comprehensive structural analysis of both projects in the Guardian Gateway workspace:
- `guardian-gateway` - Backend API and core verification engine
- `v0-guardian-gateway-ide` - Frontend Next.js IDE application

**Analysis Date:** January 28, 2026

---

## Project 1: guardian-gateway

### Root Directory Structure

```
guardian-gateway/
├── .cursorrules
├── .dockerignore
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── verify-dafny.yml
├── api/
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 001_add_projects_and_unit_links.py
│   │       └── 002_add_renamed_field_to_files.py
│   ├── alembic.ini
│   ├── auth.py (386 lines)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── adapters.py (248 lines)
│   │   ├── file_operations.py (266 lines)
│   │   ├── migration.py (100 lines)
│   │   ├── models.py (211 lines)
│   │   └── project_management.py (169 lines)
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── python_crawler.py (320 lines)
│   │   └── typescript_crawler.py (145 lines)
│   ├── database.py (618 lines)
│   ├── deconstruct.py (469 lines)
│   ├── files.py (405 lines)
│   ├── github/
│   │   ├── __init__.py
│   │   ├── api_client.py (449 lines)
│   │   ├── app.py (253 lines)
│   │   ├── checks.py (177 lines)
│   │   ├── commits.py (229 lines)
│   │   └── webhooks.py (411 lines)
│   ├── main.py (601 lines)
│   ├── middleware.py (301 lines)
│   ├── models.py (403 lines)
│   ├── projects.py (616 lines)
│   ├── README.md
│   ├── requirements.txt
│   ├── transpiler/
│   │   ├── __init__.py
│   │   ├── gemini.py (291 lines)
│   │   └── merger.py (280 lines)
│   ├── verification/
│   │   ├── contract_translator.py (177 lines)
│   │   ├── dafny_runner.py (164 lines)
│   │   ├── file_operations.dfy (187 lines)
│   │   ├── models.dfy (62 lines)
│   │   ├── project_management.dfy (111 lines)
│   │   ├── project_migration.dfy (85 lines)
│   │   ├── spec_generation.dfy (55 lines)
│   │   └── traceability.dfy (49 lines)
│   └── verification.py (183 lines)
├── assets/
│   ├── demo/
│   │   └── rewards.dfy (34 lines)
│   └── examples/
│       ├── bank_transfer.json
│       └── voting.json
├── complete_spec-first_implementation.patch (1778 lines)
├── core/
│   ├── __init__.py (23 lines)
│   ├── auditor.py (476 lines)
│   ├── gateway.py (504 lines)
│   ├── parser.py (227 lines)
│   └── workflow.py (482 lines)
├── dev-backend.sh
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.api
├── docs/
│   ├── architecture/
│   │   ├── Guardian_02_Architecture_HLD.md
│   │   ├── Guardian_03_Methodology_Dafny.md
│   │   ├── Guardian_09_Security_Integrity.md
│   │   └── Guardian_10_Production_Roadmap.md
│   ├── ARCHITECTURE.md
│   ├── EXPERT_REQUIREMENTS.md
│   ├── experts/
│   │   ├── architect/
│   │   │   └── SPEC_FIRST_TRANSITION_PLAN.md
│   │   └── oracle/
│   │       └── SPEC_FIRST_TRANSITION_PLAN.md
│   ├── FORMAL_VERIFICATION_PLAN.md (753 lines)
│   ├── GITHUB_APP_LOCALHOST_SETUP.md
│   ├── GITHUB_APP_SETUP.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── instructions/
│   │   ├── Cursor_Build_Lens.md
│   │   ├── Cursor_Workflow.md
│   │   └── Spec_Process_Guide.md
│   ├── knowledge/
│   │   └── dafny_ref.md
│   ├── README.md
│   ├── SAMPLE_SPECS_FOR_EXPERTS.md (310 lines)
│   ├── SECURITY.md
│   ├── specs/
│   │   ├── dev/
│   │   │   ├── archive/
│   │   │   │   ├── Dev_Spec_Auto_Sepc_Refinement.md
│   │   │   │   ├── Dev_Spec_Interactive_Review.md
│   │   │   │   ├── Dev_Spec_Unified_Integration.md
│   │   │   │   ├── Guardian_01_Vision_Strategy.md
│   │   │   │   ├── Guardian_04_PRD_MVP.md
│   │   │   │   ├── Guardian_05_Demo_Script.md
│   │   │   │   └── Guardian_08_UX_Spec_Canvas.md
│   │   │   ├── Dev_Spec_Deconstruct_To_Units.md (608 lines)
│   │   │   ├── Dev_Spec_File_Operations.md (554 lines)
│   │   │   ├── Dev_Spec_Project_Management.md (976 lines)
│   │   │   └── implemented/
│   │   │       ├── Dev_Spec_Auditor.md
│   │   │       ├── Dev_Spec_Compiler.md
│   │   │       ├── Dev_Spec_Doc_Aware_Auditor.md
│   │   │       ├── Dev_Spec_Dynamic_Few-Shot_Gateway.md
│   │   │       ├── Dev_Spec_Lens.md
│   │   │       ├── Dev_Spec_Product_Flow.md
│   │   │       └── Dev_Spec_Traceability.md
│   │   ├── Draft_01_Rewards_System.md
│   │   └── Gap_Analysis_Report.md
│   ├── templates/
│   │   ├── Guardian_07_Spec_Template.md
│   │   └── Template_Architects_Canvas.md
│   ├── development/UI_API_MAPPING.md (554 lines)
│   ├── development/UI_BACKEND_INTEGRATION_PLAN.md (350 lines)
│   ├── reports/verification/VERIFICATION_STATUS.md
│   └── Z3_AND_TESTING_FIXES.md
├── frontend/
│   └── app/
│       └── page.tsx (159 lines)
├── github-app-private-key.pem
├── guardian_gateway.db
├── README.md
├── requirements.txt
├── scripts/
│   ├── dev-docker.sh
│   ├── generate_test_vectors.py (206 lines)
│   ├── organize-docs.sh
│   ├── synthesize_core.py (202 lines)
│   └── verify_dafny.sh (25 lines)
├── spec_first_transition.patch (2084 lines)
├── test.db
└── tests/
    ├── conftest.py (71 lines)
    ├── fixtures/
    │   └── interface.dfy (41 lines)
    └── oracle/
        ├── __init__.py
        └── test_core_oracle.py (211 lines)
```

### Key Directories

#### `/api` - FastAPI Backend
- **Purpose:** REST API endpoints, database models, authentication, GitHub integration
- **Key Files:**
  - `main.py` - FastAPI application entry point
  - `database.py` - SQLAlchemy models and database initialization
  - `projects.py` - Project CRUD operations
  - `files.py` - File management endpoints
  - `auth.py` - Authentication and authorization
  - `verification.py` - Dafny verification endpoints

#### `/api/core` - Functional Core Layer
- **Purpose:** Pure business logic matching Dafny specifications
- **Files:**
  - `models.py` - Core data models
  - `project_management.py` - Project operations (create, delete)
  - `file_operations.py` - File operations
  - `adapters.py` - Adapters between DB and core models
  - `migration.py` - Project migration logic

#### `/api/verification` - Dafny Specifications
- **Purpose:** Formal specifications for core operations
- **Files:** All `.dfy` files containing Dafny contracts

#### `/api/github` - GitHub Integration
- **Purpose:** GitHub App, webhooks, API client, commit checks
- **Files:**
  - `app.py` - GitHub App initialization
  - `webhooks.py` - Webhook handlers
  - `api_client.py` - GitHub API client
  - `commits.py` - Commit processing
  - `checks.py` - Status checks

#### `/core` - Core Verification Engine
- **Purpose:** Standalone verification logic (no FastAPI dependencies)
- **Files:**
  - `gateway.py` - Code verification engine
  - `workflow.py` - Specification workflow (Triage → Structure → Audit)
  - `auditor.py` - Specification auditor
  - `parser.py` - Specification parser

#### `/docs` - Documentation
- **Purpose:** Architecture docs, specs, implementation guides
- **Structure:**
  - `architecture/` - High-level architecture documents
  - `specs/dev/` - Development specifications
  - `experts/` - Expert-specific transition plans
  - `instructions/` - User guides

#### `/tests` - Test Suite
- **Purpose:** Unit tests and test fixtures
- **Files:**
  - `conftest.py` - Pytest configuration
  - `oracle/test_core_oracle.py` - Oracle tests for core logic

---

## Project 2: v0-guardian-gateway-ide

### Root Directory Structure

```
v0-guardian-gateway-ide/
├── .dockerignore
├── .gitignore
├── app/
│   ├── api/
│   │   └── auth/
│   │       ├── github/
│   │       │   └── callback/
│   │       │       └── route.ts (93 lines)
│   │       ├── logout/
│   │       │   └── route.ts (35 lines)
│   │       ├── me/
│   │       │   └── route.ts (35 lines)
│   │       └── refresh/
│   │           └── route.ts (62 lines)
│   ├── app/
│   │   ├── [projectId]/
│   │   │   └── page.tsx (473 lines)
│   │   └── page.tsx (79 lines)
│   ├── auth/
│   │   └── github/
│   │       └── callback/
│   │           └── page.tsx (132 lines)
│   ├── dashboard/
│   │   └── page.tsx (31 lines)
│   ├── globals.css (204 lines)
│   ├── layout.tsx (45 lines)
│   └── page.tsx (21 lines)
├── components/
│   ├── auth/
│   │   ├── login-modal.tsx (129 lines)
│   │   └── user-menu.tsx (156 lines)
│   ├── github/
│   │   ├── pr-creator.tsx (251 lines)
│   │   └── repo-picker.tsx (176 lines)
│   ├── ide/
│   │   ├── code-editor.tsx (226 lines)
│   │   ├── gemini-insight-panel.tsx (301 lines)
│   │   ├── header.tsx (199 lines)
│   │   ├── markdown-editor.tsx (473 lines)
│   │   ├── project-explorer.tsx (824 lines)
│   │   ├── projects-dashboard.tsx (152 lines)
│   │   ├── save-status-indicator.tsx (60 lines)
│   │   ├── spec-refinement-view.tsx (531 lines)
│   │   ├── terminal-panel.tsx (125 lines)
│   │   ├── traceability-view.tsx (466 lines)
│   │   └── verification-panel.tsx (219 lines)
│   ├── project/
│   │   └── create-project-modal.tsx (136 lines)
│   ├── theme-provider.tsx (11 lines)
│   ├── theme-toggle.tsx (112 lines)
│   └── ui/
│       ├── alert-dialog.tsx (133 lines)
│       ├── avatar.tsx (50 lines)
│       ├── button.tsx (60 lines)
│       ├── card.tsx (92 lines)
│       ├── dialog.tsx (125 lines)
│       ├── dropdown-menu.tsx (257 lines)
│       ├── input.tsx (21 lines)
│       ├── label.tsx (26 lines)
│       ├── popover.tsx (48 lines)
│       ├── tabs.tsx (66 lines)
│       └── tooltip.tsx (61 lines)
├── components.json
├── Dockerfile
├── IMPLEMENTATION_SUMMARY.md (211 lines)
├── lib/
│   ├── api-client.ts (491 lines)
│   ├── auth-context.tsx (253 lines)
│   ├── crawler/
│   │   └── index.ts (191 lines)
│   ├── github-context.tsx (217 lines)
│   ├── hooks/
│   │   └── useAutoSave.ts (195 lines)
│   ├── local-storage.ts (311 lines)
│   ├── project-context.tsx (1471 lines)
│   ├── types.ts (462 lines)
│   └── utils.ts (6 lines)
├── next.config.mjs
├── package.json
├── pnpm-lock.yaml (3912 lines)
├── postcss.config.mjs
├── public/
│   ├── apple-icon.png
│   ├── icon-dark-32x32.png
│   ├── icon-light-32x32.png
│   ├── icon.svg
│   ├── logo-dark.png (12590 lines - binary)
│   ├── logo.png (12804 lines - binary)
│   ├── placeholder-logo.png
│   ├── placeholder-logo.svg
│   ├── placeholder-user.jpg
│   ├── placeholder.jpg
│   └── placeholder.svg
├── README.md
├── styles/
│   └── globals.css
└── tsconfig.json
```

### Key Directories

#### `/app` - Next.js App Router
- **Purpose:** Next.js 13+ App Router pages and API routes
- **Structure:**
  - `app/[projectId]/page.tsx` - Main IDE page for a project
  - `app/api/auth/` - Authentication API routes
  - `app/auth/github/callback/` - OAuth callback page

#### `/components` - React Components
- **Purpose:** Reusable UI components
- **Structure:**
  - `ide/` - IDE-specific components (editors, panels, views)
  - `ui/` - Base UI components (buttons, dialogs, etc.)
  - `auth/` - Authentication components
  - `github/` - GitHub integration components
  - `project/` - Project management components

#### `/lib` - Library Code
- **Purpose:** Business logic, contexts, utilities
- **Key Files:**
  - `project-context.tsx` - Main project state management (1471 lines)
  - `api-client.ts` - API client wrapper
  - `auth-context.tsx` - Authentication context
  - `types.ts` - TypeScript type definitions
  - `local-storage.ts` - Local storage utilities

#### `/public` - Static Assets
- **Purpose:** Images, icons, static files

---

## Files Exceeding Best Practices

### Best Practice Thresholds
- **File Size:** >300 lines (recommended: <300 lines per file)
- **Method/Function Size:** >50 lines (recommended: <50 lines per function)

### guardian-gateway - Large Files (>300 lines)

#### Very Large Files (>500 lines)
1. **`api/database.py`** - 618 lines
   - **Purpose:** SQLAlchemy models and database initialization
   - **Structure:** Multiple model classes (User, Project, File, UnitLink, Installation, Repository, Anchor, ProofReceipt)
   - **Large Methods:**
     - `init_db()` - ~60 lines (database initialization with enum cleanup)

2. **`api/projects.py`** - 616 lines
   - **Purpose:** Project CRUD endpoints
   - **Large Methods:**
     - `create_project()` - ~60 lines
     - `list_projects()` - ~50 lines
     - `get_project_structure()` - ~60 lines
     - `update_project()` - ~80 lines
     - `delete_project()` - ~50 lines
     - `migrate_anonymous_projects_to_user()` - ~50 lines

3. **`api/main.py`** - 601 lines
   - **Purpose:** FastAPI application entry point and main endpoints
   - **Large Methods:**
     - `generate_spec()` - ~280 lines (complex unit deconstruction logic)
     - `find_gaps()` - ~60 lines
     - `refine_spec()` - ~80 lines

4. **`core/gateway.py`** - 504 lines
   - **Purpose:** Code verification engine
   - **Structure:** Verification logic, transpilation
   - **Large Methods:**
     - `verify_code()` - ~100+ lines (main verification flow)

5. **`core/workflow.py`** - 482 lines
   - **Purpose:** Specification workflow engine
   - **Structure:** Triage, Structure, Audit stages
   - **Large Methods:**
     - `run_triage()` - ~50 lines
     - `run_structuring()` - ~80 lines
     - `audit_spec()` - ~100+ lines

6. **`core/auditor.py`** - 476 lines
   - **Purpose:** Specification auditor
   - **Large Methods:**
     - `audit_spec()` - ~150+ lines (main audit logic)

7. **`api/deconstruct.py`** - 469 lines
   - **Purpose:** Specification deconstruction to units
   - **Large Methods:**
     - `deconstruct_spec()` - ~200+ lines (complex unit extraction)

8. **`api/github/api_client.py`** - 449 lines
   - **Purpose:** GitHub API client wrapper
   - **Large Methods:**
     - Multiple API methods (~30-50 lines each)

9. **`api/github/webhooks.py`** - 411 lines
   - **Purpose:** GitHub webhook handlers
   - **Large Methods:**
     - `handle_push_event()` - ~80 lines
     - `handle_pull_request_event()` - ~100+ lines

10. **`api/files.py`** - 405 lines
    - **Purpose:** File management endpoints
    - **Large Methods:**
      - `save_file()` - ~60 lines
      - `update_file()` - ~80 lines
      - `get_file()` - ~50 lines

11. **`api/models.py`** - 403 lines
    - **Purpose:** Pydantic request/response models
    - **Structure:** Multiple model classes

12. **`api/auth.py`** - 386 lines
    - **Purpose:** Authentication and authorization
    - **Large Methods:**
      - `get_current_user()` - ~50 lines
      - OAuth flow handlers

#### Medium-Large Files (300-400 lines)
- `api/middleware.py` - 301 lines
- `api/crawler/python_crawler.py` - 320 lines
- `api/transpiler/gemini.py` - 291 lines
- `api/transpiler/merger.py` - 280 lines
- `api/core/file_operations.py` - 266 lines
- `api/github/app.py` - 253 lines
- `api/core/adapters.py` - 248 lines
- `core/parser.py` - 227 lines
- `api/github/commits.py` - 229 lines
- `api/verification.py` - 183 lines
- `api/verification/contract_translator.py` - 177 lines
- `api/github/checks.py` - 177 lines
- `api/core/project_management.py` - 169 lines
- `api/verification/dafny_runner.py` - 164 lines

### v0-guardian-gateway-ide - Large Files (>300 lines)

#### Very Large Files (>500 lines)
1. **`lib/project-context.tsx`** - 1471 lines
   - **Purpose:** Main project state management context
   - **Structure:** 
     - State type definitions (~100 lines)
     - Reducer function (~150 lines)
     - Multiple action handlers (~1200 lines)
   - **Large Methods:**
     - `projectReducer()` - ~150 lines
     - `generateSpec()` - ~120 lines
     - `loadProjectFromUrl()` - ~60 lines
     - `loadFile()` - ~80 lines
     - `selectFile()` - ~30 lines
     - `deconstructToUnits()` - ~80 lines
     - Multiple other handlers (50-100 lines each)

2. **`components/ide/project-explorer.tsx`** - 824 lines
   - **Purpose:** File tree explorer component
   - **Structure:**
     - File tree rendering
     - Project switcher
     - File operations (create, delete, rename)
   - **Large Methods:**
     - `ProjectExplorer` component - ~500 lines
     - `FileTreeItem` component - ~180 lines
     - `loadProjects()` - ~20 lines

3. **`components/ide/spec-refinement-view.tsx`** - 531 lines
   - **Purpose:** Specification refinement UI
   - **Large Methods:**
     - Main component - ~400+ lines

4. **`lib/api-client.ts`** - 491 lines
   - **Purpose:** API client wrapper for backend calls
   - **Structure:** Multiple API methods
   - **Large Methods:**
     - Individual API methods (~30-50 lines each)

5. **`components/ide/markdown-editor.tsx`** - 473 lines
   - **Purpose:** Markdown editor component
   - **Large Methods:**
     - Main component - ~400+ lines

6. **`app/app/[projectId]/page.tsx`** - 473 lines
   - **Purpose:** Main IDE page
   - **Large Methods:**
     - Main page component - ~400+ lines

7. **`components/ide/traceability-view.tsx`** - 466 lines
   - **Purpose:** Traceability matrix view
   - **Large Methods:**
     - Main component - ~400+ lines

8. **`lib/types.ts`** - 462 lines
   - **Purpose:** TypeScript type definitions
   - **Structure:** Multiple type/interface definitions

#### Medium-Large Files (300-400 lines)
- `lib/local-storage.ts` - 311 lines
- `components/ide/gemini-insight-panel.tsx` - 301 lines
- `lib/auth-context.tsx` - 253 lines
- `components/github/pr-creator.tsx` - 251 lines
- `components/ui/dropdown-menu.tsx` - 257 lines
- `lib/github-context.tsx` - 217 lines
- `components/ide/verification-panel.tsx` - 219 lines
- `components/ide/header.tsx` - 199 lines
- `lib/hooks/useAutoSave.ts` - 195 lines
- `lib/crawler/index.ts` - 191 lines

---

## Methods/Functions Exceeding Best Practices (>50 lines)

### guardian-gateway

#### `api/main.py`
- **`generate_spec()`** - ~280 lines
  - **Issue:** Extremely long method handling multiple concerns (triage, structure, audit, unit deconstruction)
  - **Recommendation:** Split into smaller functions: `_handle_triage()`, `_handle_structure()`, `_handle_audit()`, `_handle_unit_deconstruction()`

#### `api/projects.py`
- **`update_project()`** - ~80 lines
  - **Issue:** Complex validation and update logic
  - **Recommendation:** Extract validation to separate function

#### `api/deconstruct.py`
- **`deconstruct_spec()`** - ~200+ lines
  - **Issue:** Very long method with complex unit extraction logic
  - **Recommendation:** Split into: `_identify_units()`, `_extract_unit_content()`, `_create_unit_files()`, `_create_unit_links()`

#### `core/auditor.py`
- **`audit_spec()`** - ~150+ lines
  - **Issue:** Long method handling multiple audit concerns
  - **Recommendation:** Split into: `_analyze_gaps()`, `_analyze_ambiguities()`, `_build_traceability()`, `_generate_dafny()`

#### `core/gateway.py`
- **`verify_code()`** - ~100+ lines
  - **Issue:** Long verification flow
  - **Recommendation:** Extract sub-steps: `_transpile_code()`, `_run_dafny()`, `_parse_results()`

#### `core/workflow.py`
- **`run_structuring()`** - ~80 lines
- **`audit_spec()`** - ~100+ lines

#### `api/github/webhooks.py`
- **`handle_pull_request_event()`** - ~100+ lines
- **`handle_push_event()`** - ~80 lines

### v0-guardian-gateway-ide

#### `lib/project-context.tsx`
- **`projectReducer()`** - ~150 lines
  - **Issue:** Large reducer with many cases
  - **Recommendation:** Split into multiple reducers or use reducer composition

- **`generateSpec()`** - ~120 lines
  - **Issue:** Long method handling spec generation and unit creation
  - **Recommendation:** Split into: `_callGenerateSpec()`, `_handleFilenameSuggestion()`, `_handleUnitsCreation()`, `_handleRootDafny()`

- **`loadFile()`** - ~80 lines
  - **Issue:** Complex caching and loading logic
  - **Recommendation:** Extract: `_checkCache()`, `_loadFromAPI()`, `_updateState()`

- **`deconstructToUnits()`** - ~80 lines
  - **Issue:** Long method with multiple concerns
  - **Recommendation:** Split into smaller helper functions

- **`loadProjectFromUrl()`** - ~60 lines
- **`selectFile()`** - ~30 lines (acceptable but could be split)
- **`renameFile()`** - ~70 lines
- **`createNewFile()`** - ~40 lines

#### `components/ide/project-explorer.tsx`
- **`ProjectExplorer` component** - ~500 lines
  - **Issue:** Very large component handling multiple concerns
  - **Recommendation:** Split into: `ProjectExplorerHeader`, `ProjectSwitcher`, `FileTree`, `ProjectExplorerFooter`

- **`FileTreeItem` component** - ~180 lines
  - **Issue:** Large component with inline logic
  - **Recommendation:** Extract: `FileIcon`, `VerificationIcon`, `FileContextMenu`, `RenameInput`

#### `components/ide/spec-refinement-view.tsx`
- **Main component** - ~400+ lines
  - **Issue:** Very large component
  - **Recommendation:** Split into: `GapList`, `AmbiguityList`, `StatisticsPanel`, `RefinementActions`

#### `components/ide/markdown-editor.tsx`
- **Main component** - ~400+ lines
  - **Issue:** Large editor component
  - **Recommendation:** Extract: `EditorToolbar`, `EditorContent`, `EditorStatusBar`

#### `app/app/[projectId]/page.tsx`
- **Main page component** - ~400+ lines
  - **Issue:** Large page component orchestrating multiple sub-components
  - **Recommendation:** Extract layout logic to separate components

---

## Summary Statistics

### guardian-gateway
- **Total Python Files:** ~50 files
- **Total Lines of Code:** ~11,293 lines (excluding assets/docs)
- **Files >300 lines:** 12 files
- **Files >500 lines:** 4 files
- **Largest File:** `api/database.py` (618 lines)
- **Average File Size:** ~226 lines

### v0-guardian-gateway-ide
- **Total TypeScript/TSX Files:** ~50 files
- **Total Lines of Code:** ~10,095 lines (excluding node_modules/public)
- **Files >300 lines:** 11 files
- **Files >500 lines:** 8 files
- **Largest File:** `lib/project-context.tsx` (1471 lines)
- **Average File Size:** ~202 lines

---

## Recommendations Summary

### High Priority Refactoring
1. **`lib/project-context.tsx`** (1471 lines) - Split into multiple contexts or use reducer composition
2. **`api/main.py::generate_spec()`** (280 lines) - Extract unit deconstruction logic to separate service
3. **`components/ide/project-explorer.tsx`** (824 lines) - Split into smaller components
4. **`api/deconstruct.py::deconstruct_spec()`** (200+ lines) - Extract unit processing logic

### Medium Priority Refactoring
1. **`core/auditor.py::audit_spec()`** (150+ lines) - Split audit stages
2. **`components/ide/spec-refinement-view.tsx`** (531 lines) - Component decomposition
3. **`api/projects.py`** (616 lines) - Extract validation logic
4. **`api/github/webhooks.py`** (411 lines) - Split webhook handlers

### Low Priority (Acceptable but Could Improve)
- Files between 300-400 lines are manageable but could benefit from extraction of helper functions
- Methods between 30-50 lines are generally acceptable but could be split if they handle multiple concerns

---

## Notes

- Binary files (images, PNGs) are excluded from line count analysis
- Documentation files (.md) are included in structure but not analyzed for code size
- Test files are included in structure
- Configuration files (package.json, tsconfig.json, etc.) are included but not analyzed for method size
- The analysis focuses on source code files (.py, .ts, .tsx, .dfy)

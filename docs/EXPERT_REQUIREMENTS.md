# Expert Requirements: Sources Needed for Formal Verification

This document lists the sources and information needed by the InspecThor experts to build the formal verification specifications.

---

## Status Summary

| Source | Status | Location | Purpose |
|--------|--------|----------|---------|
| Database Models | ✅ Available | `api/database.py` | Map SQLAlchemy → Dafny types |
| UI API Mapping | ✅ Available | `docs/UI_API_MAPPING.md` | Identify Core vs Shell |
| File Operations | ✅ Available | `api/files.py` | Current Python logic |
| Project Management | ✅ Available | `api/projects.py` | Current Python logic |
| Unit Identification | ✅ Available | `api/deconstruct.py` | Unit creation logic |
| **Sample English Spec** | ⚠️ **NEEDED** | N/A | Clover Loop demonstration |
| **Architecture Diagram** | ⚠️ **NEEDED** | N/A | Visual reference |

---

## 1. Database Models (`api/database.py`)

**Status:** ✅ Available  
**Location:** `C:\private-dev\guardian-gateway\api\database.py`

**Key Models:**
- `User` - GitHub OAuth user with tier/credits
- `Project` - Owned by `user_id` OR `api_key_hash` (anonymous)
- `File` - Belongs to project, has `file_type` (md/dfy/unit)
- `UnitLink` - Links root file → unit file → dafny file

**Critical Fields for Verification:**
```python
Project:
  - project_id: UUID (primary key)
  - name: String(255) - unique per owner
  - user_id: UUID (nullable) - authenticated owner
  - api_key_hash: String(64) (nullable) - anonymous owner
  - file_count: denormalized count

File:
  - file_id: UUID (primary key)
  - project_id: UUID (foreign key, CASCADE delete)
  - filename: String(255) - unique per project
  - content: Text
  - file_type: Enum('md', 'dfy', 'unit')
  - renamed: Boolean - tracks manual rename
```

**Expert Needs:**
- Map these to Dafny `datatype` definitions
- Handle UUID → string conversion
- Model nullable fields (`user_id` OR `api_key_hash`)

---

## 2. UI API Mapping (`docs/UI_API_MAPPING.md`)

**Status:** ✅ Available  
**Location:** `C:\private-dev\guardian-gateway\docs\UI_API_MAPPING.md`

**Key Information:**
- All API endpoints and their functionality
- Which endpoints are Functional Core vs Imperative Shell
- Request/response structures
- Ownership verification patterns

**Expert Needs:**
- Identify pure business logic (Core)
- Identify I/O operations (Shell)
- Understand API contracts for synthesis

---

## 3. File Operations Implementation (`api/files.py`)

**Status:** ✅ Available  
**Location:** `C:\private-dev\guardian-gateway\api\files.py`

**Key Functions:**
- `save_file()` - Creates file with ownership check
- `get_file()` - Loads file with ownership check
- `update_file()` - Updates content/rename with uniqueness check
- `delete_file()` - Deletes with ownership check
- `list_files()` - Lists files filtered by ownership

**Expert Needs:**
- Current Python logic for synthesis target
- Ownership verification pattern (`get_project_owner_filter`)
- Uniqueness check pattern (filename per project)

---

## 4. Project Management Implementation (`api/projects.py`)

**Status:** ✅ Available  
**Location:** `C:\private-dev\guardian-gateway\api\projects.py`

**Key Functions:**
- `create_project()` - Creates project, validates name uniqueness
- `list_projects()` - Lists with pagination, ownership filter
- `get_project_structure()` - Returns project + files
- `delete_project()` - Cascade deletes files (SQLAlchemy CASCADE)

**Expert Needs:**
- Cascade deletion semantics
- Name uniqueness per owner (case-insensitive)
- Migration logic (anonymous → authenticated)

---

## 5. Unit Identification Logic (`api/deconstruct.py`)

**Status:** ✅ Available  
**Location:** `C:\private-dev\guardian-gateway\api\deconstruct.py`

**Key Classes:**
- `UnitIdentifier` - Identifies units from markdown content
- `extract_content_by_lines()` - Extracts content by line range
- `create_unit_filename()` - Generates unit filenames

**Expert Needs:**
- How units are identified (line ranges, titles, requirements)
- How traceability links are created
- Unit-to-source mapping logic

---

## 6. Sample English Specification ✅ **PROVIDED**

**Status:** ✅ **AVAILABLE**  
**Location:** `docs/SAMPLE_SPECS_FOR_EXPERTS.md`  
**Purpose:** Demonstrate Clover Loop refinement process

**What's Included:**

1. **Example 1: Rewards System** - Simple transfer operation
2. **Example 2: Voting System** - Stateful system with multiple operations
3. **Example 3: File Management System** - Our actual use case (matches API)
4. **Example 4: Bank Transfer** - From existing assets/examples

**Each Example Includes:**
- Raw English Input (Gil's Input)
- Expected Refinement Flow (Triage → Structure → Audit → Units)
- Expected Dafny Output (conceptual)

**Special Request:**
- Experts should demonstrate Clover Loop using **Example 3 (File Management)** as it matches our API

---

## 7. Architecture Diagram ⚠️ **NEEDED**

**Status:** ⚠️ **REQUIRED FROM US**  
**Purpose:** Visual reference for InspecThor architecture

**What Experts Need:**
- The "Spec-First InspecThor Architecture" diagram mentioned in their feedback
- Shows: Clover Loop, Python Synthesis Loop, Oracle Test Generation
- Shows: Functional Core vs Imperative Shell separation

**Action Required:**
- Locate or recreate the architecture diagram
- Ensure it shows the synthesis loop clearly

---

## 8. Additional Context (Optional but Helpful)

### Current Verification Endpoint (`api/verification.py`)
- How Dafny verification is currently executed
- Output parsing logic
- Error handling

### Specification Generation (`api/main.py` - `generate_spec`)
- How English spec → Dafny conversion works
- Unit creation logic
- Traceability matrix generation

### Authentication (`api/auth.py`)
- How ownership is determined (`user_id` vs `api_key_hash`)
- Session management

---

## Recommended Delivery Package

To enable experts to build the formal verification specifications, provide:

### Package 1: Core Sources (Immediate)
1. ✅ `api/database.py` - Database models
2. ✅ `docs/UI_API_MAPPING.md` - API mapping
3. ✅ `api/files.py` - File operations
4. ✅ `api/projects.py` - Project management

### Package 2: Process Examples (High Priority)
5. ⚠️ **Sample English Spec** - Raw input + refinement flow
6. ⚠️ **Architecture Diagram** - Visual reference

### Package 3: Supporting Context (Helpful)
7. ✅ `api/deconstruct.py` - Unit identification
8. ✅ `api/verification.py` - Current verification logic
9. ✅ `api/main.py` - Spec generation endpoint

---

## Expert Deliverables Expected

Once sources are provided, experts will deliver:

1. **Optimized `models.dfy`**
   - Dafny datatypes matching database models
   - Ghost sets for performance
   - Opaque types for content

2. **Component Specifications**
   - `file_operations.dfy` (stateless functions)
   - `project_management.dfy` (cascade deletion)
   - `traceability.dfy` (link validation)
   - `spec_generation.dfy` (unit consistency)

3. **Python Synthesis Templates**
   - LLM prompt templates
   - icontract translation rules
   - Test vector generation scripts

4. **Clover Loop Demonstration**
   - Example English spec → Refined Dafny spec
   - Shows refinement process

---

## Next Actions

1. **Locate/Provide Architecture Diagram** → Experts need visual reference
2. **Create Sample English Spec Examples** → Demonstrate Clover Loop
3. **Package All Sources** → Send to experts for review
4. **Schedule Expert Review** → Get optimized specifications

---

## Questions for Experts

After providing sources, we should ask:

1. **Type Mapping:** How to handle UUID → string in Dafny?
2. **Nullable Fields:** Best way to model `user_id OR api_key_hash`?
3. **Content Opaque:** Should we use `Content` opaque type or hash?
4. **Synthesis Target:** What LLM should we use for Python synthesis?
5. **Test Vectors:** How to export Dafny test cases to JSON?

---

## File Checklist

- [x] `api/database.py` - Available
- [x] `docs/UI_API_MAPPING.md` - Available  
- [x] `api/files.py` - Available
- [x] `api/projects.py` - Available
- [x] `api/deconstruct.py` - Available
- [x] **Sample English Spec** - ✅ Created (`docs/SAMPLE_SPECS_FOR_EXPERTS.md`)
- [ ] **Architecture Diagram** - NEED TO LOCATE/CREATE (see note below)

**Note on Architecture Diagram:**
The experts referenced a "Spec-First InspecThor Architecture" diagram showing:
- Clover Loop (Gemini Refinement)
- Python Synthesis Loop (LLM + Oracle)
- Oracle Test Generation
- Functional Core vs Imperative Shell separation

If this diagram exists, please locate it. Otherwise, we can reference the architecture described in:
- `docs/architecture/Guardian_02_Architecture_HLD.md` (mentions similar concepts)
- The expert feedback itself (describes the architecture flow)

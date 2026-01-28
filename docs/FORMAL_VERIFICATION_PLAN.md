# Formal Verification Plan: InspecThor Spec-First Architecture

**Status:** Aligned with InspecThor Architecture - Spec-First Synthesis Loop

This document details the approach for formally verifying Guardian Gateway components using the **InspecThor Spec-First Architecture**, where Dafny specifications serve as the **Ground Truth** and Python code is **synthesized** via the Python Synthesis Loop (LLM + Oracle).

---

## Table of Contents

1. [Architectural Alignment](#architectural-alignment)
2. [Functional Core vs Imperative Shell](#functional-core-vs-imperative-shell)
3. [Component Specifications (Optimized)](#component-specifications-optimized)
4. [Python Synthesis Loop Integration](#python-synthesis-loop-integration)
5. [Oracle Test Generation](#oracle-test-generation)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Required Sources for Expert Review](#required-sources-for-expert-review)

---

## Architectural Alignment

### The InspecThor Protocol

**Core Principle:** The **Refined Dafny Spec (.dfy)** is the **Ground Truth**. Python code is **derived** from the spec, not manually aligned.

### Architecture Flow

```
English Spec (Gil's Input)
    ↓
Clover Loop (Gemini Refinement)
    ↓
Refined Dafny Spec (.dfy) ← GROUND TRUTH
    ↓
Native Dafny Compiler (Verification)
    ↓
Verified Code
    ↓
Python Synthesis Loop (LLM + Oracle)
    ↓
Best-Effort Python (+ icontracts)
    ↓
Oracle Test Generation
    ↓
Runtime Verification
```

### Rejected Approaches

❌ **Option 1 (Manual Reference):** Humans write Python to match Dafny  
❌ **Option 3 (Property Testing):** Tests derived from specs without synthesis  
✅ **Python Synthesis Loop:** Automated generation with runtime contract enforcement

---

## Functional Core vs Imperative Shell

### Separation of Concerns

**Functional Core (Dafny-Verified):**
- Pure state transition functions
- Business logic invariants
- Ownership checks
- Uniqueness constraints
- Cascade deletion logic

**Imperative Shell (Python I/O):**
- Database operations (SQLAlchemy)
- HTTP request/response handling
- File system operations
- External API calls (Gemini, GitHub)
- Dafny compiler subprocess execution

### Boundary Mapping

From `UI_API_MAPPING.md`, the **Functional Core** includes:

| Component | Core Logic | Shell Logic |
|-----------|-----------|-------------|
| File Operations | Ownership checks, uniqueness validation, state transitions | DB queries, HTTP responses |
| Project Management | Ownership isolation, cascade deletion, name uniqueness | DB transactions, file system |
| Verification Pipeline | ❌ **Moved to Shell** (parsing stdout is I/O) | Dafny subprocess, output parsing |
| Traceability Links | Range validation, link consistency | DB queries, file content reading |
| Spec Generation | Unit identification logic, traceability matrix | Gemini API calls, file creation |

---

## Component Specifications (Optimized)

### Performance Optimizations Applied

1. **Ghost Sets** instead of map quantification (O(1) vs O(N²))
2. **Opaque Types** for file content (avoid string verification overhead)
3. **Stateless Functions** (pure transitions, not global state)
4. **Pre-computed Indices** for line counting

---

## Component 1: File Operations (Stateless Functional Core)

### Optimized Dafny Specification

```dafny
module FileOperations {
  
  // ===== Data Types (Immutable) =====
  
  datatype FileType = MD | DFY | Unit
  
  // Opaque type for content (avoid string verification overhead)
  type Content = OpaqueType
  
  datatype File = File(
    fileId: string,
    projectId: string,
    filename: string,
    content: Content,  // Opaque - we don't verify content syntax
    fileType: FileType,
    sizeBytes: nat,
    ownerId: string
  )
  
  datatype Project = Project(
    projectId: string,
    name: string,
    ownerId: string,
    fileCount: nat  // Denormalized for performance
  )
  
  // State snapshot (immutable)
  datatype SystemState = SystemState(
    projects: map<string, Project>,
    files: map<string, File>,
    // Ghost set for O(1) uniqueness checks
    ghost activeFilenames: set<(string, string)>  // (projectId, filename)
  )
  
  // ===== Invariants =====
  
  predicate ValidState(state: SystemState)
  {
    // All files belong to existing projects
    (forall fileId :: fileId in state.files ==>
      state.files[fileId].projectId in state.projects) &&
    
    // File count consistency
    (forall projectId :: projectId in state.projects ==>
      state.projects[projectId].fileCount == CountFilesInProject(state, projectId)) &&
    
    // Ghost set matches actual files
    (forall fileId :: fileId in state.files ==>
      (state.files[fileId].projectId, state.files[fileId].filename) in state.activeFilenames) &&
    
    // Size consistency
    (forall fileId :: fileId in state.files ==>
      state.files[fileId].sizeBytes == GetContentSize(state.files[fileId].content))
  }
  
  function CountFilesInProject(state: SystemState, projectId: string): nat
  {
    |set fileId | fileId in state.files && state.files[fileId].projectId == projectId|
  }
  
  function GetContentSize(content: Content): nat
  
  // ===== Ownership Checks =====
  
  predicate OwnsProject(state: SystemState, projectId: string, ownerId: string)
  {
    projectId in state.projects &&
    state.projects[projectId].ownerId == ownerId
  }
  
  predicate OwnsFile(state: SystemState, fileId: string, ownerId: string)
  {
    fileId in state.files &&
    OwnsProject(state, state.files[fileId].projectId, ownerId)
  }
  
  // ===== Pure State Transition Functions =====
  
  // Save File: Pure function that returns new state
  function SaveFile(
    state: SystemState,
    projectId: string,
    filename: string,
    content: Content,
    fileType: FileType,
    ownerId: string
  ): (newState: SystemState, result: Result<string>)  // Returns (newState, fileId or error)
    requires ValidState(state)
    requires OwnsProject(state, projectId, ownerId)
    requires (projectId, filename) !in state.activeFilenames  // O(1) check via ghost set
    ensures ValidState(newState)
    ensures result.Success? ==> result.value in newState.files
    ensures result.Success? ==> newState.files[result.value].projectId == projectId
    ensures result.Success? ==> newState.files[result.value].filename == filename
    ensures result.Success? ==> (projectId, filename) in newState.activeFilenames
    ensures result.Success? ==> OwnsFile(newState, result.value, ownerId)
  {
    var fileId := GenerateFileId();
    var newFile := File(fileId, projectId, filename, content, fileType, GetContentSize(content), ownerId);
    
    var newFiles := state.files[fileId := newFile];
    var newActiveFilenames := state.activeFilenames + {(projectId, filename)};
    
    // Update project file count
    var project := state.projects[projectId];
    var updatedProject := Project(
      project.projectId,
      project.name,
      project.ownerId,
      project.fileCount + 1
    );
    var newProjects := state.projects[projectId := updatedProject];
    
    var newState := SystemState(newProjects, newFiles, newActiveFilenames);
    (newState, Success(fileId))
  }
  
  // Update File: Pure function
  function UpdateFile(
    state: SystemState,
    fileId: string,
    newContent: Content,
    newFilename: string,  // Empty string means no rename
    ownerId: string
  ): (newState: SystemState, result: Result<bool>)
    requires ValidState(state)
    requires OwnsFile(state, fileId, ownerId)
    requires newFilename == "" || (state.files[fileId].projectId, newFilename) !in state.activeFilenames
    ensures ValidState(newState)
    ensures result.Success? && result.value == true ==>
      newState.files[fileId].content == newContent &&
      (newFilename != "" ==> newState.files[fileId].filename == newFilename)
    ensures result.Success? && result.value == true ==>
      OwnsFile(newState, fileId, ownerId)
  {
    var file := state.files[fileId];
    var projectId := file.projectId;
    
    var updatedFilename := if newFilename != "" then newFilename else file.filename;
    var updatedActiveFilenames := state.activeFilenames;
    
    // Update ghost set if renaming
    if newFilename != "" && newFilename != file.filename {
      updatedActiveFilenames := (updatedActiveFilenames - {(projectId, file.filename)}) + {(projectId, newFilename)};
    }
    
    var updatedFile := File(
      file.fileId,
      file.projectId,
      updatedFilename,
      newContent,
      file.fileType,
      GetContentSize(newContent),
      file.ownerId
    );
    
    var newFiles := state.files[fileId := updatedFile];
    var newState := SystemState(state.projects, newFiles, updatedActiveFilenames);
    (newState, Success(true))
  }
  
  // Get File: Pure function
  function GetFile(
    state: SystemState,
    fileId: string,
    ownerId: string
  ): (file: File?)
    requires ValidState(state)
    ensures file != null ==> OwnsFile(state, fileId, ownerId)
    ensures file != null ==> file.fileId == fileId
  {
    if fileId in state.files && OwnsFile(state, fileId, ownerId) {
      file := state.files[fileId];
    } else {
      file := null;
    }
  }
  
  // Delete File: Pure function
  function DeleteFile(
    state: SystemState,
    fileId: string,
    ownerId: string
  ): (newState: SystemState, result: Result<bool>)
    requires ValidState(state)
    requires OwnsFile(state, fileId, ownerId)
    ensures ValidState(newState)
    ensures result.Success? && result.value == true ==>
      fileId !in newState.files
    ensures result.Success? && result.value == true ==>
      (state.files[fileId].projectId, state.files[fileId].filename) !in newState.activeFilenames
  {
    var file := state.files[fileId];
    var projectId := file.projectId;
    
    // Remove from files map
    var newFiles := state.files[fileId := *];
    
    // Remove from ghost set
    var newActiveFilenames := state.activeFilenames - {(projectId, file.filename)};
    
    // Update project file count
    var project := state.projects[projectId];
    var updatedProject := Project(
      project.projectId,
      project.name,
      project.ownerId,
      project.fileCount - 1
    );
    var newProjects := state.projects[projectId := updatedProject];
    
    var newState := SystemState(newProjects, newFiles, newActiveFilenames);
    (newState, Success(true))
  }
  
  // Helper: Generate unique file ID
  function GenerateFileId(): string
}

// Result type for error handling
datatype Result<T> = Success(value: T) | Failure(message: string)
```

### Python Synthesis Target

The Python Synthesis Loop will generate:

```python
import icontract

@icontract.require(
    lambda state, project_id, filename, owner_id: 
        project_id in state.projects and
        state.projects[project_id].owner_id == owner_id and
        (project_id, filename) not in state.active_filenames
)
@icontract.ensure(
    lambda state, project_id, filename, owner_id, result, OLD: 
        result.success and
        result.value in OLD.state.files and
        OLD.state.files[result.value].project_id == project_id and
        (project_id, filename) in state.active_filenames
)
def save_file(state: SystemState, project_id: str, filename: str, 
              content: Content, file_type: FileType, owner_id: str) -> Result[str]:
    """Synthesized from Dafny SaveFile function."""
    # LLM-generated implementation matching Dafny spec
    ...
```

---

## Component 2: Project Management (Cascade Deletion)

### Optimized Specification

```dafny
module ProjectManagement {
  
  import FileOperations
  
  // Delete Project with Cascade: Batch operation
  function DeleteProjectCascade(
    state: SystemState,
    projectId: string,
    ownerId: string
  ): (newState: SystemState, result: Result<bool>)
    requires FileOperations.ValidState(state)
    requires FileOperations.OwnsProject(state, projectId, ownerId)
    ensures FileOperations.ValidState(newState)
    ensures result.Success? && result.value == true ==>
      projectId !in newState.projects
    ensures result.Success? && result.value == true ==>
      (forall fileId :: fileId in state.files && state.files[fileId].projectId == projectId ==>
        fileId !in newState.files)  // All files deleted
    ensures FileOperations.NoOrphanedFiles(newState)
  {
    // Collect all files to delete
    var filesToDelete := set fileId | fileId in state.files && state.files[fileId].projectId == projectId;
    
    // Batch delete: Remove all files at once
    var newFiles := state.files;
    var newActiveFilenames := state.activeFilenames;
    
    // Remove all project files from maps and ghost set
    for fileId in filesToDelete {
      var file := state.files[fileId];
      newFiles := newFiles[fileId := *];
      newActiveFilenames := newActiveFilenames - {(file.projectId, file.filename)};
    }
    
    // Remove project
    var newProjects := state.projects[projectId := *];
    
    var newState := SystemState(newProjects, newFiles, newActiveFilenames);
    (newState, Success(true))
  }
  
  // Loop invariant for batch deletion (if needed)
  predicate CascadeDeletionInvariant(
    state: SystemState,
    projectId: string,
    remainingFiles: set<string>,
    newFiles: map<string, File>,
    newActiveFilenames: set<(string, string)>
  )
  {
    // Files already deleted are not in newFiles
    (forall fileId :: fileId in remainingFiles ==>
      fileId !in newFiles) &&
    // Active filenames consistent with newFiles
    (forall fileId :: fileId in newFiles ==>
      (newFiles[fileId].projectId, newFiles[fileId].filename) in newActiveFilenames)
  }
}
```

---

## Component 3: Verification Pipeline → **MOVED TO SHELL**

**Architectural Decision:** Verification pipeline (Dafny subprocess execution, stdout parsing) belongs in the **Imperative Shell**, not the Functional Core.

**Reasoning:**
- Parsing stdout is I/O, not business logic
- Timeout handling is system-level, not verifiable in Dafny
- Error parsing correctness can be tested via Oracle Test Generation

**New Location:** Oracle Test Run (Red Loop in architecture diagram)

---

## Component 4: Traceability Links (Optimized)

### Pre-computed Line Index

```dafny
module TraceabilityLinks {
  
  // Pre-computed line index (avoid recursive string counting)
  datatype LineIndex = LineIndex(
    lineCount: nat,
    lineStarts: seq<nat>  // Character positions where lines start
  )
  
  function BuildLineIndex(content: Content): LineIndex
  {
    // Opaque: Built by Imperative Shell, passed to Core
    // Core only verifies consistency, doesn't build it
  }
  
  datatype SourceRange = SourceRange(
    startLine: nat,
    endLine: nat
  )
  
  predicate ValidSourceRange(range: SourceRange, index: LineIndex)
  {
    range.startLine > 0 &&
    range.endLine >= range.startLine &&
    range.endLine <= index.lineCount
  }
  
  datatype TraceabilityLink = TraceabilityLink(
    unitId: string,
    dafnyFileId: string,
    sourceFileId: string,
    sourceRange: SourceRange,
    verificationStatus: string
  )
  
  // Verify link consistency
  function ValidateTraceabilityLink(
    state: SystemState,
    link: TraceabilityLink,
    sourceIndex: LineIndex
  ): bool
    requires FileOperations.ValidState(state)
    requires link.sourceFileId in state.files
    requires link.dafnyFileId in state.files
    ensures result == true ==>
      ValidSourceRange(link.sourceRange, sourceIndex)
  {
    ValidSourceRange(link.sourceRange, sourceIndex) &&
    link.sourceFileId in state.files &&
    link.dafnyFileId in state.files
  }
}
```

---

## Component 5: Specification Generation

### Unit Identification Logic

```dafny
module SpecificationGeneration {
  
  // Unit candidate identification (pure logic)
  datatype UnitCandidate = UnitCandidate(
    title: string,
    description: string,
    lineRange: SourceRange,
    requirements: seq<string>
  )
  
  // Identify units from English spec (abstracted - actual logic in Shell)
  function IdentifyUnits(englishSpec: Content): seq<UnitCandidate>
  {
    // Opaque: Implemented by Gemini in Imperative Shell
    // Core only verifies consistency of identified units
  }
  
  // Verify unit creation consistency
  function ValidateUnitCreation(
    state: SystemState,
    candidates: seq<UnitCandidate>,
    sourceFileId: string,
    sourceIndex: LineIndex
  ): bool
    requires FileOperations.ValidState(state)
    requires sourceFileId in state.files
    ensures result == true ==>
      (forall candidate :: candidate in candidates ==>
        TraceabilityLinks.ValidSourceRange(candidate.lineRange, sourceIndex))
  {
    (forall candidate :: candidate in candidates ==>
      TraceabilityLinks.ValidSourceRange(candidate.lineRange, sourceIndex)) &&
    // No overlapping ranges
    (forall c1, c2 :: c1 in candidates && c2 in candidates && c1 != c2 ==>
      !RangesOverlap(c1.lineRange, c2.lineRange))
  }
  
  predicate RangesOverlap(r1: SourceRange, r2: SourceRange)
  {
    (r1.startLine <= r2.endLine && r1.endLine >= r2.startLine) ||
    (r2.startLine <= r1.endLine && r2.endLine >= r1.startLine)
  }
}
```

---

## Python Synthesis Loop Integration

### Synthesis Workflow

1. **Dafny Spec Verified** → Ground Truth established
2. **LLM Prompt Generation:**
   ```
   Given this verified Dafny function:
   
   function SaveFile(state: SystemState, ...): (newState: SystemState, result: Result<string>)
     requires ValidState(state)
     requires OwnsProject(state, projectId, ownerId)
     ...
   
   Generate Python function with icontract decorators that:
   - Matches the Dafny preconditions as @icontract.require
   - Matches the Dafny postconditions as @icontract.ensure
   - Implements the logic described in the Dafny function body
   ```

3. **Oracle Validation:**
   - Generate test vectors from Dafny spec (using `/mv` flag)
   - Run Python function with test vectors
   - Verify Python output matches Dafny output

4. **Runtime Enforcement:**
   - `icontract` decorators enforce pre/postconditions
   - Contract violations halt execution (no AI modification allowed)

### icontract Translation Rules

| Dafny | Python icontract |
|-------|------------------|
| `requires P` | `@icontract.require(lambda: P)` |
| `ensures Q` | `@icontract.ensure(lambda result, OLD: Q)` |
| `reads state` | Implicit in function parameters |
| `modifies state` | `OLD.state` vs `state` comparison |

---

## Oracle Test Generation

### Test Vector Generation from Dafny

```dafny
// Generate test cases
method GenerateTestVectors() returns (testCases: seq<TestCase>)
{
  // Valid case: Save file in owned project
  testCases := testCases + [TestCase(
    state := InitialState(),
    operation := SaveFileOp(projectId := "p1", filename := "test.md", ownerId := "u1"),
    expectedResult := Success("f1")
  )];
  
  // Invalid case: Unauthorized access
  testCases := testCases + [TestCase(
    state := InitialState(),
    operation := SaveFileOp(projectId := "p1", filename := "test.md", ownerId := "u2"),  // Wrong owner
    expectedResult := Failure("Unauthorized")
  )];
  
  // Invalid case: Duplicate filename
  testCases := testCases + [TestCase(
    state := StateWithFile("p1", "test.md"),
    operation := SaveFileOp(projectId := "p1", filename := "test.md", ownerId := "u1"),
    expectedResult := Failure("Duplicate")
  )];
}
```

### Python Test Execution

```python
import json
import pytest

@pytest.mark.parametrize("test_case", load_dafny_test_vectors("file_operations.json"))
def test_save_file_from_dafny(test_case):
    """Test generated from Dafny spec."""
    result = save_file(
        test_case["state"],
        test_case["operation"]["project_id"],
        test_case["operation"]["filename"],
        test_case["operation"]["content"],
        test_case["operation"]["file_type"],
        test_case["operation"]["owner_id"]
    )
    assert result == test_case["expected_result"]
```

---

## Implementation Roadmap

### Phase 1: Core Models & Infrastructure (Week 1-2)

1. **Create `api/verification/models.dfy`**
   - Define `SystemState`, `File`, `Project` with ghost sets
   - Define `ValidState` invariant
   - Define ownership predicates

2. **Set up Python Synthesis Pipeline**
   - LLM prompt templates
   - icontract integration
   - Test vector generation script

### Phase 2: File Operations (Week 3-4)

1. **Create `api/verification/file_operations.dfy`**
   - Implement stateless `SaveFile`, `UpdateFile`, `GetFile`, `DeleteFile`
   - Verify with Dafny compiler

2. **Synthesize Python Code**
   - Generate Python functions via LLM
   - Add icontract decorators
   - Generate test vectors

3. **Oracle Validation**
   - Run test vectors against Python
   - Verify contract compliance

### Phase 3: Project Management (Week 5-6)

1. **Create `api/verification/project_management.dfy`**
   - Implement cascade deletion
   - Verify loop invariants

2. **Synthesize & Validate**

### Phase 4: Traceability & Spec Generation (Week 7-8)

1. **Create traceability and spec generation specs**
   - Use pre-computed line indices
   - Verify unit consistency

---

## Required Sources for Expert Review

To complete the formal verification specifications, the experts need:

### 1. Database Models (`api/database.py`)
**Status:** ✅ Available  
**Purpose:** Map SQLAlchemy models to Dafny datatypes

### 2. UI API Mapping (`docs/UI_API_MAPPING.md`)
**Status:** ✅ Available  
**Purpose:** Identify Functional Core vs Imperative Shell boundaries

### 3. Sample English Specification
**Status:** ⚠️ **NEEDED**  
**Purpose:** Demonstrate Clover Loop refinement process

**Request:** Please provide:
- One raw English specification input (Gil's Input)
- Example of how it flows through Gemini refinement
- Example of final Dafny spec output

### 4. Unit Identification Logic (`api/deconstruct.py`)
**Status:** ✅ Available  
**Purpose:** Understand how units are identified to verify consistency

### 5. Current Python Implementation
**Status:** ✅ Available (`api/files.py`, `api/projects.py`)  
**Purpose:** Understand current logic for synthesis target

---

## Next Steps

1. **Provide Sample English Spec** → Experts will demonstrate Clover Loop
2. **Review Database Models** → Experts will create Dafny type mappings
3. **Create Initial `models.dfy`** → Experts will provide optimized version
4. **Set up Synthesis Pipeline** → Integrate LLM + Oracle workflow

---

## Success Criteria

### Phase 1 Complete:
- ✅ `models.dfy` verified with Dafny
- ✅ Python synthesis pipeline operational
- ✅ Test vector generation working

### Phase 2 Complete:
- ✅ All Functional Core components verified
- ✅ Python code synthesized from specs
- ✅ Oracle tests passing
- ✅ Runtime contracts enforced

### Long-term Goal:
- ✅ Zero manual Python-Dafny alignment
- ✅ All critical logic verified
- ✅ Automated synthesis loop operational
- ✅ Guaranteed correctness via contracts

---

## References

- InspecThor Architecture Diagram (Spec-First Synthesis Loop)
- Dafny Documentation: https://dafny.org/dafny/DafnyRef/DafnyRef
- icontracts: https://github.com/Parquery/icontract
- Guardian Gateway: `docs/UI_API_MAPPING.md`

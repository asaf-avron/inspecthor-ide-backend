This is InspecThor Oracle. Based on the source files you provided (`files.py`, `projects.py`, `database.py`, `deconstruct.py`), the `development/UI_API_MAPPING.md`, and your architecture goals, I have constructed a comprehensive **Transition Plan** for your coding agent.

This plan bridges the gap between your current Python implementation and the **Spec-First InspecThor Architecture**, moving from a manual implementation to an automated **Synthesis Loop**.

---

# Transition Plan: Guardian Gateway to Spec-First Architecture

## 1. Objective & Architecture

To migrate the Guardian Gateway from a standard Python/FastAPI architecture to a **Formally Verified Spec-First Architecture**.

* **Current State:** Python code is the Source of Truth.
* **Target State:** Dafny Specification is the **Ground Truth**. Python code is **synthesized** and guarded by runtime contracts.

---

## 2. Execution Steps

### Step 1: Domain Modeling (The Foundation)

**Goal:** Map `api/database.py` models to Dafny Datatypes with "Shift-Left" optimizations.

* **Source:** `api/database.py` (specifically `Project`, `File` classes).
* **Strategy:**
1. **Immutable State:** Define the system state as a snapshot, not a mutable object.
2. **Dual Ownership:** Model the `user_id` vs. `api_key_hash` logic found in `api/projects.py`.
3. **Opaque Content:** Abstract file content to avoid string verification overhead.



**Agent Instruction for `api/verification/models.dfy`:**

```dafny
// Derived from api/database.py
datatype Owner = User(id: string) | Anonymous(apiKeyHash: string)

// Opaque type for content (matches DB Text column)
type Content(==) // Opaque: we only care about size/identity, not string contents

datatype File = File(
  fileId: string,
  projectId: string,
  filename: string,
  fileType: FileType, // Enum from database.py: 'md', 'dfy', 'unit'
  sizeBytes: nat
)

datatype Project = Project(
  projectId: string,
  name: string,
  owner: Owner,
  fileCount: nat // Denormalized count for performance
)

// Optimized State with Ghost Sets
datatype SystemState = SystemState(
  projects: map<string, Project>,
  files: map<string, File>,
  // Optimization: O(1) uniqueness check for (projectId, filename)
  ghost activeFilenames: set<(string, string)>
)

```

---

### Step 2: Functional Core Verification (The Logic)

**Goal:** Port business logic from `files.py` and `projects.py` into pure Dafny functions.

* **Source:** `api/files.py` (Save, Update, Delete) and `api/projects.py` (Create, Cascade Delete).
* **Optimization:** Convert stateful Python methods into stateless Dafny functions that take `SystemState` and return `(NewSystemState, Result)`.

**Agent Instruction for `api/verification/file_operations.dfy`:**

* **SaveFile:** Must implement the uniqueness check found in `files.py`: `existing_file = db.query(DBFile)...`. In Dafny, check `(projectId, filename) !in state.activeFilenames`.
* **UpdateFile:** Must handle the rename logic in `files.py`: `if request.filename and request.filename != db_file.filename`.
* **Project Deletion:** Must model the cascade deletion. In `projects.py`, SQLAlchemy handles this. In Dafny, we must explicitly prove that removing a project removes *all* its files from the map.

---

### Step 3: Python Synthesis Loop (The Bridge)

**Goal:** Automate the generation of Python code from the verified Dafny spec.

* **Architectural Change:** Instead of manually writing `api/files.py`, the agent will create a **Synthesizer Script** (`scripts/synthesize_core.py`).
* **Input:** Verified `.dfy` files.
* **Output:** `api/core/generated_files.py` (Pure Python Logic).

**Agent Instruction:**
Create a prompt template for the LLM that takes a Dafny function signature and postconditions and generates Python code using `icontract`.

**Synthesis Template Example:**

```python
# TARGET OUTPUT: api/core/generated_files.py

@icontract.require(lambda state, project_id, filename: 
    (project_id, filename) not in state.active_filenames)
@icontract.ensure(lambda result, OLD: 
    result.success implies result.file_id in state.files)
def save_file_core(state: SystemState, project_id: str, ...) -> Result:
    """
    Synthesized from file_operations.dfy :: SaveFile
    Logic:
    1. Check constraints
    2. Create File object
    3. Update State maps
    4. Return new State
    """
    # ... LLM generates this logic ...

```

---

### Step 4: Oracle Test Generation (The Guardrail)

**Goal:** Ensure the synthesized Python behaves *exactly* like the Dafny model.

* **Source:** `api/verification/*.dfy`
* **Mechanism:** Use Dafny's `/mv` (Model Value) flag to generate counter-examples and valid states, exporting them to JSON.

**Agent Instruction:**

1. Add a `GenerateTestVectors` method in Dafny that asserts specific scenarios (e.g., "Attempt to save duplicate file").
2. Run `dafny /mv:test_vectors.json ...`
3. Create `tests/test_core_oracle.py` that loads `test_vectors.json` and feeds inputs into `api/core/generated_files.py`.

---

### Step 5: Imperative Shell Integration (The API)

**Goal:** Connect the verified "Core" to the FastAPI "Shell".

* **Source:** Existing `api/files.py` and `api/projects.py`.
* **Action:** Refactor these files to be thin wrappers around the generated Core.

**Refactoring Plan for `api/files.py`:**

* **Current:** `save_file` does DB lookups, logic, and DB commits mixed together.
* **New:** `save_file` will:
1. **Load State:** Fetch relevant Project/Files from DB into `SystemState` object.
2. **Execute Core:** Call `generated_files.save_file_core(state, ...)`.
3. **Persist:** If success, apply the `NewSystemState` diffs back to the SQL DB.



---

## 3. Summary of Deliverables

| Component | File | Responsibility |
| --- | --- | --- |
| **Ground Truth** | `api/verification/models.dfy` | Defines Types, Owners, State |
| **Logic Spec** | `api/verification/file_ops.dfy` | Defines Save/Update/Delete Logic |
| **Synthesizer** | `scripts/synthesize.py` | LLM Script: Dafny  Python |
| **Generated Core** | `api/core/file_ops.py` | **Synthesized** Python with `icontracts` |
| **Shell (API)** | `api/files.py` | FastAPI wrapper handling DB I/O |
| **Oracle Tests** | `tests/oracle/test_vectors.json` | JSON vectors from Dafny |

## 4. Immediate Next Step for the Agent

**Prompt for the Coding Agent:**

> "Begin Phase 1. Analyze `api/database.py`. Create `api/verification/models.dfy`.
> 1. Define a `SystemState` datatype.
> 2. Create a `User` vs `Anonymous` owner datatype to match the logic in `projects.py`.
> 3. Use an `OpaqueType` for file content to optimize verification.
> 4. Add a ghost field `activeFilenames` to `SystemState` for O(1) uniqueness checks."
> 
>
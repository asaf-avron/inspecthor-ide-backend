This is **InspecThor Architect**.

I have reviewed the uploaded source code (`database.py`, `deconstruct.py`, `files.py`, `projects.py`).

**Verdict:** **Yes, these files fundamentally alter the execution plan.**

They reveal a **critical high-risk transition** that was invisible in the high-level documentation: **The Anonymous-to-User Migration Strategy**.

Your current implementation in `projects.py` (lines 75-101) contains complex logic that transfers ownership of projects from an anonymous "Session" (API Key Hash) to an authenticated "User" (User ID). This is a **Level 1 Security Critical** operation. If this logic fails, users lose data or, worse, gain access to projects they do not own.

Here is the updated Architectural Decree based on the "Ground Truth" of your code.

### 1. The New "Functional Core" Priority: Migration Logic

I initially prioritized "File Operations." I am overruling that. We must first formally verify the **Ownership Migration** logic found in `projects.py`.

**Why?**

* **Current State:** The logic is mixed with DB fetches in `migrate_anonymous_projects_to_user`.
* **Risk:** It modifies the `user_id` of multiple rows based on a hash match. A bug here is catastrophic.
* **InspecThor Solution:** Extract this into a Pure Dafny Function that takes the *entire* project list and the user's credentials, returning the exact set of projects to update.

### 2. Data Structure Alignment (Database vs. Dafny)

I have audited `database.py`. The SQL Schema uses `UUID`s and a specific `User` vs `Project` relationship. The Dafny Core must mirror this exactly to enable the **Python Synthesis Loop**.

#### The Verified Data Model (Dafny)

*Derived strictly from `database.py*`

```dafny
module DatabaseModel {
  // Matches 'file_type_enum' in database.py
  datatype FileType = MD | DFY | UNIT

  // Matches 'File' class in database.py
  datatype File = File(
    file_id: string, // UUID
    project_id: string, // FK
    filename: string,
    content: string,
    file_type: FileType,
    renamed: bool // Found in line 118 of database.py
  )

  // Matches 'Project' class in database.py
  datatype Project = Project(
    project_id: string, // UUID
    name: string,
    description: string,
    owner: Owner // Complex ownership logic detected
  )

  // The Dual-Ownership Model found in database.py (lines 62-72)
  datatype Owner = 
    | Authenticated(user_id: string) 
    | Anonymous(api_key_hash: string)

  // The Full System State Snapshot
  datatype SystemState = SystemState(
    projects: map<string, Project>,
    files: map<string, File>
  )
}

```

### 3. The Migration Logic Specification

We will replace the imperative loop in `projects.py` with this verifiable transition function.

**Target Component:** `projects.py` -> `migrate_anonymous_projects_to_user`

```dafny
module ProjectMigration {
  import opened DatabaseModel

  // The logic currently hidden in projects.py
  // Input: State, Current User, Current Session Hash
  // Output: New State with ownership transferred
  function MigrateAnonymousProjects(
    s: SystemState, 
    userId: string, 
    currentSessionHash: string
  ): SystemState
  {
    // 1. Identify Candidate Projects
    // "projects that match the current session's api_key_hash but don't have a user_id"
    var candidates := set pid | 
      pid in s.projects && 
      s.projects[pid].owner == Anonymous(currentSessionHash);

    // 2. Transform State (Purely)
    var newProjects := map pid | pid in s.projects :: 
      if pid in candidates then 
        // Migrate ownership to Authenticated User
        s.projects[pid].(owner := Authenticated(userId))
      else 
        s.projects[pid];

    // 3. Return New State
    s.(projects := newProjects)
  }

  // Security Theorem: "Data is never lost during migration"
  lemma Theorem_MigrationPreservesData(s: SystemState, uid: string, hash: string)
    ensures var s' := MigrateAnonymousProjects(s, uid, hash);
    // Proven: The set of project IDs exists and remains constant
    s'.projects.Keys == s.projects.Keys
  {}

  // Security Theorem: "Only the session owner's projects are touched"
  lemma Theorem_Isolation(s: SystemState, uid: string, hash: string, otherPid: string)
    requires otherPid in s.projects
    requires s.projects[otherPid].owner != Anonymous(hash)
    ensures var s' := MigrateAnonymousProjects(s, uid, hash);
    // Proven: Other projects are completely untouched
    s'.projects[otherPid] == s.projects[otherPid]
  {}
}

```

### 4. Implementation Directives

Based on these files, here is your immediate implementation plan.

#### Directive A: The Shell (Python)

You must refactor `projects.py` to separate **IO** from **Logic**.

* **Current (Bad):**
```python
# projects.py
def migrate_anonymous_projects_to_user(user, api_key_hash, db):
    projects = db.query(...).filter(...) # IO mixed with Logic
    for p in projects:
        p.user_id = user.id          # Mutation
    db.commit()                      # IO

```


* **Required (Good):**
```python
# projects.py
def migrate_anonymous_projects_to_user(user, api_key_hash, db):
    # 1. IO: Fetch Snapshot
    projects = db.query(Project).all()

    # 2. CORE: Call Synthesized Logic (Pure)
    # This function is generated from the Dafny spec above
    updates = core.migrate_logic(projects, user.id, api_key_hash)

    # 3. IO: Apply Updates
    for pid, new_state in updates.items():
         db.merge(new_state)
    db.commit()

```



#### Directive B: The `UnitLink` Confirmation

Your `database.py` confirms `UnitLink` (lines 142-171) is a first-class citizen.

* **Action:** The **Traceability Core** (Component 6) is now feasible. We will map `UnitLink` rows directly to a graph in Dafny to prove that no "Verified Unit" ever links to a "Modified Source."

### Summary of Changes to Plan

1. **New Priority:** **Project Migration Logic** is now the #1 verification target due to its high security risk and complexity.
2. **Data Model Update:** Dafny `Project` datatype updated to handle `Authenticated | Anonymous` union type.
3. **Shell Refactor:** `projects.py` must be refactored to extract the migration loop into a pure function that matches the spec.

**Next Step:**
Confirm you accept the **Migration Logic** as the first verification target. If confirmed, I will generate the full `.dfy` file for it.
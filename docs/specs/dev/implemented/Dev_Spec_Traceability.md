# Feature Spec: Traceability Matrix (The Audit Trail)

## 1. The Logic Model

We map English Requirements to Dafny Code Lines using strict ID tags to ensure compliance. This creates a bi-directional link between "Intent" and "Implementation."

### Entities

* **RequirementID:** String formatted as `[REF-XX]` (Sequential integer).
* **CodeLocation:** Record `{ file_path: String, line_number: Int }`.
* **TraceabilityEntry:**
* `id`: RequirementID
* `source_text`: String (The extracted English sentence)
* `code_context`: `List[CodeLocation]` (Deterministic mapping to source lines)
* `status`: TraceabilityStatus
* `timestamp`: Int (Unix epoch of last update)


* **TraceabilityMap:** `Map<RequirementID, TraceabilityEntry>`
* **TraceabilityStatus:** Enum(`Pending`, `Implemented`, `Verified`, `Missing`, `Obsolete`)

### Concurrency Model

* **Atomic Updates:** The map is read-only during the Audit phase. Updates are applied in a single atomic transaction at the end of the `AuditWithTraceability` function.

---

## 2. Capabilities (The Auditor Upgrade)

### Function: `AuditWithTraceability`

**Description:** The Auditor parses the input text and syncs it with the Traceability Map.

**Definition of "Atomic Requirement":**
Any sentence or independent clause containing a Normative Keyword:

> "MUST", "SHALL", "SHOULD", "WILL", "REQUIRES", "ENSURES".

**ID Management Logic (Sync):**

1. **Snapshot:** Clone current `TraceabilityMap` to `local_map`.
2. **Parse:** Extract existing tags.
3. **Identify New:** Assign `[REF-Max+1]` to untagged normative sentences.
4. **Mark Obsolete:** If ID in `local_map` but not in text, set `status = Obsolete`.
5. **Commit:** Atomically replace global map with `local_map`.

### Function: `UpdateStatus`

**Description:** Updates the status based on the Build Lab (Gateway) results.

**Logic:**

* **Implemented:** If `dafny_code` contains `// [REF-XX]`.
* **Verified:** If `Gateway.verify()` returns `Success` AND the Dafny Verifier confirms the assertion on the line defined in `CodeContext`.
* **Missing:** If `[REF-XX]` is `Pending` and no matching comment exists.

### Function: `PruneObsolete`

**Description:** Prevents map bloat.

**Logic:**
Remove any entry where:


---

## 3. The Imperative Shell (UI)

### Design Studio Tab

* **Top:** Display the **"Tagged Spec"** (Read-only view of English with tags).
* **Bottom:** The **Traceability Matrix** (Interactive Dataframe).

**Dataframe Columns:**

| Col | Field | Display / Format |
| --- | --- | --- |
| **1** | **ID** | `REF-01` |
| **2** | **Requirement** | "Sender must exist" |
| **3** | **Status** | **Badge:** 🟢 Verified, 🟡 Implemented, 🔴 Missing, ⚫ Obsolete |
| **4** | **Logic Link** | `File:Line` (Clickable link) |

---
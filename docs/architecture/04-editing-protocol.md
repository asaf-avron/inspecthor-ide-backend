# Editing Protocol: "AI-Gapped Development"

The strongest requirement of InspecThor is that **code in the IDE should not be edited directly by the user.**

## The Protocol

### 0. Identity & Drift
InspecThor tracks components by **UUID**, not path.
- If you move a component folder, InspecThor will find it and update its registry.
- **Constraint**: Do not delete the `.inspecthor_meta` file.

### 1. Trigger
The user modifies a specification file, e.g., `src/features/voting/spec.md`.
- *Example*: changing "One vote per user" to "Weighted voting allowed".

### 2. IDE State
The IDE detects the change and flags the component as **"Desynchronized"** (Red Status).
- Visual indicator: "Spec changed. Re-examination required."

### 3. Re-examination (The "Thinking" Phase)
The user clicks **"Harmonize"** (or "Run Re-examination").
- **Agent Action**:
    1.  **Analyze Diff**: Identifies that `spec.md` has changed.
    2.  **Scope**: Determines only `voting_logic` is affected (Incremental focus).
    3.  **Update Logic**: Updates `core.dfy` to support weighted sums.
    4.  **Verify**: Runs Dafny verification.
    5.  **Update Shell**: Updates `src/shell` to handle new inputs.

### 4. Merge
Once verified (Green Status), the IDE enables the **"Merge Branch"** button. The user can then merge the InspecThor-created PR.

## Component Refinement Goal

To ensure verifiability, we must avoid "monolithic" specs.
- **Metric**: "For an initial feature scope MD, we need at least 4 verifiable core components."
- **Decomposition Engine**: When the AI reads a vague MD, it must shatter the requirement into atomic, verifiable units (e.g., `StateContainer`, `TransitionLogic`, `AccessControl`, `DataValidator`).
- **Strategic Value**: Small components are easier to verify (Dafny is faster) and easier to visualize (Mermaid is cleaner).

## Post-Verification
- **Visualization**: A post-verification Mermaid diagram shows the actual implementation interactions.
- **Fix Suggestions**: Gemini suggests fixes in GitHub. If a fix applies to contracts, it is suggested in the IDE.
- **Refinement**: MD files should be refined by AI to maintain the 4-component metric.

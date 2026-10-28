# Verification Pipeline: "The Triad"

Our verification strategy relies on **The Three Horizons of Truth**, refining the manual/semi-auto/auto classification into a rigorous pipeline.

## Horizon A: Intent Verification (Manual / Vision)

**Context**: "Did I ask for the right thing?"

- **Mechanism**:
    1.  **Spec**: User reads `spec.md`.
    2.  **Visualization**: IDE renders the Mermaid Diagram (Expected) derived from the MD.
- **Check**: User confirms, "Yes, this logic flow represents my requirements."
- **Artifacts**: `spec.md`, `interactions.mermaid`.

## Horizon B: Logic Verification (Semi-Auto / Dafny)

**Context**: "Is the math correct?"

- **Mechanism**:
    1.  **Generation**: AI translates `spec.md` $\rightarrow$ `core.dfy`.
    2.  **Proof**: Dafny verifier runs. It checks for invariants (safety, liveness).
- **Constraint**: If Dafny fails, the code is **never generated**.
- **Feedback Loop**: The error is fed back to the AI to "Refine Spec" or "Fix Implementation."
- **Artifacts**: `core.dfy`, Verification Report.

## Horizon C: Runtime Verification (Auto / CI)

**Context**: "Does the shell obey the kernel?"

- **Mechanism**:
    1.  **Compilation**: `core.dfy` $\rightarrow$ `src/generated/kernel.py`.
    2.  **Integration Test**: The AI generates a Python test suite that fuzzes the Shell to ensure it handles the Kernel's exceptions correctly.
    3.  **Visual Diff**: Post-verification Mermaid of actual Python call graphs vs. expected logic.
- **Artifacts**: `src/generated/kernel.py`, `tests/`, Execution Logs.

## Automated Checks (CI)
GitHub Actions will run:
1.  **Dafny Verification**: Verify `.dfy` files.
2.  **Python Tests**: Run the generated test suite.
3.  **Desync Check**: Ensure that `spec.md`, `core.dfy`, and `src/` are synchronized.

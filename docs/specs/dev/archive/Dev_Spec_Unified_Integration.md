# Feature Spec: Workflow Integration (Lens & Gateway)

## 1. The Logic Model

Connect the standalone "Spec Lens" and "Gateway" tools into the post-audit workflow with strict matching rules.

---

## 2. Capability: "Lens" Integration (The Explainer)

* **Trigger:** State becomes `Finalized`.
* **Action:**
* Pass `session_state.contract_code` to `render_lens_tab`.


* **Validation:**
* Verify `contract_code` is valid Dafny before rendering.
* If invalid, show "Contract Error".



---

## 3. Capability: "Gateway" Integration (The Project Verifier)

* **Trigger:** Implementation phase.
* **New Feature:** Multi-File Verification

### Input

* File Uploader (`.py`, `.zip`).

### Pre-Check

* **If ZIP:** Validate integrity, unzip to temp dir.
* **If non-code file found:** Skip and warn.

### Matching Logic (The Link)

* **Target:** Look for Python class `X` where contract defines trait `X_Interface`.
* **Heuristic:** Class must explicitly inherit or implement the Interface (e.g., `class RewardsImpl(RewardsInterface):`).
* **If no match found:** Fail verification with "No implementation class found for contract."

### Verification Loop

1. **For each matched file:** Run `Gateway.verify(contract, implementation)`.

### Display

* **Summary:** Table `[File | Class | Status | Risk]`.
* **Detail:** Expandable logs for compiler errors.
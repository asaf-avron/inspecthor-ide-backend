# Feature Spec: Interactive Spec Review & Resolution

## 1. The Logic Model

TRANSFORM the "Audit Report" from a static list into an interactive "ToDo List" for the user.

### Entities

* **ResolutionAction:** Enum(`Apply`, `Edit`, `Dismiss`)
* **Suggestion:**
* `gap_id`: String (from Audit)
* `original_text`: String (Snippet causing the issue)
* `proposed_text`: String (AI's fix)
* `rationale`: String ("Fixes negative amount bug")


* **EditState:** Enum(`Viewing`, `Editing`, `Applied`, `Invalidated`)

### Invariants

* **Atomic Application:** A suggestion can only be applied if `original_text` matches the current document state exactly.
* **Risk Monotonicity:** Resolving a gap must reduce the displayed Risk Score.

---

## 2. Capabilities (The "Fixer" Assistant)

### Function: `GenerateSuggestion`

* **Trigger:** User clicks "Fix" on a Gap Card.
* **Input:** The Gap description + Current Spec.
* **Output:** A `Suggestion` object.
* **AI Prompt:**
> "You are a Tech Lead.
> GAP: {gap_description}
> CONTEXT: {spec_snippet}
> TASK: Rewrite the snippet to fix the gap. Keep it minimal."



### Function: `ApplyCorrection`

* **Trigger:** User clicks "Apply" (on AI suggestion) or "Confirm" (on manual edit).
* **Pre-Check:** Search for `original_text` in `current_spec`.
* **If Not Found:** Mark Suggestion as `Invalidated` (Conflict Detected). Alert User.
* **If Found:** Replace `original_text` with `proposed_text`.


* **State Update:**
1. Mark Gap ID as **Resolved**.
2. Update `current_risk = current_risk - Gap.weight`.
3. Move Card to "Resolved" tab.



---

## 3. The Imperative Shell (UI - "Review Mode")

### Interaction Design

* **Split View:**
* **Left:** The English Spec (Editable).
* **Right:** The "Gap List" (Cards).


* **Gap Card Interaction:**
* Clicking a card scrolls the **Left Editor** to the relevant section.
* **Card expands to show:**
* **The Issue:** "Missing negative check."
* **The Fix:** Diff view.
* **Buttons:** ✅ Apply, ✏️ Edit Fix, 🗑️ Dismiss.


* **Edit Flow:**
1. Click ✏️ **Edit Fix**  Text Area becomes editable.
2. User modifies text  Click **Save & Apply**.
3. System runs `ApplyCorrection`.
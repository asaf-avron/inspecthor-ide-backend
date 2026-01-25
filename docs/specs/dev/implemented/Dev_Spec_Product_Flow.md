# **Feature Spec: Guardian Product Workflow (The Triage & Rigor System)**

## **1\. The Logic Model**

A multi-stage pipeline that filters, standardizes, and verifies user input based on a user-selected rigor level.

* **Dependencies:**  
  * SpecRefiner: The autonomous agent defined in Dev\_Spec\_Auto\_Refinement.md (Self-Healing Loop).  
  * SpecAuditor: The logic analyzer defined in Dev\_Spec\_Auditor\_Enhanced.md.  
  * Traceability: The compliance mapping defined in Dev\_Spec\_Traceability.md.  
* **Definitions:**  
  * **Saturated Risk (![][image1]):** ![][image2].  
  * **Standard Template:** The markdown structure requiring: \* \*\*Entities:\*\*, \* \*\*Invariants:\*\*, and \#\#\# Function:.  
  * **APIError:** Any exception of type TimeoutError, ConnectionError, or HTTP 5xx.  
* **State Space:**  
  * raw\_input: String (User paste)  
  * doc\_type: Enum(Spec, Code, Junk)  
  * rigor\_level: Enum(Sanity, Standard, Paranoid)  
  * structured\_spec: String  
  * traceability\_data: List\[Dict\] (The Matrix rows)  
  * current\_risk: SafeInt (0..100,000)  
  * workflow\_status: Enum(Draft, Analyzing, Ready, Finalized)

## **2\. Capabilities**

### **Stage 1: The Triage Gateway (Invisible Guard)**

* **Goal:** Reject junk immediately.  
* **Input:** Raw text.  
* **Logic:** Call Gemini Flash (Timeout: 5s)."Classify this text: 'Functional Spec', 'Source Code', or 'Other/Junk'. Return JSON."  
* **Validation:** Parse JSON. If doc\_type is undefined, default to 'Junk'.  
* **Decision:**  
  * If Code: Redirect to Gateway Tab.  
  * If Junk: Show Error "Please provide a functional requirement."  
  * If Spec: Proceed to Stage 2\.

### **Stage 2: The Structure Gateway (Normalization)**

* **Goal:** Enforce the unified baseline.  
* **Input:** Raw Spec.  
* **Logic:** Call Gemini Pro (Timeout: 15s)."Rewrite this into the Guardian Standard Template. Output Markdown."  
* **Validation:**  
  * **Header Check:** Verify presence of \* \*\*Entities:\*\* and \#\#\# Function:.  
  * If validation fails: Flag as "Normalization Failed" \-\> Manual Override.  
* **Result:** structured\_spec is displayed.

### **Stage 3: The Audit & Compliance Loop**

* **UI Controls:**  
  * **Rigor Level:** Dropdown (Sanity, Standard, Paranoid).  
  * **Action:** Button ✨ Auto-Refine Spec.  
* **Refinement Logic (Connected to SpecRefiner):**  
  1. **Initial Audit:** report \= SpecAuditor.audit\_spec(structured\_spec) (Includes Traceability extraction).  
  2. **Auto-Fix Loop:** If user clicks Auto-Refine:  
     * Call SpecRefiner.optimize\_spec(structured\_spec) (The robust v41 loop).  
     * **Visual Feedback:** Use st.status to show loop progress ("Iteration 1: Fixing gaps...", "Iteration 2: Converged").  
     * Update structured\_spec with the result.  
  3. **Visualization:**  
     * Display structured\_spec (Editable).  
     * Display **Traceability Matrix** (from Dev\_Spec\_Traceability.md) showing coverage of English reqs vs Dafny code.  
     * Display **Risk Score (![][image1])**.

### **Stage 4: The Convergence Signal & Approval**

* **UI Feedback:**  
  * If ![][image3]: Show "Green Check" (Ready).  
  * If ![][image4]: Show "Orange Warning" (Needs Review).  
* **Approval Action:**  
  * User clicks "Finalize Spec".  
  * **Precondition:** System must be in "Ready" or "Warning" state.  
  * **Effect:** Set workflow\_status \= Finalized. Lock structured\_spec (Read-Only). Enable "Generate Dafny" button.

## **3\. Postconditions**

1. **Compliance:** Every finalized spec includes a Traceability Matrix linking requirements to code.  
2. **Bounded Effort:** The loop terminates after max 3 refinement attempts OR if refinement fails to improve risk.  
3. **Monotonicity:** The workflow never auto-updates the spec to a version with a higher Risk Score.  
4. **Immutable Finality:** Once Finalized, the spec cannot be modified without restarting the workflow.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAABQklEQVR4XmNgGOFAXl7eEYifA/F/JPwKiH8B8V85ObmTQDoYqJQZXS8cABXMAeLfQMU2SMLMQH4a1JAyIJ8RSQ4C1NXVeYEKDgPxXUVFRXFkOaCYJBA/xCYHU6AJxG+BeA2Qy4IsJysrawoU/wbEV6WkpESQ5WAK/ICS/xUUFNLR5YBiDSA5IC5GlwMDoMQkeTT/GhsbswLFkqEuKgXxkfWAgaioKA9Q8oA8JHSPQdnXQbYBDZsuLS0tjK4HDuSx+5cR6NxKeUgouyIpRwUw/wJxEbI4UJMxUOwrEM9BFkcB8lj8CxWPhhraiiwOBwTiF2QoyN/lyOJwAHSyDlDBe3nM+GUBiq1C1gxkVwPZLiBNtvKQVANyFgy/AvkfphvIDwbivyBDgJpigfRsGRkZToT5BADIK0CNvqAQJ0njKKASAABwRWKIIbwzAgAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,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>
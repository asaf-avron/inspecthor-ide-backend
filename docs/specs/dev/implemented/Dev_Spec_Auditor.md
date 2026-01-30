# **Feature Spec: Guardian "Spec Auditor"**

## **1\. The Logic Model**

The Spec Auditor is a "Semantic Analysis Engine." It takes unstructured English requirements and converts them into structured Verification Gaps.

* **Entities:** GapReport  
* **Key State Variables:**  
  * GapReport.CriticalGaps: List of Strings (Logic holes that allow exploits).  
  * GapReport.Ambiguities: List of Strings (Vague definitions).  
  * GapReport.DafnySkeleton: String (The generated trait code).

## **2\. Capabilities (The Functional Core)**

### **Function: AuditSpec**

**Description:** Asynchronous function that calls the LLM.

* **Inputs:** spec\_text: String (The English requirement).  
* **Outputs:** GapReport Object.  
* **Logic (The Gemini Pipeline):**  
  1. **System Prompt:** "You are a Formal Verification Expert. Analyze this text for missing preconditions (e.g., negative amounts, missing IDs)."  
  2. **Constraint:** Return JSON only.  
  3. **Validation:** Ensure the generated Dafny Skeleton is syntactically valid.

## **3\. The Imperative Shell (Streamlit Update)**

* **New Tab:** Add a "Spec Auditor" tab to the existing app.py. *(The referenced app was the legacy Streamlit UI; the current UI is Next.js.)*  
* **Input:** Text Area (for pasting the spec) or "Load Template" button.  
* **Output:**  
  * **Gap Cards:** Red cards for Critical Gaps.  
  * **Skeleton Code:** A copy-pasteable Dafny block.

## **4\. Environment Variables**

* GEMINI\_API\_KEY: Required for the LLM.
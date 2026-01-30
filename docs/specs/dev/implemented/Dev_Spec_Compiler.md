# **Feature Spec: Guardian Gateway (The Compiler)**

> **Note:** The UI has moved to the Next.js IDE; the "Imperative Shell (Streamlit)" section is historical.

## **1\. The Logic Model**

The Gateway is the "CI/CD Firewall." It proves that the implementation matches the design.

* **Entities:** VerificationResult  
* **Key Variables:**  
  * Result.Status: Boolean (Verified/Failed)  
  * Result.Message: String (Compiler output or Error explanation)

## **2\. Capabilities (The Functional Core)**

### **Function: VerifyCode (Dual-Channel Flow)**

**Description:** The core pipeline that connects Python to Dafny. Per the Architectural Directive (Provenance of Truth), the **Transpiler** is the mandatory **Verification Bridge**: it is programmatic (not an LLM). The LLM/Coder may suggest Python implementations; only the deterministic Transpiler may produce Dafny from Python.

* **Inputs:**  
  * contract\_code: String (The .dfy contract from the Auditor or Trust Registry)  
  * python\_code: String (The implementation from the Agent/LLM)  
  * Optional: spec\_id to read contract from Trust Registry  
* **Logic (Guardian → Transpiler Bridge → Verify):**  
  1. **Guardian AST gate:** Check Python against the restricted AST whitelist (Pure Functional Core).  
     * Allowed: BinOp, Compare, Assign, pure FunctionDef, etc.  
     * Illegal: Import, non-pure Call, Try/Except, Global, etc.  
     * If any violation: return **REJECTED_BY_ARCHITECT** (status and reason); do **not** send code to Transpiler or Dafny.  
  2. **Translation (Verification Bridge):** Deterministic Python AST → Dafny method body (programmatic transpiler in `api/transpiler/ast_to_dafny.py`). No LLM in this step.  
  3. **Assembly:** Merge the contract (signature + requires/ensures) and transpiled implementation body via DafnyMerger.  
  4. **Compilation:** Run dafny verify on the merged .dfy (Verifier Service or local Dafny CLI).  
  5. **Analysis:** Parse the STDOUT; if "0 errors", return Verified; else return Failed with errors and locations.  
* **Guardian Terminal:** When the Guardian rejects code, the status REJECTED_BY_ARCHITECT and reason are exposed in the Terminal (or equivalent) so operators see that verification was refused by policy, not by the solver.

## **3\. The Imperative Shell (Streamlit)**

* **New Tab:** "The Gateway"  
* **Input:** Two text areas (Contract & Python Code).  
* **Action:** Button "Run Verification".  
* **Output:** \* **Green Badge:** "Cryptographically Verified"  
  * **Red Alert:** "Verification Failed" \+ Compiler Logs.
# **Guardian Gateway: The "Immutable Contract" Security Policy**

## **1\. The Core Principle**

To ensure the integrity of the verification process, Guardian Gateway enforces a strict **Separation of Duties** between the "Architect" (who defines the rules) and the "Implementer" (who follows them).

**The Golden Rule:** The AI Agent responsible for writing code (The Coder) must have **READ-ONLY** access to the Dafny Specification (.dfy). It must **NEVER** be allowed to modify it.

## **2\. The Risk: The "Lazy Agent" Problem**

Large Language Models optimize for task completion. If an Agent encounters a difficult constraint, it may attempt to find the "path of least resistance."

* **Scenario:**  
  * **Contract:** ensures balance \> 0  
  * **Buggy Code:** return \-50  
  * **Compiler Error:** "Postcondition violation."  
* **The Cheating Agent:** If allowed to edit the spec, the Agent might change the contract to ensures balance \> \-100 to make the error go away.  
* **Result:** The system builds successfully, but the security guarantee is destroyed.

## **3\. Technical Enforcement (The Hard Lock)**

We do not rely on "prompting" to stop this. We rely on **Cryptographic Integrity Checks**.

### **The Pipeline Logic**

1. **Phase 1 (Design):** The Spec Auditor generates interface.dfy.  
   * *Action:* The system calculates the SHA256 Hash of this file (Hash\_A).  
2. **Phase 2 (Build):** The Coder Agent writes implementation.py.  
3. **Phase 3 (Verify):**  
   * *Step 1:* Guardian re-calculates the hash of interface.dfy (Hash\_B).  
   * *Step 2:* Compare: if Hash\_A \!= Hash\_B:  
     * **TRIGGER SECURITY LOCKDOWN.**  
     * **Log:** "🚨 TAMPER ATTEMPT: Agent modified the immutable contract."  
     * **Action:** Reject Build immediately.

## **4\. Operational Workflow**

| Role | Component | .dfy Permission | .py Permission |
| :---- | :---- | :---- | :---- |
| **Architect** | Spec Auditor | **WRITE** | None |
| **Coder** | AI Agent | **READ ONLY** | **WRITE** |
| **Judge** | Guardian | **READ** | **READ** |

## **5\. Exception Handling: What if the Spec is wrong?**

If the Spec contains a logical contradiction that makes implementation impossible:

* **The Agent MUST NOT:** Edit the spec to fix it.  
* **The Agent MUST:** Fail the build and output a "Spec Escalation" error.  
* **The Workflow:** The Human Architect must update spec.md, regenerate the Dafny Contract, and restart the pipeline.

## **6\. Narrative for Judges**

"In our system, the student is not allowed to grade their own exam. We lock the Dafny Contract using cryptographic hashing. If the AI Agent tries to 'lower the bar' to get the code to pass, the Guardian detects the tampering and locks the pipeline."
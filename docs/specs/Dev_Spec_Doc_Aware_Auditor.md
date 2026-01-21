# **Feature Spec: Doc-Aware Auditor (RAG)**

## **1\. The Logic Model**

The Auditor now includes a "Knowledge Base" component.

* **Input:** User Spec (English).  
* **Context:** Dafny Reference Manual (Text/PDF).  
* **Output:** Gap Report \+ Skeleton Code.

## **2\. Capabilities**

### **Function: AuditWithContext**

**Description:** Injects Dafny documentation into the System Prompt.

* **Logic:**  
  1. **Load Docs:** Read docs/knowledge/dafny\_ref.md (or similar).  
  2. **Truncate:** If too large, take the "Verification" and "Preconditions" chapters.  
  3. **Prompt Construction:**"You are a Verification Expert.  
     REFERENCE MATERIAL:  
     {dafny\_docs\_excerpt}  
     TASK:  
     Analyze this spec: '{user\_spec}'  
     Use the Reference Material to suggest advanced invariants (e.g. conservation of mass, multiset preservation)."

## **3\. Implementation Details**

* **File:** Update core\_auditor.py.  
* **Data:** Create docs/knowledge/ and place the Dafny docs there.
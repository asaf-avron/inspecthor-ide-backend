# **Guardian Gateway: Spec-Driven Development Process**

## **The Philosophy**

"We do not write code to see if it works. We write specs to define what 'working' means."

## **The Workflow Cycle**

### **1\. The Architect's Canvas (Human Phase)**

Goal: Capture Business Intent without implementation details.  
Tool: Markdown Template (Template\_Architects\_Canvas.md).  
Rules:

* **No Database Talk:** Do not mention SQL, Redis, or Tables in the "Logic Model". Talk about "Entities" and "Maps".  
* **Strict Invariants:** Define what must *always* be true (e.g., "Balance \>= 0").  
* **Pure Functions:** Identify the core logic separate from the API shell.

### **2\. The Ambiguity Hunt (AI Auditor Phase)**

Goal: Stress-test the English logic before writing a single line of code.  
Action: The "Auditor" (Gemini 3\) scans the Canvas for:

* **Missing Preconditions:** "What if the input is null?" "What if amount is negative?"  
* **State Corruptions:** "Does this operation preserve the Total Supply invariant?"  
* **Race Conditions:** "What if two transfers happen exactly at once?"

### **3\. The Dafny Contract (Formal Phase)**

Goal: Translate English "Promises" into Mathematical "Ensures".  
Output: interface.dfy.  
Key mapping:

* Logic Model \-\> class or datatype  
* Invariants \-\> predicate Valid()  
* Preconditions \-\> requires  
* Postconditions \-\> ensures

### **4\. The Functional Core (Implementation Phase)**

Goal: Write Python code that satisfies the Dafny Contract.  
Constraint: Must be Pure Python (no I/O, no random, no globals) to pass verification.

## **Next Steps for Hackathon**

1. **Approve** the "Rewards System" draft (the demo case).  
2. **Audit** the draft to generate the "Gap Report" (the "Aha\!" moment for the audience).  
3. **Finalize** the interface.dfy that we will use in the live demo.
# **Guardian Gateway: Product Requirements Document (MVP)**

> **Note:** The UI has moved to the Next.js IDE; references to Streamlit in this doc are historical.

## **1\. User Personas**

* **The "Junior" Agent (Input):** A coding bot (Cursor/Windsurf) that generates Python code and submits PRs.  
* **The Compliance Officer (Stakeholder):** Requires proof that software meets specs (CSRD, Banking Regs).  
* **The DevOps Lead (User):** Needs a pipeline that prevents buggy AI code from reaching production.

## **2\. Functional Requirements**

### **Feature 1: Spec Auditor (Design Phase)**

* **Input:** Markdown text (spec.md).  
* **Logic:** Gemini 3 Pro (Thinking) identifies missing preconditions and edge cases.  
* **Output:** A "Gap Report" (JSON) and a Skeleton Dafny Contract.

### **Feature 2: Guardian Gateway (Build Phase)**

* **Input:** Python Source Code \+ Dafny Contract.  
* **Logic:** 1\. Translates Python logic to Dafny body. 2\. Compiles against the Contract. 3\. If fail \-\> Sends error to Gemini 3 Flash for "Self-Healing."  
* **Output:** Boolean Verified Status.

### **Feature 3: Spec Lens (Visualization)**

* **Input:** Dafny Contract.  
* **Logic:** "Humanizes" mathematical logic into English summaries.  
* **Output:** Interactive "Drill-Down" Dashboard for non-technical users.

## **3\. Hackathon Execution Plan**

**Phase 1: The Skeleton (Hours 1-4)**

* Setup auditor.py using google-genai SDK.  
* Install Dafny locally.  
* Create "Hello World" flow.

**Phase 2: The Brain & Eyes (Hours 5-12)**

* Implement Context Caching for Dafny Manual.  
* Implement thinking\_config for the "Split Translation."  
* Build Streamlit UI ("Mission Control").

**Phase 3: The Polish (Hours 13-18)**

* Implement the "Fixer Loop" (Self-Healing).  
* Create test\_spec.md with known bugs for the live demo.

**Phase 4: The Pitch**

* Scenario: Show "Junior Agent" deploying a banking exploit. Show Guardian catching and fixing it.
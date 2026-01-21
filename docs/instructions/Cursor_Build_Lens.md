# **Master Instruction: Guardian Spec Lens (Phase 1\)**

Context:  
We are building "Guardian Gateway," a formal verification tool.  
We are implementing the Spec Lens feature: a visualization dashboard that translates Dafny code into human-readable cards.  
**Reference Documentation (Crucial):**

* **Dafny Syntax:** https://dafny.org/latest/DafnyRef/DafnyRef (Refer to this for parsing trait, method, requires, ensures).  
* **Streamlit API:** https://docs.streamlit.io (Use modern features like st.status and st.expander).

**Local Context:**

* @Dev\_Spec\_Lens.md (The Blueprint)  
* @Guardian\_06\_Architecture\_Pattern.md (The "Pure Function" Rules)

## **The Mission**

Generate the following three files to implement the Spec Lens.

### **File 1: core\_parser.py (The Functional Core)**

* **Class:** DafnyParser  
* **Method:** parse(source\_code: str) \-\> Dict  
* **Logic:**  
  * Use **Regex** to parse a standard Dafny trait.  
  * **Robustness:** The parser must handle the provided interface.dfy structure (see File 3 below).  
  * **Extraction Targets:**  
    1. **Contract Name** (e.g., RewardsInterface).  
    2. **Methods** (e.g., SendKudos).  
    3. **Guardrails** (Extract requires lines). *Tip: Strip comments like // Fixes ... for the clean text, but keep them for a "reason" field if possible.*  
    4. **Promises** (Extract ensures lines).  
  * **Constraint:** Strictly Pure Python. No Streamlit imports.

### **File 2: app.py (The Imperative Shell)**

* **Framework:** Streamlit  
* **Flow:**  
  1. **Title:** "Guardian Gateway: Spec Lens".  
  2. **Input:** File Uploader (accept .dfy) OR a Default "Load Demo" button that loads tests/fixtures/interface.dfy.  
  3. **Processing:** Read string \-\> Call DafnyParser.parse().  
  4. **Layout:** Two Columns.  
     * **Col 1 (The Code):** st.code(language='dafny').  
     * **Col 2 (The Lens):** Iterate through the parsed methods.  
       * Use st.expander for each Method Name.  
       * **Guardrails Section:** Display requires with st.error(icon="🛡️").  
       * **Promises Section:** Display ensures with st.success(icon="✨").

### **File 3: tests/fixtures/interface.dfy (The Ground Truth)**

**Create this file exactly with this content to use as the test case:**

// Guardian Gateway: Immutable Contract  
// Feature: Rewards System (P2P Transfer)

// 1\. The Logic Model (State)  
type Database \= map\<string, int\>

trait RewardsInterface {  
      
    // Predicate: The Holy Laws (Invariants)  
    predicate Valid(db: Database) {  
        forall id :: id in db \==\> db\[id\] \>= 0  
    }

    // 2\. Capabilities (The Functional Core)  
    method SendKudos(db: Database, sender: string, receiver: string, amount: int)   
        returns (new\_db: Database, success: bool)  
      
    // GUARDRAILS (Preconditions)  
    requires amount \> 0                             // Fixes Negative Value Exploit  
    requires sender in db && receiver in db         // Fixes Ghost Employee Crash  
    requires sender \!= receiver                     // Fixes Self-Dealing  
    requires db\[sender\] \>= amount                   // Original Spec Rule  
    requires Valid(db)                              // System must be valid to start

    // PROMISES (Postconditions)  
    ensures success \==\> Valid(new\_db)               // Result must be valid  
    ensures success \==\> new\_db\[sender\] \== db\[sender\] \- amount  
    ensures success \==\> new\_db\[receiver\] \== db\[receiver\] \+ amount  
      
    // CONSERVATION OF MASS  
    ensures success \==\> forall id :: id in db && id \!= sender && id \!= receiver \==\> new\_db\[id\] \== db\[id\]  
}

**Execution Strategy:**

1. Write core\_parser.py first.  
2. Write tests/fixtures/interface.dfy.  
3. Write app.py.  
4. (Self-Correction): Before finishing, ensure the Regex in core\_parser.py actually works against the multi-line comments and predicate definitions in File 3\.
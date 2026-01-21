# **Guardian Gateway: High Level Design (HLD)**

## **1\. System Architecture Diagram**

The system functions as a unidirectional pipeline with three distinct components.  
`graph TD`  
    `subgraph "Phase 1: Design (The Ambiguity Hunter)"`  
        `User[Human Architect] -->|Writes spec.md| Auditor[Spec Auditor Service]`  
        `Auditor -->|Gemini 3 Pro (Thinking)| Gaps[Gap Report]`  
        `Auditor -->|Gemini 3 Pro (Thinking)| Contract[interface.dfy]`  
        `Gaps -->|Feedback Loop| User`  
    `end`

    `subgraph "Phase 2: Build (The Guardian)"`  
        `Agent[AI Coder] -->|Reads spec.md + interface.dfy| Python[implementation.py]`  
        `Python -->|Submit PR| Gateway[Guardian Gateway]`  
        `Gateway -->|Dual-Channel Translation| Verifier[Dafny Compiler]`  
        `Verifier -->|Success| Deploy[Production]`  
        `Verifier -->|Fail| Fixer[Gemini 3 Flash Loop]`  
        `Fixer -->|Retry| Gateway`  
    `end`  
      
    `subgraph "Phase 3: Visualization"`  
        `Contract -->|Parse| Lens[Spec Lens UI]`  
        `Gateway -->|Stream Logs| Console[Mission Control UI]`  
    `end`

## **2\. Technology Stack (The "Gemini 3 Stack")**

* **Brain:** **Gemini 3 Pro** (thinking\_level="high"). Performs the "Split Translation" (Python \-\> Dafny) using deep reasoning.  
* **Reflexes:** **Gemini 3 Flash**. The "Fixer Loop." Fast, cheap iterations to repair buggy code.  
* **Knowledge:** **Context Caching**. Caches the Dafny Manual \+ Project Style Guide for instant retrieval.  
* **Eyes:** **Gemini 3 Vision**. Compares code against a whiteboard architecture diagram.  
* **Judge:** **Dafny Compiler**. The mathematical engine that approves or rejects the logic.  
* **Sandbox:** **Nomad / Docker**. Ephemeral environment to run the code safely.  
* **UI:** **Streamlit**. Pure Python dashboard for "Mission Control."

## **3\. Data Flow & API Design**

### **3.1. The "Ambiguity Hunt" (Auditor Flow)**

* **Input:** User pastes spec.md into Streamlit.  
* **Process:**  
  1. Call Gemini 3 Pro (Config: thinking\_level="high").  
  2. System Prompt: "Extract Nouns (State) and Verbs (Methods). Identify missing preconditions."  
  3. Output: JSON { "code": "...", "gaps": \[...\] }.  
* **Output:** Streamlit renders "Gap Cards" (Red/Yellow).

### **3.2. The "Verification Loop" (Guardian Flow)**

* **Input:** agent\_code.py \+ interface.dfy.  
* **Process:**  
  1. **Dual Translation:** \* Channel A: agent\_code.py Logic \-\> implementation.dfy Body.  
     * Channel B: interface.dfy Contracts \-\> Included as Trait.  
  2. **Compilation:** Run dafny verify implementation.dfy.  
  3. **Result:** Capture exit\_code.  
* **Output:** Streamlit updates status to Green (Signed) or Red (Blocked).
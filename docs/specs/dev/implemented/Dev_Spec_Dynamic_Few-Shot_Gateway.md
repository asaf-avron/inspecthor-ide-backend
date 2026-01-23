# **Feature Spec: Dynamic Few-Shot Gateway**

## **1\. The Logic Model**

The Gateway (Transpiler) logic is decoupled from the Prompt Examples.

* **Entities:** PromptExample  
* **Structure (JSON):**  
  {  
      "name": "Bank Transfer",  
      "contract": "trait Bank { ... }",  
      "python": "def withdraw(...): ...",  
      "dafny\_impl": "class BankImpl ... { ... }"  
  }

## **2\. Capabilities**

### **Class: PromptLoader**

**Description:** Manages the library of "Golden Examples."

* **Method:** load\_examples(dir\_path: str) \-\> str  
* **Logic:**  
  1. Scan assets/examples/\*.json.  
  2. Format them into the "Input \-\> Output" text block for the LLM.  
  3. Return the formatted string to be injected into the System Prompt.

## **3\. Implementation Details**

* **File:** Update core\_gateway.py.  
* **Storage:** Create assets/examples/.  
* **Benefit:** To make the model smarter, we just add a new JSON file. No code changes.
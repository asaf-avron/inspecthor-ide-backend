# **Guardian Gateway: The Spec-Driven Methodology**

## **1\. The Core Philosophy: Proof-Driven Development (PDD)**

We invert the typical development pyramid. Instead of writing code and then testing it, we write the **Specification** and then **Refine** it into code.

### **The Hierarchy of Truth**

| Source | Role | Authority Level | Function |
| :---- | :---- | :---- | :---- |
| **Dafny Spec** | **The Law** | **Highest (Hard Constraint)** | Correctness, input validation, edge cases. |
| **English Spec** | **The Guide** | **Medium (Soft Context)** | Variable naming, readability, business intent. |

## **2\. The "Gap Analysis" (Ambiguity Hunter)**

The Spec Auditor uses Gemini 3 to interrogate the English text for missing logic.  
**Example Gap Detection:**

* *Input:* "The transfer function moves money."  
* *Gap Found:* "Missing Precondition: What if the sender has insufficient funds?"  
* *Dafny Fix:* requires sender.balance \>= amount

## **3\. The "Ironclad Handshake" (Refinement)**

The system enforces strict compliance between the Interface and the Implementation using Dafny's class refinement features.  
**File 1: The Law (interface.dfy)**  
`trait BankingInterface {`  
    `method Transfer(amount: int) returns (success: bool)`  
        `requires amount > 0`  
        `ensures success ==> old(balance) == balance + amount`  
`}`

**File 2: The Worker (implementation.dfy)**  
`class MyBank extends BankingInterface {`  
    `method Transfer(amount: int) returns (success: bool) {`  
        `// Implementation logic...`  
    `}`  
`}`

**Verification Check:** If the Implementation returns true but the balance does not change, Dafny raises: Error: Method does not satisfy the postcondition of the trait.

## **4\. The System Prompts**

### **The Auditor Prompt (Gemini 3 Pro)**

"You are a Senior Formal Methods Engineer. Analyze the Nouns (State) and Verbs (Methods). Hunt for Gaps: Did the user specify valid inputs? What happens if the resource doesn't exist? Generate a Dafny Trait and a Gap Report."

### **The Dual-Input Code Gen Prompt**

"Input 1: English Context (The Guide). Input 2: Dafny Contract (The LAW). Write the implementation body. Ensure it passes the Dafny compiler. Do not change the signature."
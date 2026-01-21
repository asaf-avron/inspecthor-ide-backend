# **Guardian Gateway: Feature Specification Template**

## **1\. How to use this Template**

This template is designed to support **Spec-Driven Development**. By filling out these specific sections, you provide the **Spec Auditor** (Gemini 3\) with the structure it needs to generate perfect Dafny contracts.  
**Philosophy:**

* **Don't write:** "Make it work."  
* **Do write:** "Given State X and Input Y, guarantee State Z."

# **\[Feature Name\] Specification**

## **1\. The Logic Model (The State)**

*Describe the abstract data this feature manipulates. Do not worry about database implementation (SQL/NoSQL).*

* **Entities:** \[e.g., User, Wallet, InventoryItem\]  
* **Key Variables:** \[e.g., User.Balance (Integer), Inventory.Count (Integer \>= 0)\]  
* **Invariants (The Holy Laws):**  
  * \[e.g., A Wallet balance can never be negative.\]  
  * \[e.g., The total number of items in the system must remain constant during a transfer.\]

## **2\. Capabilities (The Functional Core)**

*Define the pure logic functions. Mark strictly what is allowed and what is guaranteed.*

### **Function: \[FunctionName\]**

* **Description:** \[One sentence summary\]  
* **Inputs:**  
  * \[Variable Name\]: \[Type\] \- \[Description\]  
* **Preconditions (Guardrails):**  
  * *What must be true BEFORE this runs?*  
  * \[e.g., Input Amount must be \> 0\]  
  * \[e.g., User must be active\]  
* **Postconditions (Promises):**  
  * *What is guaranteed to be true AFTER this runs?*  
  * \[e.g., Receiver balance increases by exactly Amount\]  
  * \[e.g., Sender balance decreases by exactly Amount\]  
* **Edge Case Handling:**  
  * \[e.g., If Sender \== Receiver, do nothing and return True.\]

## **3\. The Imperative Shell (Out of Scope)**

*List the I/O operations that surround this logic. The Guardian will NOT verify these, but needs to know they exist.*

* **External Calls:** \[e.g., Fetch User from Postgres\]  
* **Side Effects:** \[e.g., Send Email Notification\]

## **Example: Peer-to-Peer Transfer (Filled Out)**

### **1\. The Logic Model**

* **Entities:** Account  
* **Variables:** Account.Balance (Integer)  
* **Invariants:** TotalSystemMoney must be constant (Conservation of Mass).

### **2\. Capabilities**

#### **Function: TransferPoints**

* **Inputs:**  
  * sender\_id: String  
  * receiver\_id: String  
  * amount: Integer  
* **Preconditions:**  
  * amount must be positive (\> 0).  
  * sender must have balance \>= amount.  
  * sender\_id must not equal receiver\_id (No self-dealing).  
* **Postconditions:**  
  * sender.balance decreases by amount.  
  * receiver.balance increases by amount.  
  * Sum of sender \+ receiver balance remains unchanged.

### **3\. Imperative Shell**

* Load accounts from Redis.  
* Save updated balances to Redis.  
* Log transaction to Splunk.
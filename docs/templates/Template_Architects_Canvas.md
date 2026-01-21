# **\[Feature Name\] Specification**

## **1\. The Logic Model (The State)**

*Describe the abstract data this feature manipulates. Focus on the "Truth" of the system.*

* **Entities:** \[e.g., User, Wallet, Order\]  
* **Key State Variables:**  
  * \[Entity\].\[Variable\]: \[Type\] (e.g., User.Balance: Integer)  
* **Invariants (The Holy Laws):**  
  * *What must NEVER be false?*  
  * \[e.g., A Wallet balance can never be negative.\]  
  * \[e.g., The sum of all balances must equal the Total Supply.\]

## **2\. Capabilities (The Functional Core)**

*Define the pure logic functions. This is what the Guardian will verify.*

### **Function: \[FunctionName\]**

**Description:** \[One sentence summary\]

* **Inputs:**  
  * \[Name\]: \[Type\]  
* **Preconditions (Guardrails):**  
  * *What must be true BEFORE this runs?*  
  * \[e.g., Input Amount \> 0\]  
  * \[e.g., Sender exists in the system\]  
* **Postconditions (Promises):**  
  * *What is guaranteed to be true AFTER this runs?*  
  * \[e.g., Return value is True\]  
  * \[e.g., Sender balance decreases by exactly Amount\]  
* **Edge Case Handling:**  
  * \[e.g., If Sender \== Receiver, return False.\]

## **3\. The Imperative Shell (Unverified I/O)**

*List the external operations. The Guardian ignores these, but the Human Architect needs them.*

* **Reads:** \[e.g., Fetch User from Postgres\]  
* **Writes:** \[e.g., Update Redis Cache\]  
* **Side Effects:** \[e.g., Send Push Notification\]
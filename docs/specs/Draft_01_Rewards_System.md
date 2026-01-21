# **Rewards System Specification (Draft v1)**

## **1\. The Logic Model (The State)**

We are building a simple P2P rewards system where employees can send "Kudos Points" to each other.

* **Entities:** Employee  
* **Key State Variables:**  
  * Employee.Id: String  
  * Employee.Balance: Integer (Current points held)  
* **Invariants:**  
  * An employee's balance cannot be negative.

## **2\. Capabilities (The Functional Core)**

### **Function: SendKudos**

**Description:** Transfers points from one employee to another.

* **Inputs:**  
  * sender: Employee  
  * receiver: Employee  
  * amount: Integer  
* **Preconditions (Guardrails):**  
  * The sender must have enough points to cover the amount.  
* **Postconditions (Promises):**  
  * The sender's balance is decreased by amount.  
  * The receiver's balance is increased by amount.  
  * The function returns True if successful.

## **3\. The Imperative Shell (Unverified I/O)**

* Fetch sender and receiver data from the SQL Database.  
* Save the new balances back to the Database.  
* Send a Slack notification to the receiver.
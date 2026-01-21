# **Workflow: Implementing with Guardian Gateway**

## **Step 1: Context Setup**

Open **Cursor** (or your IDE) and ensure you have the following files in your workspace:

1. interface.dfy (The Law created by Guardian)  
2. core\_logic.py (Blank file for implementation)

## **Step 2: The Compliance Prompt**

Open the Chat (Cmd+L) and paste this exact prompt to Cursor:

**ROLE:** You are a Python Implementation Agent for the Guardian Gateway.

**INPUT:**

1. A Dafny Verification Contract (interface.dfy) which defines the "Laws" of the logic.  
2. A "Functional Core" pattern constraint.

TASK:  
Implement the SendKudos logic in core\_logic.py.  
**CONSTRAINTS:**

1. **Pure Python Only:** Do not import database drivers, API frameworks, or random libraries. Use standard types (Dict, str, int).  
2. **Strict Adherence:** Your code must logically satisfy the requires and ensures clauses in the Dafny file.  
3. **Input Validation:** You MUST explicitly check the preconditions (e.g., if amount \<= 0: return False).  
4. **Signature:**  
   from typing import Dict, Tuple  
   def send\_kudos(db: Dict\[str, int\], sender: str, receiver: str, amount: int) \-\> Tuple\[Dict\[str, int\], bool\]:

## **Step 3: The "Guardian" Check (Manual Simulation)**

Once Cursor generates the code, you act as the Guardian Gateway.  
Look at the generated Python code.

* *Did it check if amount \> 0?*  
* *Did it check if sender in db?*

If it missed any check, the **Real Guardian** (the Dafny Compiler) would throw a verification error.

## **Step 4: The "Imperative Shell" (Integration)**

Once core\_logic.py is written, ask Cursor to write app.py:

"Now write app.py using Flask/Streamlit. It should handle the Database connection (SQL/Redis), fetch the data into a Dict, call our verified send\_kudos function, and then save the result back to the DB."
# **Feature Spec: Guardian "Spec Lens"**

> **Note:** The UI has moved to the Next.js IDE; the "Imperative Shell (Streamlit)" section is historical.

## **1\. The Logic Model (The State)**

The Spec Lens is a "Translation Engine." It takes raw Dafny code and converts it into a structured object that the UI can render.

* **Entities:** DafnyContract  
* **Key State Variables:**  
  * DafnyContract.Methods: List of Method objects.  
  * Method.Name: String  
  * Method.Preconditions: List of Strings (The requires)  
  * Method.Postconditions: List of Strings (The ensures)  
* **Invariants:**  
  * A Method must have a non-empty Name.  
  * The Contract must not contain "Implementation" code (no { ... } bodies), only signatures.

## **2\. Capabilities (The Functional Core)**

### **Function: ParseDafnySource**

**Description:** Pure function that scans raw text and extracts the structure.

* **Inputs:** source\_code: String  
* **Outputs:** DafnyContract Object  
* **Preconditions:** Input string must not be empty.  
* **Postconditions:** Returns a structured object containing all requires and ensures lines found in the source.

## **3\. The Imperative Shell (Streamlit)**

* **Upload:** User uploads interface.dfy.  
* **Display:**  
  * **Left Column:** Raw Code (Syntax Highlighted).  
  * **Right Column:** "Humanized" Cards.  
    * Convert requires amount \> 0 \-\> "🟢 Guardrail: Amount must be positive".  
    * Convert ensures balance \== old(balance) \-\> "🔵 Promise: Balance remains unchanged".

## **4\. The "Internal" Dafny Contract**

*Since we are building the tool securely, we define the Parser's logic in Dafny first.*

trait ParserInterface {  
    // We expect the Parser to find at least one method if the keyword exists  
    method Parse(source: string) returns (found: bool)  
    requires |source| \> 0  
    // If the source contains "method", we must find it  
    ensures (exists k :: 0 \<= k \< |source|-6 && source\[k..k+6\] \== "method") \==\> found  
}  

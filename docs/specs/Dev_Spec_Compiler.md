# **Feature Spec: Guardian Gateway (The Compiler)**

## **1\. The Logic Model**

The Gateway is the "CI/CD Firewall." It proves that the implementation matches the design.

* **Entities:** VerificationResult  
* **Key Variables:**  
  * Result.Status: Boolean (Verified/Failed)  
  * Result.Message: String (Compiler output or Error explanation)

## **2\. Capabilities (The Functional Core)**

### **Function: VerifyCode**

**Description:** The core pipeline that connects Python to Dafny.

* **Inputs:** \* contract\_code: String (The .dfy content from the Auditor)  
  * python\_code: String (The implementation from the Agent)  
* **Logic (The "Transpiler Bridge"):**  
  1. **Translation:** Call Gemini 3 Flash.  
     * *Prompt:* "Translate this Python function into a Dafny implementation method that implements this Trait."  
  2. **Assembly:** Merge the interface.dfy (Trait) and impl.dfy (Translation) into a temporary file.  
  3. **Compilation:** Run dafny verify temp.dfy via Python subprocess.  
  4. **Analysis:** Parse the STDOUT.  
     * If "0 errors", return True.  
     * If errors, return False \+ the specific line number.

## **3\. The Imperative Shell (Streamlit)**

* **New Tab:** "The Gateway"  
* **Input:** Two text areas (Contract & Python Code).  
* **Action:** Button "Run Verification".  
* **Output:** \* **Green Badge:** "Cryptographically Verified"  
  * **Red Alert:** "Verification Failed" \+ Compiler Logs.
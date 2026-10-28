# **Dafny Reference Manual (RAG Optimized)**

For: Inspecthor Spec Auditor  
Focus: Verification, Refinement, and Contracts

## **1\. Core Types & Logic**

* **Basic Types:** bool, int (mathematical integer, infinite precision), real, string.  
* **Collection Types:**  
  * set\<T\>: Finite set (unordered, unique). s1 \+ s2 (union), s1 \* s2 (intersection), x in s.  
  * seq\<T\>: Immutable sequence. s\[i\] (index), s\[..i\] (prefix), s1 \+ s2 (concat). |s| is length.  
  * map\<K,V\>: Immutable dictionary. m\[k\] (lookup), k in m (membership).  
  * multiset\<T\>: Set with counts.

## **2\. Method Contracts (The Hoare Triplet)**

Methods are opaque units of verification.

method Transfer(amount: int) returns (success: bool)  
    requires amount \> 0                 // Precondition (Guardrail)  
    modifies this                       // Frame Rule (What can change)  
    ensures success \==\> balance \> 0     // Postcondition (Promise)  
    ensures \!success \==\> balance \== old(balance) // State preservation  
{  
    // Body must satisfy ALL ensures given the requires  
}

## **3\. Functions vs. Predicates**

* **Function:** Pure mathematical mapping. Must be side-effect free. Used in specs.  
* **Predicate:** A function returning bool. Used for Invariants.

// Pure function (can be used in requires/ensures)  
function Sum(a: int, b: int): int { a \+ b }

// Predicate (used for validity checks)  
predicate ValidState(db: map\<string, int\>) {  
    forall u :: u in db \==\> db\[u\] \>= 0  
}

## **4\. Class Refinement (The Guardian Pattern)**

This is the core mechanism for connecting Abstract Traits to Concrete Implementations.

**The Trait (Interface):**

trait BankInterface {  
    var balance: int  
    method Withdraw(x: int) returns (ok: bool)  
        modifies this  
        ensures ok \==\> balance \< old(balance)  
}

**The Implementation (Refinement):**

class BankImpl extends BankInterface {  
    // CRITICAL: You must restate or refine the contract  
    method Withdraw(x: int) returns (ok: bool)  
        // Explicitly inheriting the contract logic  
        ensures ok \==\> balance \< old(balance)   
    {  
        if x \> 0 && balance \> x {  
            balance := balance \- x;  
            return true;  
        }  
        return false;  
    }  
}

## **5\. Advanced Quantifiers (The "Brain" Logic)**

* **Forall:** forall x :: x in s \==\> x \> 0 (All elements are positive).  
* **Exists:** exists x :: x in s && x \< 0 (There exists a negative element).

## **6\. Map Preservation (Structural Integrity)**

When a method transforms a map (e.g., transferring between accounts), you must prove keys are preserved before accessing values in the new map.

**The Problem:**
If you have `requires sender in db` but your ensures clause references `new_db[sender]`, Dafny cannot prove `sender in new_db` without explicit guidance.

**The Fix - Add Structural Integrity Clause:**

method Transfer(db: map<string, int>, sender: string, receiver: string, amount: int)
    returns (new_db: map<string, int>, success: bool)
    
    // Preconditions
    requires sender in db && receiver in db
    requires amount > 0 && db[sender] >= amount
    
    // STRUCTURAL INTEGRITY: Keys are preserved
    ensures success ==> (forall k :: k in db <==> k in new_db)
    
    // Now these are safe (Dafny knows sender/receiver are in new_db)
    ensures success ==> new_db[sender] == db[sender] - amount
    ensures success ==> new_db[receiver] == db[receiver] + amount
    
    // Conservation: Unchanged keys keep their values
    ensures success ==> forall id :: id in db && id != sender && id != receiver ==> new_db[id] == db[id]

**Why it works:**
1. `requires sender in db` → sender exists in old map
2. `ensures (k in db <==> k in new_db)` → same keys in both maps
3. Therefore: `sender in new_db` → safe to access `new_db[sender]`

## **7\. Common Verification Errors & Fixes**

* **"Element might not be in domain":** You accessed map\[k\] without requires k in map. Add structural integrity clause for transformed maps.  
* **"Postcondition might not hold":** The code path didn't explicitly prove the promise.  
* **"Modifies clause violation":** You changed a variable not listed in modifies.
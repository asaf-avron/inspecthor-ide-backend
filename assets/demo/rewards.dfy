// Inspecthor: Immutable Contract
// Feature: Rewards System (P2P Transfer)

// 1. The Logic Model (State)
type Database = map<string, int>

trait RewardsInterface {
    
    // Predicate: The Holy Laws (Invariants)
    predicate Valid(db: Database) {
        forall id :: id in db ==> db[id] >= 0
    }

    // 2. Capabilities (The Functional Core)
    method SendKudos(db: Database, sender: string, receiver: string, amount: int) 
        returns (new_db: Database, success: bool)
    
    // GUARDRAILS (Preconditions)
    requires amount > 0                             // [REF-01] Fixes Negative Value Exploit
    requires sender in db && receiver in db         // [REF-02] Fixes Ghost Employee Crash
    requires sender != receiver                     // [REF-03] Fixes Self-Dealing
    requires db[sender] >= amount                   // [REF-04] Original Spec Rule
    requires Valid(db)                              // [REF-05] System must be valid to start

    // STRUCTURAL INTEGRITY (The Bridge)
    ensures success ==> (forall k :: k in db <==> k in new_db)

    // PROMISES (Postconditions)
    ensures success ==> Valid(new_db)               // [REF-06] Result must be valid
    ensures success ==> new_db[sender] == db[sender] - amount      
    ensures success ==> new_db[receiver] == db[receiver] + amount
    
    // CONSERVATION OF MASS
    ensures success ==> forall id :: id in db && id != sender && id != receiver ==> new_db[id] == db[id]
}
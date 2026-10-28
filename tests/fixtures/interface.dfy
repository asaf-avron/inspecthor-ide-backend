// Inspecthor: Immutable Contract
// Feature: Rewards System (P2P Transfer)

// 1. The Logic Model (State)
// We model the Database as a Map of Employee IDs to Balance (Integers)
type Database = map<string, int>

trait RewardsInterface {
    
    // Predicate: The Holy Laws (Invariants)
    // 1. All balances must be non-negative
    predicate Valid(db: Database) {
        forall id :: id in db ==> db[id] >= 0
    }

    // 2. Capabilities (The Functional Core)
    // We define the abstract method signature.
    // The implementation MUST satisfy these 'requires' and 'ensures'.
    method SendKudos(db: Database, sender: string, receiver: string, amount: int) 
        returns (new_db: Database, success: bool)
    
    // GUARDRAILS (Preconditions)
    // The "Gap Analysis" added these to prevent exploits:
    requires amount > 0                             // Fixes Negative Value Exploit
    requires sender in db && receiver in db         // Fixes Ghost Employee Crash
    requires sender != receiver                     // Fixes Self-Dealing
    requires db[sender] >= amount                   // Original Spec Rule
    requires Valid(db)                              // System must be valid to start

    // STRUCTURAL INTEGRITY (The Bridge)
    // Keys are preserved - this allows Dafny to prove sender/receiver exist in new_db
    ensures success ==> (forall k :: k in db <==> k in new_db)

    // PROMISES (Postconditions)
    ensures success ==> Valid(new_db)               // Result must be valid
    ensures success ==> new_db[sender] == db[sender] - amount      // Sender logic
    ensures success ==> new_db[receiver] == db[receiver] + amount  // Receiver logic
    
    // CONSERVATION OF MASS (The Invisible Law)
    // The total points of everyone ELSE must not change
    ensures success ==> forall id :: id in db && id != sender && id != receiver ==> new_db[id] == db[id]
}
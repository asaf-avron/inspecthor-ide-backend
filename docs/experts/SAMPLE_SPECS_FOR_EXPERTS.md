# Sample English Specifications for Expert Review

This document provides example English specifications (Gil's Input) to demonstrate the Clover Loop refinement process for the InspecThor experts.

---

## Example 1: Rewards System (Simple)

### Raw English Input (Gil's Input)

```
A rewards system where employees can send "Kudos Points" to each other.

Entities:
- Employee with ID and Balance

Capabilities:
- SendKudos: Transfer points from sender to receiver
  - Precondition: Sender must have enough points
  - Postcondition: Sender balance decreases, receiver balance increases
  - Invariant: Employee balance cannot be negative
```

### Expected Refinement Flow

1. **Triage Stage:** Identifies as "functional specification"
2. **Structuring Stage:** Extracts state (Employee, Balance) and methods (SendKudos)
3. **Audit Stage:** Generates Dafny skeleton with contracts
4. **Unit Identification:** May identify as single unit (simple system)

### Expected Dafny Output

```dafny
module RewardsSystem {
  datatype Employee = Employee(id: string, balance: int)
  
  predicate ValidEmployee(e: Employee) {
    e.balance >= 0
  }
  
  method SendKudos(
    sender: Employee,
    receiver: Employee,
    amount: int
  ) returns (newSender: Employee, newReceiver: Employee, success: bool)
    requires ValidEmployee(sender)
    requires ValidEmployee(receiver)
    requires amount > 0
    requires sender.balance >= amount
    ensures success ==>
      newSender.balance == sender.balance - amount &&
      newReceiver.balance == receiver.balance + amount &&
      ValidEmployee(newSender) &&
      ValidEmployee(newReceiver)
  {
    // Implementation
  }
}
```

---

## Example 2: Voting System (With State)

### Raw English Input

```
A voting system for proposals.

State:
- Proposals: Each has an ID, title, status (open/closed)
- Votes: Each user can vote once per proposal
- Vote tracking: Map of (proposal_id, user_id) -> has_voted

Capabilities:
- CreateProposal: Create a new proposal (status=open)
- CastVote: User votes on a proposal
  - Precondition: Proposal is open, user hasn't voted yet
  - Postcondition: User marked as voted, vote counted
- CloseProposal: Close voting and tally results
  - Precondition: Proposal is open
  - Postcondition: Proposal status = closed, results available
```

### Expected Refinement Flow

1. **Triage:** "Stateful system with multiple operations"
2. **Structuring:** Identifies three methods, state invariants
3. **Audit:** Generates Dafny with state transitions
4. **Unit Identification:** May break into units:
   - Unit 1: Proposal Management (Create, Close)
   - Unit 2: Voting Logic (CastVote)

### Expected Dafny Output (Simplified)

```dafny
module VotingSystem {
  datatype ProposalStatus = Open | Closed
  
  datatype Proposal = Proposal(
    id: string,
    title: string,
    status: ProposalStatus,
    voteCount: nat
  )
  
  // State: has_voted map
  var has_voted: map<(string, string), bool>;  // (proposal_id, user_id)
  var proposals: map<string, Proposal>;
  
  method CreateProposal(id: string, title: string) returns (success: bool)
    requires id !in proposals
    ensures success ==> proposals[id].status == Open
  {
    // Implementation
  }
  
  method CastVote(proposalId: string, userId: string) returns (success: bool)
    requires proposalId in proposals
    requires proposals[proposalId].status == Open
    requires !has_voted[(proposalId, userId)]
    ensures success ==> has_voted[(proposalId, userId)] == true
    ensures success ==> proposals[proposalId].voteCount == old(proposals[proposalId].voteCount) + 1
  {
    // Implementation
  }
}
```

---

## Example 3: File Management System (Our Use Case)

### Raw English Input

```
A file management system where users can create and manage files within projects.

State:
- Projects: Each project has an ID, name, owner (user_id or api_key_hash)
- Files: Each file belongs to a project, has filename, content, type (md/dfy/unit)

Invariants:
- Files must belong to an existing project
- Filenames are unique within a project
- Users can only access files in projects they own

Capabilities:
- CreateProject: Create new project (owned by user)
- SaveFile: Save file to project
  - Precondition: Project exists and user owns it, filename unique in project
  - Postcondition: File created with correct project_id
- UpdateFile: Update file content or rename
  - Precondition: File exists, user owns project, new filename unique (if renaming)
  - Postcondition: File updated, renamed flag set if renamed
- DeleteFile: Delete file
  - Precondition: File exists, user owns project
  - Postcondition: File removed from project
- DeleteProject: Delete project and all its files (cascade)
  - Precondition: Project exists, user owns it
  - Postcondition: Project and all files deleted
```

### Expected Refinement Flow

1. **Triage:** "CRUD system with ownership constraints"
2. **Structuring:** Extracts ownership model, uniqueness constraints
3. **Audit:** Generates Dafny with ownership predicates, uniqueness invariants
4. **Unit Identification:** May identify:
   - Unit 1: Project Operations (Create, Delete with cascade)
   - Unit 2: File Operations (Save, Update, Delete)
   - Unit 3: Ownership Verification (shared across units)

### Expected Dafny Output (Conceptual)

```dafny
module FileManagement {
  datatype FileType = MD | DFY | Unit
  
  datatype File = File(
    fileId: string,
    projectId: string,
    filename: string,
    content: Content,  // Opaque
    fileType: FileType
  )
  
  datatype Project = Project(
    projectId: string,
    name: string,
    ownerId: string  // user_id or api_key_hash
  )
  
  // State snapshot
  datatype SystemState = SystemState(
    projects: map<string, Project>,
    files: map<string, File>,
    ghost activeFilenames: set<(string, string)>
  )
  
  predicate OwnsProject(state: SystemState, projectId: string, ownerId: string)
  {
    projectId in state.projects &&
    state.projects[projectId].ownerId == ownerId
  }
  
  function SaveFile(
    state: SystemState,
    projectId: string,
    filename: string,
    content: Content,
    fileType: FileType,
    ownerId: string
  ): (newState: SystemState, result: Result<string>)
    requires ValidState(state)
    requires OwnsProject(state, projectId, ownerId)
    requires (projectId, filename) !in state.activeFilenames
    ensures result.Success? ==>
      result.value in newState.files &&
      newState.files[result.value].projectId == projectId &&
      (projectId, filename) in newState.activeFilenames
  {
    // Implementation
  }
}
```

---

## Example 4: Bank Transfer (From Assets)

### Raw English Input

```
A bank transfer system that transfers money between accounts.

State:
- Balances: Map of account_id -> balance amount

Capabilities:
- Transfer: Move amount from one account to another
  - Precondition: Both accounts exist, amount > 0, sender has sufficient balance
  - Postcondition: Sender balance decreased, receiver balance increased
  - Invariant: Account balances remain non-negative
```

### Expected Dafny Output (From assets/examples/bank_transfer.json)

```dafny
trait BankInterface {
  method Transfer(
    balances: map<string, int>,
    from_acct: string,
    to_acct: string,
    amount: int
  ) returns (new_balances: map<string, int>, success: bool)
    requires from_acct in balances && to_acct in balances
    requires amount > 0
    ensures success ==> (forall k :: k in balances <==> k in new_balances)
    ensures success ==> new_balances[from_acct] == balances[from_acct] - amount
    ensures success ==> new_balances[to_acct] == balances[to_acct] + amount
}
```

---

## Clover Loop Demonstration Request

**For Experts:** Please demonstrate the Clover Loop refinement process using **Example 3 (File Management System)** as it matches our actual use case.

**Expected Demonstration:**
1. **Input:** Raw English spec (Example 3 above)
2. **Step 1:** Triage result (doc type, confidence)
3. **Step 2:** Structured spec (formatted markdown)
4. **Step 3:** Dafny skeleton with contracts
5. **Step 4:** Unit identification (if applicable)
6. **Step 5:** Refined Dafny spec (optimized with ghost sets, opaque types)

This will show us:
- How Gemini refines the spec
- What the intermediate stages look like
- How to structure our Dafny specs for optimal verification performance

---

## Notes for Experts

1. **Ownership Model:** Our system supports both authenticated users (`user_id`) and anonymous users (`api_key_hash`). This needs to be modeled in Dafny.

2. **Cascade Deletion:** SQLAlchemy handles CASCADE delete at the database level. We need to verify the logical correctness in Dafny.

3. **File Content:** We don't need to verify content syntax, just:
   - Size consistency (`size_bytes == content.length`)
   - Ownership
   - Uniqueness

4. **Unit Deconstruction:** When a spec is broken into units, we need to verify:
   - Unit line ranges are valid
   - Units don't overlap incorrectly
   - Traceability links are consistent

---

## Questions for Experts

1. **How to model nullable ownership?** (`user_id` OR `api_key_hash`, not both)
2. **Best way to handle UUIDs?** Convert to strings or use opaque type?
3. **Ghost set maintenance:** How to prove ghost set stays consistent?
4. **Batch operations:** How to verify cascade deletion efficiently?
5. **Synthesis target:** What LLM/model should we use for Python synthesis?

# Verification Condition Generator Specification

> **Phase:** 2 - The Bridge (The Integration)  
> **Priority:** P0 - Core formal verification capability  
> **Estimated Effort:** 4 sprints

---

## 1. Logic Model (State)

### Entities
- **Claim** - Structured English requirement with formal annotations
- **VerificationCondition (VC)** - Mathematical assertion to be proven
- **DafnyModule** - Generated Dafny code containing VCs
- **ProofResult** - Solver output (verified, failed, timeout)

### Key State Variables
- `Claim.id`: String (REF-XX format)
- `Claim.preconditions`: List[Assertion]
- `Claim.postconditions`: List[Assertion]
- `VC.claim_id`: String (link to source claim)
- `VC.assertion`: String (Dafny expression)
- `VC.status`: Enum (pending, verified, failed, timeout)

### Invariants
- Every Claim must generate at least 1 VC
- VCs must be traceable back to source Claim
- A ProofResult must exist for every discharged VC
- Sum of (verified + failed + timeout) VCs = total VCs

---

## 2. Capabilities (Functional Core)

### Function: ParseStructuredClaim

**Description:** Parse English claim with formal annotations into AST.

**Inputs:**
- `claim_text`: String - Structured English with annotations

**Preconditions:**
- Claim text is non-empty
- Claim follows structured template format

**Postconditions:**
- Returns ClaimAST with parsed preconditions, postconditions
- Each assertion is validated for syntax
- Error list is empty OR contains specific line/column info

**Edge Cases:**
- If no preconditions specified, assume `requires true`
- If no postconditions specified, return error (claims must have guarantees)

**Example Input:**
```markdown
## Claim: REQ-101
### Preconditions
- User balance >= withdrawal amount
- User account is active

### Postconditions  
- User balance decreases by exactly withdrawal amount
- Transaction is recorded in ledger
```

**Example Output:**
```python
ClaimAST(
    id="REQ-101",
    preconditions=[
        Assertion("user.balance >= amount"),
        Assertion("user.is_active == true")
    ],
    postconditions=[
        Assertion("user.balance == old(user.balance) - amount"),
        Assertion("ledger.contains(transaction)")
    ]
)
```

---

### Function: GenerateVerificationConditions

**Description:** Transform ClaimAST into Dafny VCs.

**Inputs:**
- `claim_ast`: ClaimAST - Parsed claim structure
- `context`: DafnyContext - Type definitions, existing modules

**Preconditions:**
- ClaimAST is valid (passed parsing)
- Context contains required type definitions

**Postconditions:**
- Returns list of VC objects
- Each VC has unique ID (VC-{claim_id}-{index})
- VCs are ordered: precondition checks, then postcondition checks
- Dafny code is syntactically valid

**Output Format:**
```dafny
// Generated from REQ-101
method Withdraw(user: User, amount: int) returns (success: bool)
    requires user.balance >= amount  // VC-REQ-101-1
    requires user.is_active          // VC-REQ-101-2
    ensures success ==> user.balance == old(user.balance) - amount  // VC-REQ-101-3
    ensures success ==> ledger.Contains(transaction)                // VC-REQ-101-4
{
    // Implementation body (to be provided)
}
```

---

### Function: RunVerification

**Description:** Execute Dafny verifier on generated VCs.

**Inputs:**
- `dafny_code`: String - Complete Dafny module
- `timeout_seconds`: Integer - Max verification time (default: 60)
- `solver`: Enum - SMT solver (z3, cvc5)

**Preconditions:**
- Dafny code is syntactically valid
- Dafny CLI is available
- Solver is installed and accessible

**Postconditions:**
- Returns ProofResult for each VC
- Verified VCs have empty counterexample
- Failed VCs have counterexample (if solver provides)
- Total time <= timeout_seconds + 5s buffer

**Edge Cases:**
- If timeout reached, mark remaining VCs as `timeout`
- If solver crashes, mark as `error` with crash log

---

## 3. API Endpoints

### POST /api/v1/verify/generate-vcs

**Request:**
```json
{
    "claim_text": "string",
    "context_blueprint_id": "uuid (optional)"
}
```

**Response:**
```json
{
    "claim_id": "REQ-101",
    "vcs": [
        {
            "vc_id": "VC-REQ-101-1",
            "assertion": "user.balance >= amount",
            "type": "precondition",
            "dafny_line": 3
        }
    ],
    "dafny_code": "// Generated Dafny...",
    "errors": []
}
```

### POST /api/v1/verify/run

**Request:**
```json
{
    "dafny_code": "string",
    "timeout_seconds": 60,
    "solver": "z3"
}
```

**Response:**
```json
{
    "verified": true,
    "vcs_discharged": 4,
    "vcs_total": 4,
    "results": [
        {
            "vc_id": "VC-REQ-101-1",
            "status": "verified",
            "time_ms": 42
        }
    ],
    "proof_certificate": { ... }
}
```

---

## 4. Implementation Files

### New Files

| File | Purpose |
|------|---------|
| `core/claim_parser.py` | Structured claim → AST |
| `core/vc_generator.py` | AST → Dafny VCs |
| `core/dafny_emitter.py` | VCs → Dafny code string |
| `api/endpoints/verify_vc.py` | New API endpoints |
| `tests/test_vc_generator.py` | Unit tests |

### Modified Files

| File | Changes |
|------|---------|
| `core/gateway.py` | Remove LLM transpilation, use VC generator |
| `api/main.py` | Add new verify router |
| `verifier/runner.py` | Return structured VC results |

---

## 5. Verification Plan

### Automated Tests
1. Parse known-good claims, verify AST structure
2. Generate VCs from AST, verify Dafny syntax valid
3. Run verification on simple VCs, verify correct results
4. Test timeout handling with complex VCs
5. Test error handling with malformed input

### Property-Based Tests
```python
# Using Hypothesis
@given(valid_claim())
def test_roundtrip(claim):
    ast = parse_claim(claim)
    vcs = generate_vcs(ast)
    assert len(vcs) >= 1
    assert all(vc.claim_id == ast.id for vc in vcs)
```

### Manual Verification
1. Write Banking domain claim
2. Generate VCs via API
3. Verify Dafny code compiles
4. Run verification, inspect proof output

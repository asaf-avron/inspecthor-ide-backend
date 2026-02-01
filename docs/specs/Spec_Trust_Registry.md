# Trust Registry Specification

> **Phase:** 3 - The Ledger (The Trust)  
> **Priority:** P0 - Immutable proof storage for compliance  
> **Estimated Effort:** 3 sprints

---

## 1. Logic Model (State)

### Entities
- **VerificationLedger** - Append-only chain of proof entries
- **ProofCertificate** - Complete structured proof with signatures
- **AuditEvent** - Who did what when (immutable log)
- **TrustedTimestamp** - RFC 3161 timestamp authority reference

### Key State Variables
- `LedgerEntry.sequence_number`: BigInt (monotonic, unique)
- `LedgerEntry.previous_hash`: String (SHA-256, chain link)
- `LedgerEntry.entry_hash`: String (SHA-256 of this entry)
- `LedgerEntry.immutable`: Boolean (always True after creation)
- `ProofCertificate.verifier_signature`: String (Ed25519)
- `ProofCertificate.claim_id`: String (traceable to source)

### Invariants
- **Append-Only**: Ledger entries can NEVER be modified or deleted
- **Chain Integrity**: `entry[n].previous_hash == entry[n-1].entry_hash`
- **Monotonic Sequence**: `entry[n].sequence_number == entry[n-1].sequence_number + 1`
- **All Entries Signed**: Every certificate has valid verifier signature
- **No Expiry**: Unlike current ProofReceipt, proofs do NOT expire

---

## 2. Capabilities (Functional Core)

### Function: CreateLedgerEntry

**Description:** Append new proof certificate to immutable ledger.

**Inputs:**
- `proof_certificate`: ProofCertificate - The verification result
- `verifier_key`: PrivateKey - Signing key for the verifier

**Preconditions:**
- Proof certificate is complete (all fields populated)
- Verifier key is valid and authorized
- Previous ledger entry exists (or this is genesis entry)

**Postconditions:**
- New entry appended with sequence_number = prev + 1
- Entry hash computed from all fields
- Previous hash links to last entry
- Signature covers: claim_id + result + timestamp + hashes
- Entry marked immutable = True

**Edge Cases:**
- If genesis entry (first ever), previous_hash = SHA256("GENESIS")
- If verifier key invalid, reject with AuthenticationError
- If concurrent writes, serialize via database lock

---

### Function: VerifyChainIntegrity

**Description:** Validate entire ledger chain from genesis to tip.

**Inputs:**
- `start_sequence`: BigInt (optional, default: 0)
- `end_sequence`: BigInt (optional, default: latest)

**Preconditions:**
- Ledger has at least one entry
- Start <= End

**Postconditions:**
- Returns IntegrityReport with pass/fail status
- If pass: all hashes verified, chain unbroken
- If fail: identifies first broken link with details

**Edge Cases:**
- Empty range returns trivial pass
- Single entry only checks entry hash, not chain

---

### Function: GetProofCertificate

**Description:** Retrieve proof certificate by claim ID or sequence number.

**Inputs:**
- `claim_id`: String (optional)
- `sequence_number`: BigInt (optional)
- One of the above must be provided

**Preconditions:**
- At least one identifier provided
- Entry exists in ledger

**Postconditions:**
- Returns complete ProofCertificate
- Includes chain position (sequence, previous/next hashes)
- Read-only: no mutations possible

---

## 3. Database Schema

### New Tables

```sql
-- Append-only ledger (no UPDATE, no DELETE allowed)
CREATE TABLE verification_ledger (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_number BIGSERIAL UNIQUE NOT NULL,
    
    -- Chain linkage
    previous_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    
    -- Proof content
    proof_certificate JSONB NOT NULL,
    
    -- Signature
    verifier_id TEXT NOT NULL,
    verifier_signature TEXT NOT NULL,
    signature_algorithm TEXT NOT NULL DEFAULT 'ed25519',
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp_authority TEXT,  -- RFC 3161 TSA URL if used
    timestamp_token TEXT,      -- RFC 3161 response if used
    
    -- Immutability flag (always TRUE, for clarity)
    immutable BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Indexes for fast lookup
    CONSTRAINT ck_immutable CHECK (immutable = TRUE)
);

-- Enforce append-only via trigger
CREATE OR REPLACE FUNCTION prevent_ledger_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Ledger entries are immutable. Updates and deletes are forbidden.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_ledger_immutable
    BEFORE UPDATE OR DELETE ON verification_ledger
    FOR EACH ROW EXECUTE FUNCTION prevent_ledger_modification();

-- Indexes
CREATE INDEX ix_ledger_sequence ON verification_ledger (sequence_number);
CREATE INDEX ix_ledger_claim_id ON verification_ledger ((proof_certificate->>'claim_id'));
CREATE INDEX ix_ledger_created_at ON verification_ledger (created_at);
```

### Proof Certificate JSON Schema

```json
{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "claim", "proof", "chain"],
    "properties": {
        "version": { "const": "1.0" },
        "claim": {
            "type": "object",
            "properties": {
                "id": { "type": "string", "pattern": "^REQ-[0-9]+$" },
                "text": { "type": "string" },
                "formal": { "type": "string" }
            }
        },
        "proof": {
            "type": "object",
            "properties": {
                "solver": { "enum": ["z3", "cvc5"] },
                "solver_version": { "type": "string" },
                "verification_time_ms": { "type": "integer" },
                "result": { "enum": ["verified", "failed", "timeout"] },
                "vcs_discharged": { "type": "integer" },
                "vcs_total": { "type": "integer" },
                "counterexample": { "type": ["object", "null"] }
            }
        },
        "chain": {
            "type": "object",
            "properties": {
                "previous_hash": { "type": "string" },
                "entry_hash": { "type": "string" },
                "sequence": { "type": "integer" }
            }
        }
    }
}
```

---

## 4. API Endpoints

### POST /api/v1/trust/submit-proof

**Request:**
```json
{
    "claim_id": "REQ-101",
    "verification_result": { ... },
    "dafny_output": "string"
}
```

**Response:**
```json
{
    "entry_id": "uuid",
    "sequence_number": 1042,
    "entry_hash": "7f3a...",
    "certificate_url": "/api/v1/trust/certificate/1042"
}
```

### GET /api/v1/trust/certificate/{sequence}

**Response:**
```json
{
    "proof_certificate": { ... },
    "chain": {
        "previous": { "sequence": 1041, "hash": "..." },
        "next": { "sequence": 1043, "hash": "..." }
    },
    "verification": {
        "signature_valid": true,
        "chain_valid": true
    }
}
```

### GET /api/v1/trust/audit

**Query Params:** `claim_id`, `start_date`, `end_date`, `limit`

**Response:**
```json
{
    "entries": [ ... ],
    "total": 1042,
    "chain_integrity": "verified"
}
```

---

## 5. Implementation Files

### New Files

| File | Purpose |
|------|---------|
| `core/trust_registry.py` | Ledger append, chain validation |
| `core/proof_certificate.py` | Certificate creation, signing |
| `core/crypto_signer.py` | Ed25519 signing/verification |
| `api/endpoints/trust.py` | Trust registry API endpoints |
| `tests/test_trust_registry.py` | Append-only tests, chain tests |

### Alembic Migration

```python
# migrations/versions/XXX_create_trust_registry.py
def upgrade():
    op.create_table('verification_ledger', ...)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_ledger_modification() ...
        CREATE TRIGGER tr_ledger_immutable ...
    """)

def downgrade():
    # In production, this should NEVER be called
    raise Exception("Trust Registry cannot be downgraded - data loss forbidden")
```

---

## 6. Verification Plan

### Automated Tests
1. Append entry, verify hash computation
2. Append 100 entries, verify chain integrity
3. Attempt UPDATE via SQL injection - verify blocked
4. Attempt DELETE via ORM - verify blocked
5. Verify signature on retrieved certificate

### Security Tests
1. Tamper with one entry, run integrity check - must fail
2. Skip sequence number, verify rejection
3. Submit with invalid signature, verify rejection

### Load Tests
1. Append 10,000 entries, measure throughput
2. Verify chain of 10,000 entries, measure time
3. Concurrent appends (10 writers), verify serialization

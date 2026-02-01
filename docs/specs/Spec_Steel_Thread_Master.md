# Steel Thread Master Specification

> **Priority:** P0 - MASTER SPEC - Takes precedence over all other specs  
> **Version:** 1.0  
> **Last Updated:** 2026-02-01  
> **Status:** ACTIVE

---

## 0. Executive Summary

This specification defines the **Steel Thread**: a single, unbroken execution path from user action to verified result. All other specifications are subordinate to this document.

**The Principle:** Correctness by Construction. The system enforces architecture, not humans.

---

## 1. The End-to-End Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend (Canvas)
    participant API as Backend (FastAPI)
    participant BG as BlueprintService
    participant GH as GitHub API
    participant VE as Verifier (Dafny)
    participant TR as Trust Registry

    User->>UI: Click "Initialize Blueprint"
    UI->>API: POST /api/v1/blueprints/initialize
    API->>BG: initialize_repository()
    BG->>GH: Push genesis files (blueprint.yaml, kernel/, shell/)
    GH-->>BG: Commit SHA
    BG->>API: Return blueprint_id
    API-->>UI: Blueprint created
    
    User->>UI: Write Claim (English spec)
    UI->>API: POST /api/v1/claims
    API->>VE: Generate VCs from Claim
    VE-->>API: VCs + Dafny code
    
    User->>UI: Click "Verify"
    UI->>API: POST /api/v1/verify/run
    API->>VE: Execute Dafny
    VE-->>API: Proof result
    API->>TR: Append to ledger
    TR-->>API: Proof certificate
    API-->>UI: Display verified badge
    
    User->>UI: Click "Commit to GitHub"
    UI->>API: POST /api/v1/github/commit
    API->>GH: Ghost Commit (verified files)
    GH-->>API: Commit + optional PR
    API-->>UI: Success + GitHub URL
```

---

## 2. The Trusted Kernel Architecture

Every InspecThor-managed repository must follow this structure. The system enforces this, not the user.

### 2.1 Repository Layout

```
repository/
├── blueprint.yaml          # THE LAW - Immutable manifest
├── claims/                  # Human-written specifications
│   └── *.nd                 # Natural Dafny (English + formal hints)
├── kernel/                  # Formally Verified Zone (Dafny only)
│   ├── Main.dfy             # Entry point - all logic here
│   ├── Prelude.dfy          # Domain types + invariants
│   └── *.dfy                # Additional modules
├── shell/                   # Unverified Zone (Python/TypeScript)
│   ├── main.py              # Entry point - I/O only
│   └── adapters/            # External integrations
├── generated/               # AUTO-GENERATED - Never edit
│   ├── contracts.dfy        # VCs from claims
│   └── proofs/              # Proof certificates
└── .inspecthor/             # System metadata
    ├── config.yaml          # Local settings
    └── cache/               # VC cache
```

### 2.2 The Manifest (blueprint.yaml)

```yaml
# blueprint.yaml - THE LAW
version: "1.0"
name: "Payment Processing System"
domain: "banking"  # banking | healthcare | authentication | custom

invariants:
  - "Balance can never be negative"
  - "Total system money is conserved"

claims:
  - path: "claims/transfer.nd"
    id: "REQ-101"
    status: "verified"  # unverified | verified | failed

kernel:
  entry: "kernel/Main.dfy"
  prelude: "preludes/banking"  # From InspecThor prelude library

shell:
  entry: "shell/main.py"
  runtime: "python3.11"

verification:
  solver: "z3"
  timeout_seconds: 120
  last_verified: "2026-02-01T10:00:00Z"
  proof_certificate: "generated/proofs/latest.json"
```

### 2.3 The Genesis Event

When a user initializes a Blueprint, InspecThor pushes the following files:

```python
GENESIS_FILES = {
    "blueprint.yaml": """version: "1.0"
name: "{blueprint_name}"
domain: "custom"
invariants: []
claims: []
kernel:
  entry: "kernel/Main.dfy"
shell:
  entry: "shell/main.py"
verification:
  solver: "z3"
  timeout_seconds: 120
""",
    "kernel/Main.dfy": """// InspecThor Kernel - Formally Verified Zone
module Kernel {
    // All business logic goes here
    // This code is verified by Dafny
    
    method Init() 
        ensures true  // Replace with actual postconditions
    {
        // Entry point
    }
}
""",
    "shell/main.py": """#!/usr/bin/env python3
\"\"\"
InspecThor Shell - Unverified I/O Zone

This layer handles:
- HTTP requests/responses
- Database operations  
- External API calls
- File I/O

It MUST NOT contain business logic.
Business logic belongs in kernel/
\"\"\"

if __name__ == "__main__":
    # Import and call kernel methods via FFI bridge
    pass
""",
    "claims/.gitkeep": "",
    "generated/.gitkeep": "",
    ".inspecthor/config.yaml": """# Local configuration
cache_enabled: true
auto_verify: false
"""
}
```

---

## 3. Implementation Strategy: Phased Approach

### Phase 0: Steel Thread MVP (THIS SPRINT)
**Goal:** One complete flow from UI to GitHub commit with verification.

| Component | Action | Status |
|-----------|--------|--------|
| `BlueprintService.initialize_repository()` | Implement genesis push | TO DO |
| UI: "Initialize Blueprint" button | Add to header | TO DO |
| API: `POST /api/v1/blueprints/initialize` | New endpoint | TO DO |
| Verification: Run existing Dafny flow | Already works | DONE |
| Trust: Store result in `proof_receipts` | Already works | DONE |
| Commit: Use `GhostCommitService` | Already implemented | DONE |

### Phase 1: Foundation (From existing spec)
- Rename Project → Blueprint (after Phase 0 validates flow)
- Database migration with backward compat

### Phase 2: The Bridge (From existing spec)
- VC Generator (deterministic, not LLM)
- Claim Parser
- Enhanced Dafny integration

### Phase 3: The Ledger (From existing spec)
- Trust Registry with chain integrity
- Proof certificates
- Immutability enforcement

---

## 4. API Contracts

### 4.1 Initialize Blueprint Repository

**Endpoint:** `POST /api/v1/blueprints/initialize`

**Request:**
```json
{
    "name": "Payment Processing",
    "repository_url": "https://github.com/user/repo",
    "installation_id": 12345,
    "domain": "banking",
    "initial_claim": "optional English spec"
}
```

**Response:**
```json
{
    "blueprint_id": "uuid",
    "repository_url": "https://github.com/user/repo",
    "commit_sha": "abc123...",
    "commit_url": "https://github.com/user/repo/commit/abc123",
    "files_created": [
        "blueprint.yaml",
        "kernel/Main.dfy",
        "shell/main.py"
    ],
    "next_steps": [
        "Add a claim in claims/ directory",
        "Run verification to generate contracts"
    ]
}
```

### 4.2 Create Claim

**Endpoint:** `POST /api/v1/blueprints/{id}/claims`

**Request:**
```json
{
    "claim_id": "REQ-101",
    "title": "Transfer Funds",
    "content": "## Preconditions\n- Balance >= amount\n\n## Postconditions\n- Sender balance decreases"
}
```

### 4.3 Verify and Commit

**Endpoint:** `POST /api/v1/blueprints/{id}/verify-and-commit`

**Request:**
```json
{
    "claims": ["REQ-101", "REQ-102"],
    "commit_message": "Verified transfer logic"
}
```

**Response:**
```json
{
    "verification": {
        "passed": true,
        "vcs_total": 4,
        "vcs_discharged": 4,
        "proof_certificate_id": "uuid"
    },
    "commit": {
        "sha": "def456...",
        "url": "https://github.com/user/repo/commit/def456"
    }
}
```

---

## 5. Implementation Files

### New Files (Phase 0)

| File | Purpose |
|------|---------|
| `api/services/blueprint_genesis.py` | Genesis event implementation |
| `api/endpoints/blueprints_v1.py` | New v1 API endpoints |
| `assets/genesis/` | Template files for repository init |

### Modified Files (Phase 0)

| File | Changes |
|------|---------|
| `api/services/project_service.py` | Add `initialize_repository()` method |
| `api/main.py` | Add v1 blueprints router |
| Frontend: `header.tsx` | Add "Initialize Blueprint" button |
| Frontend: Add `BlueprintInitModal` | Repository selection UI |

---

## 6. Extension Points (Future-Proofing)

### 6.1 Prelude Library
- Domain preludes stored in `assets/preludes/`
- Referenced by `blueprint.yaml#kernel.prelude`
- Genesis can inject appropriate prelude based on domain

### 6.2 Multi-Language Kernel
- Currently: Dafny only
- Future: Could support Coq, Lean, Z3 SMT-LIB
- Abstraction: `VerificationEngine` interface

### 6.3 CI/CD Integration
- GitHub Actions workflow generated in genesis
- Webhook triggers verification on PR
- Block merge if verification fails

### 6.4 Proof Certificate Format
- Currently: JSON stored in DB
- Future: W3C Verifiable Credentials format
- Blockchain anchoring (optional enterprise feature)

---

## 7. Error Handling

### 7.1 Genesis Failures

| Error | Handling |
|-------|----------|
| Repo not empty | Warn user, offer to overwrite or abort |
| No installation token | Prompt to install GitHub App |
| Permission denied | Check app permissions |
| Network failure | Retry with backoff |

### 7.2 Verification Failures

| Error | Handling |
|-------|----------|
| Dafny timeout | Suggest simplifying claim |
| Z3 memory limit | Increase limits or split claims |
| Syntax error in VC | Show line number, offer fix suggestions |

---

## 8. Migration Path

### From Current State to Steel Thread

1. **Backward Compatibility:** 
   - Existing `/api/projects/*` endpoints continue to work
   - New `/api/v1/blueprints/*` endpoints are additive

2. **Feature Flags:**
   - `ENABLE_BLUEPRINT_GENESIS=true` for early adopters
   - `ENABLE_TRUST_REGISTRY=false` until Phase 3

3. **Database:**
   - `projects` table remains until Phase 1 migration
   - `blueprints` table created alongside
   - Migration copies data, doesn't delete

---

## 9. Success Criteria (Phase 0)

- [ ] User can click "Initialize Blueprint" in UI
- [ ] System pushes genesis files to empty GitHub repo
- [ ] User sees commit appear in GitHub within 5 seconds
- [ ] User can add a claim in the IDE
- [ ] System generates VCs from claim
- [ ] User can run verification
- [ ] System stores proof in database
- [ ] User can commit verified code to GitHub
- [ ] Complete flow takes < 60 seconds

---

## 10. Non-Goals (Phase 0)

- ❌ Rename Project → Blueprint (Phase 1)
- ❌ Deterministic VC generator (Phase 2)
- ❌ Immutable Trust Registry (Phase 3)
- ❌ UI Canvas redesign (Phase 2-3)
- ❌ Multi-repo support
- ❌ Team collaboration features

---

## Appendix A: Existing Infrastructure Audit

### What We Have (Ready to Use)

| Component | Location | Status |
|-----------|----------|--------|
| GitHub App integration | `api/github/` | ✅ Complete |
| Tree/commit creation | `api/github/api_client.py` | ✅ Complete |
| Ghost commit service | `api/github/commits.py` | ✅ Complete |
| Dafny verification | `verifier/runner.py` | ✅ Complete |
| Proof receipt storage | `api/database.py` | ✅ Complete |
| Project CRUD | `api/services/project_service.py` | ✅ Complete |
| File CRUD | `api/files.py` | ✅ Complete |

### What We Need to Build

| Component | Description | Effort |
|-----------|-------------|--------|
| Genesis push logic | Use existing `create_tree()`, `create_commit()` | 2-3 hours |
| Blueprint init endpoint | New FastAPI route | 1 hour |
| UI init button | Frontend modal + API call | 2-3 hours |
| Template files | YAML + Dafny stubs | 1 hour |

**Total Phase 0 Effort:** ~1 day of focused work

---

## Appendix B: Commands Reference

### Local Development

```bash
# Start backend
cd inspecthor-ide-backend
uvicorn api.main:app --reload --port 8000

# Start frontend
cd inspecthor-ide-frontend
pnpm dev

# Test genesis locally (after implementation)
curl -X POST http://localhost:8000/api/v1/blueprints/initialize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"name": "test", "repository_url": "https://github.com/user/test-repo", "installation_id": 12345}'
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-01 | Initial Steel Thread specification |

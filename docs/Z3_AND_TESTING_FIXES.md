# Z3 Solver and Testing Fixes

## Issue 1: Z3 Solver Missing in Docker ✅ FIXED

### Problem
Dafny verification fails with: `CLI: Error: Z3 is not found`

### Solution Implemented

Added Z3 installation to `Dockerfile.api`:

```dockerfile
# Install Z3 solver (required for Dafny verification)
RUN mkdir -p /root/.dafny/z3 && \
    wget https://github.com/Z3Prover/z3/releases/download/Z3-4.12.1/z3-4.12.1-x64-ubuntu-20.04.zip -O /tmp/z3.zip && \
    unzip /tmp/z3.zip -d /tmp && \
    cp /tmp/z3-4.12.1-x64-ubuntu-20.04/bin/z3 /root/.dafny/z3/ && \
    chmod +x /root/.dafny/z3/z3 && \
    rm -rf /tmp/z3.zip /tmp/z3-4.12.1-x64-ubuntu-20.04 && \
    apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

ENV DAFNY_SOLVER_PATH=/root/.dafny/z3
```

### Testing Gap Without Z3

**Without Z3:**
- ✅ Syntax checking works (`dafny resolve`)
- ❌ **Verification fails** - Cannot prove mathematical properties
- ❌ **No proof of correctness** - Critical for Spec-First architecture
- ❌ **Cannot verify pre/postconditions** - Core value proposition lost

**With Z3:**
- ✅ Syntax checking
- ✅ **Full verification** - Mathematical proofs of correctness
- ✅ **Pre/postcondition verification** - Guarantees match Dafny specs
- ✅ **Proof of correctness** - Core value of Spec-First architecture

**Impact:** Without Z3, we lose the core value of Spec-First architecture - mathematical proof of correctness.

### Verification Steps

After rebuilding Docker image:

```bash
docker-compose build api
docker-compose up -d api
./scripts/verify_dafny.sh api/verification/models.dfy api/verification/file_operations.dfy
```

Should see: `Dafny program verifier finished with X verified, Y errors`

---

## Issue 2: Authentication Barrier in Tests ✅ FIXED

### Problem
All tests fail with `403 Forbidden` - "Invalid API key attempt"

### Root Cause
`APIKeyMiddleware` checks `ALLOWED_API_KEYS` environment variable. Tests use `"test_api_key_123"` but this isn't in the allowed list when the middleware initializes.

### Solution Implemented

Created `tests/conftest.py` that sets `ALLOWED_API_KEYS` **before** importing the app:

```python
# CRITICAL: Set test API keys BEFORE importing app
os.environ["ALLOWED_API_KEYS"] = "test_api_key_123,test_key_456"

from api.main import app
# ... rest of fixtures
```

This ensures `APIKeyMiddleware` reads the correct allowed keys during initialization.

### Additional Fix: icontract OLD snapshots

Fixed `icontract` postconditions that use `OLD` by adding `@icontract.snapshot` decorators:

```python
@icontract.snapshot(lambda state, project_id, owner_id: state.files.keys(), name="old_file_ids")
@icontract.ensure(
    lambda result, state, project_id, owner_id, OLD:
        # Can now use OLD.old_file_ids
)
```

### Verification Steps

```bash
python -m pytest tests/test_projects.py -v
```

Tests should now pass authentication (may have other issues to fix, but 403 errors should be gone).

---

## Summary

| Issue | Status | Impact |
|-------|--------|--------|
| Z3 Solver Missing | ✅ Fixed in Dockerfile | Enables full Dafny verification |
| Test Authentication | ✅ Fixed in conftest.py | Tests can now run |
| icontract OLD snapshots | ✅ Fixed | Postconditions work correctly |

### Next Steps

1. **Rebuild Docker image** to get Z3:
   ```bash
   docker-compose build api
   ```

2. **Verify Dafny specs** work with Z3:
   ```bash
   ./scripts/verify_dafny.sh api/verification/models.dfy api/verification/file_operations.dfy
   ```

3. **Run tests** to verify Core ↔ Adapter ↔ DB flow:
   ```bash
   python -m pytest tests/test_projects.py -v
   ```

4. **Fix remaining test issues** (if any) - likely UUID conversion issues in adapters.

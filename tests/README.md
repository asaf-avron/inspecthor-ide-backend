# Testing Strategy

## Test Coverage

### 1. Integration Tests (`tests/test_*.py`)
**Purpose:** Test the full HTTP stack to catch:
- Missing imports
- Import errors
- Dependency injection failures
- Endpoint routing issues

**Files:**
- `test_projects.py` - Project management endpoints
- `test_files.py` - File management endpoints (NEW)

**Why Critical:** These tests would have caught the `adapters` import error immediately.

### 2. Oracle Tests (`tests/oracle/test_core_oracle.py`)
**Purpose:** Verify Core logic matches Dafny specifications
**Status:** Requires Dafny test vectors (currently skipped)

## Running Tests

```bash
# Run all tests
pytest tests/

# Run integration tests only
pytest tests/test_*.py

# Run Oracle tests (if vectors exist)
pytest tests/oracle/

# Run with coverage
pytest --cov=api tests/
```

## CI/CD Recommendations

### Missing Checks (Should Add):

1. **Pre-commit Hook:**
   ```bash
   # Run tests before commit
   pytest tests/test_files.py tests/test_projects.py
   ```

2. **GitHub Actions:**
   ```yaml
   - name: Run Integration Tests
     run: pytest tests/test_*.py -v
   ```

3. **Type Checking:**
   ```bash
   # Install mypy
   pip install mypy
   # Check for undefined names
   mypy api/ --check-untyped-defs
   ```

4. **Linting:**
   ```bash
   # Install pylint
   pip install pylint
   # Check for undefined variables
   pylint api/ --errors-only
   ```

## What These Tests Catch

✅ **Integration Tests Catch:**
- Missing imports (`NameError: name 'adapters' is not defined`)
- Import path errors
- Dependency injection failures
- HTTP routing issues
- Response format errors

❌ **What They Don't Catch:**
- Business logic errors (use Oracle tests)
- Performance issues
- Security vulnerabilities (use security tests)

## Test Maintenance

- **Add integration tests for every new endpoint**
- **Run tests before committing**
- **Keep tests simple - they're smoke tests, not unit tests**
- **Update tests when API changes**

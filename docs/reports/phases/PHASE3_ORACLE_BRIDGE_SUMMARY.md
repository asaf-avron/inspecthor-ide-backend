# Phase 3: Oracle Bridge Implementation - Summary

**Date:** January 28, 2026  
**Phase:** Phase 3.1 - The Oracle Bridge  
**Status:** ✅ COMPLETE

## Overview

Implemented the strict Oracle translator (`state_from_json()`) that converts Dafny JSON test vectors to Python `SystemState` objects. This function enforces zero ambiguity - it fails immediately if the JSON structure does not perfectly match the expected schema.

## Implementation Details

### `state_from_json()` Function

**Location:** `tests/oracle/test_core_oracle.py` (lines 44-249)

**Key Features:**
1. **Zero Ambiguity:** Raises `ValueError` on any missing or unexpected fields
2. **Type Strictness:** Validates all types (dicts, lists, strings, ints, enums)
3. **Ownership Mapping:** Strictly maps Dafny `Owner` union type:
   - `{"tag": "Authenticated", "userId": "..."}` → `Owner.authenticated(user_id)`
   - `{"tag": "Anonymous", "apiKeyHash": "..."}` → `Owner.anonymous(api_key_hash)`
4. **Integrity Checks:**
   - Validates `projectId` matches dictionary key
   - Validates `fileId` matches dictionary key
   - Validates `sizeBytes` matches content length
   - Validates no unexpected fields at any level
5. **State Validation:** Calls `SystemState.validate()` after construction to ensure invariants

**JSON Structure Expected:**
```json
{
  "projects": {
    "p1": {
      "projectId": "p1",
      "name": "...",
      "description": "...",
      "owner": {
        "tag": "Authenticated" | "Anonymous",
        "userId": "..." (if Authenticated),
        "apiKeyHash": "..." (if Anonymous)
      },
      "fileIds": ["f1", "f2"]
    }
  },
  "files": {
    "f1": {
      "fileId": "f1",
      "projectId": "p1",
      "filename": "...",
      "content": "...",
      "fileType": "MD" | "DFY" | "UNIT",
      "sizeBytes": 123,
      "renamed": false
    }
  }
}
```

### Updated Test Methods

**1. `test_migrate_anonymous_projects()`**
- Loads `state_delta` from JSON using `state_from_json()`
- Calls `migration.migrate_anonymous_projects()`
- Verifies migration count matches expected
- Validates resulting state

**2. `test_save_file()`**
- Loads `state_delta` from JSON using `state_from_json()`
- Extracts SaveFile parameters from test case
- Calls `file_operations.save_file_core()`
- Verifies file creation and state validity
- Verifies error kinds match expected

**3. `test_delete_project_cascade()`**
- Loads `state_delta` from JSON using `state_from_json()`
- Extracts DeleteProject parameters
- Calls `project_management.delete_project_core()`
- Verifies cascade deletion of files
- Validates resulting state

## Architectural Compliance

### Zero Ambiguity Rule ✅
- Function raises `ValueError` on missing fields
- Function raises `ValueError` on unexpected fields
- No default values or fuzzy matching
- All type conversions are explicit and validated

### Type Strictness ✅
- IDs validated as strings
- Sets converted from lists with type checking
- Enums mapped strictly (MD/DFY/UNIT only)
- Owner tag validated (Authenticated/Anonymous only)

### Ownership Mapping ✅
- Dafny `Owner` union type correctly mapped:
  - `Authenticated(userId)` → `Owner.authenticated(user_id)`
  - `Anonymous(apiKeyHash)` → `Owner.anonymous(api_key_hash)`
- Validates tag field exists
- Validates required fields for each tag type
- Rejects unknown tag values

## Test Results

**Current Status:**
- `test_state_validation()`: ✅ PASSES
- Oracle tests with test vectors: ⏸️ SKIPPED (test vector files not generated yet)

**Note:** The tests are properly structured to skip when test vector JSON files don't exist. Once Dafny test vectors are generated, the tests will automatically run and verify Python Core == Dafny Spec.

## Files Modified

- `tests/oracle/test_core_oracle.py`:
  - Implemented `state_from_json()` (206 lines)
  - Updated `test_migrate_anonymous_projects()` to use translator
  - Updated `test_save_file()` to use translator
  - Updated `test_delete_project_cascade()` to use translator

## Next Steps

1. **Generate Test Vectors:** Run Dafny `GenerateTests()` methods to create JSON test vectors
2. **Run Oracle Tests:** Execute `pytest tests/oracle/` to verify Python Core matches Dafny Spec
3. **Phase 2:** Proceed with Frontend State Decomposition once Oracle verification is complete

## Verification

The implementation is ready for Oracle verification. When test vectors are generated from Dafny, the tests will:
1. Load JSON test vectors
2. Convert to Python `SystemState` via `state_from_json()`
3. Call Python Core functions
4. Verify results match Dafny expected outputs
5. Prove: **Python Core == Dafny Spec**

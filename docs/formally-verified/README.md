# Formally Verified Components

This directory documents the **only components** in Inspecthor that have Dafny-verified formal specifications. All specifications are verified in CI (`.github/workflows/verify-dafny.yml`).

## Verified Specifications

| Specification | Description | Status |
|--------------|-------------|--------|
| [`models.md`](models.md) | Core database model and state invariants | ✅ Fully Verified |
| [`file_operations.md`](file_operations.md) | File create, update, delete operations | ✅ Fully Verified |
| [`project_management.md`](project_management.md) | Project create and cascade delete | ✅ Fully Verified |
| [`project_migration.md`](project_migration.md) | Anonymous → authenticated project migration | ✅ Fully Verified |
| [`crypto_contract.md`](crypto_contract.md) | Token encryption/decryption (Fernet) | ✅ Fully Verified |
| [`spec_generation.md`](spec_generation.md) | LLM-based spec generation | ⚠️ Partial (requires expert) |
| [`traceability.md`](traceability.md) | Traceability link management | ⚠️ Partial (requires expert) |

## Verification Process

All `.dfy` specifications are located in [`api/verification/`](../../api/verification/). The verification service runs in Docker (no local Dafny/Z3 installation required) and is automatically verified on every push via GitHub Actions.

**Verification Service:** [`verifier/`](../../verifier/) - Isolated Docker container with Dafny and Z3 solver

## What Is NOT Formally Verified

Everything else in the codebase (API endpoints, frontend, database migrations, GitHub integration, etc.) is **not** formally verified. See [`../README.md`](../README.md) for the complete documentation structure.

## Implementation Mapping

Each specification has a corresponding Python implementation:
- `models.dfy` → `api/core/models.py`
- `file_operations.dfy` → `api/core/file_operations.py`
- `project_management.dfy` → `api/core/project_management.py`
- `project_migration.dfy` → `api/core/migration.py`
- `crypto_contract.dfy` → `core/security/crypto.py`
- `spec_generation.dfy` → `api/services/spec_generator.py`
- `traceability.dfy` → `api/deconstruct.py`

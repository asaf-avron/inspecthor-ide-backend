# DatabaseModel Specification

**Dafny Spec:** [`api/verification/models.dfy`](../../api/verification/models.dfy)  
**Python Implementation:** [`api/core/models.py`](../../api/core/models.py)

## Purpose

Defines the core data structures and state invariants for the Guardian Gateway database model. This specification establishes the foundation for all other verified components.

## Key Types

- **`UUID`**: String-based unique identifier
- **`Content`**: String representing file content
- **`FileType`**: Enum (`MD`, `DFY`, `UNIT`)
- **`Owner`**: Union type (`Authenticated(userId)` | `Anonymous(apiKeyHash)`)
- **`File`**: File metadata (id, projectId, filename, content, type, size, renamed flag)
- **`Project`**: Project metadata (id, name, description, owner, fileIds set)
- **`SystemState`**: Complete system snapshot (projects map, files map)

## Core Invariant

**`ValidState(s: SystemState)`** ensures:
1. **Relational Integrity**: Every file referenced by a project exists
2. **Reverse Integrity**: Every file points back to its project
3. **Size Integrity**: File metadata size matches content length

## Verification Status

✅ Verified with Dafny compiler in CI (`.github/workflows/verify-dafny.yml`)

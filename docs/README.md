# Inspecthor Documentation

## Overview

Inspecthor is the backend for Proof-Driven Development. It turns English requirements into Dafny contracts using Google Gemini, and verifies implementations against them with Dafny and Z3. The IDE is in [inspecthor-ide-frontend](https://github.com/asaf-avron/inspecthor-ide-frontend).

---

## Formally Verified Components

**→ [`formally-verified/`](formally-verified/)** - The only components with Dafny-verified formal specifications.

This directory contains documentation for the 7 formally verified specifications:
- Database model and state invariants
- File operations (create, update, delete)
- Project management (create, cascade delete)
- Project migration (anonymous → authenticated)
- Cryptographic operations (token encryption)
- Spec generation (partial, requires expert)
- Traceability links (partial, requires expert)

All specifications are verified in CI via Docker-based verification service (no local Dafny/Z3 installation required).

---

## Design & Implementation (Not Formally Verified)

The following documentation covers components that are **not** formally verified:

### Core Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Consolidated architecture, design philosophy, security, and roadmap
- **[SECURITY.md](SECURITY.md)** - Security practices, authentication, and deployment

### Architecture
The `architecture/` subfolder has been consolidated into `ARCHITECTURE.md`. Contents include:
- High-level system design
- Proof-Driven Development methodology
- Security and integrity (Immutable Contract Policy)
- Production vision (Three Pillars)
- Specification template appendix

### Instructions & Setup
- **[instructions/](instructions/)** - Setup instructions
  - [`GITHUB_APP_SETUP.md`](instructions/GITHUB_APP_SETUP.md) - GitHub App setup
  - [`GITHUB_APP_LOCALHOST_SETUP.md`](instructions/GITHUB_APP_LOCALHOST_SETUP.md) - GitHub App setup for localhost

### Specifications (Implementation Specs)
- **[specs/](specs/)** - Feature specifications for the roadmap
  - **[`Spec_Steel_Thread_Master.md`](specs/Spec_Steel_Thread_Master.md)** - **MASTER SPEC** - Takes precedence over all others
  - [`Spec_Blueprint_Nomenclature_Refactor.md`](specs/Spec_Blueprint_Nomenclature_Refactor.md) - Phase 1: Project→Blueprint rename
  - [`Spec_Verification_Condition_Generator.md`](specs/Spec_Verification_Condition_Generator.md) - Phase 2: Deterministic VC generation
  - [`Spec_Trust_Registry.md`](specs/Spec_Trust_Registry.md) - Phase 3: Immutable proof ledger
  - [`Spec_Architects_Canvas_UI.md`](specs/Spec_Architects_Canvas_UI.md) - Phase 2-3: Split-view Blueprint/Proof UI
  - [`Spec_Dafny_Domain_Preludes.md`](specs/Spec_Dafny_Domain_Preludes.md) - Phase 2: Banking/Healthcare/Auth modules

### Reference Materials
- **[knowledge/](knowledge/)** - Reference materials
  - [`dafny_ref.md`](knowledge/dafny_ref.md) - Dafny reference

---

## Quick Links

### For Developers
- [Formally Verified Components](formally-verified/) - Dafny-verified specifications
- [API Endpoints](ARCHITECTURE.md#api-layer) - API documentation
- [Security Setup](SECURITY.md#api-authentication) - Authentication and security
- [Local Development](../README.md#quickstart) - Setup guide

### For Deployment
- [Production Checklist](SECURITY.md#production-deployment-checklist) - Deployment guide
- [Environment Variables](SECURITY.md#environment-variables) - Configuration
- [Docker Setup](../README.md#2-run) - Docker deployment

## Core Modules (Not Formally Verified)

### `core/workflow.py`
- Triage: Classifies input documents
- Structuring: Organizes requirements

### `core/auditor.py`
- Analyzes specifications with Gemini
- Generates Dafny skeleton code
- Identifies gaps and ambiguities

### `core/gateway.py`
- Interfaces with Dafny verifier
- Executes verification checks

### `core/parser.py`
- Parses Dafny contracts
- Extracts requirements

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (public) |
| `/api/generate/spec` | POST | Generate Dafny from English |
| `/api/assistant/chat` | POST | AI debugging assistant |
| `/docs` | GET | Swagger API documentation |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed API contracts.

## Getting Help

- **Issues**: GitHub Issues
- **Security**: See [SECURITY.md](SECURITY.md#contact)
- **API Docs**: http://localhost:8000/docs (when running)

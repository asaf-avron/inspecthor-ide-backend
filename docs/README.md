# Guardian Gateway Documentation

## Overview

Guardian Gateway is a backend API service for formal specification verification. It transforms English requirements into verified Dafny specifications using Google Gemini AI.

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
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, components, and API contracts
- **[SECURITY.md](SECURITY.md)** - Security practices, authentication, and deployment

### Architecture & Design
- **[architecture/](architecture/)** - High-level design documents
  - `Guardian_02_Architecture_HLD.md` - Architecture high-level design
  - `Guardian_03_Methodology_Dafny.md` - Dafny methodology
  - `Guardian_09_Security_Integrity.md` - Security and integrity
  - `Guardian_10_Production_Roadmap.md` - Production roadmap

### Development & Integration
- **[development/](development/)** - Development guides and integration docs
  - `UI_API_MAPPING.md` - UI functionality to API mapping
  - `UI_BACKEND_INTEGRATION_PLAN.md` - UI/backend integration plan

### Instructions & Setup
- **[instructions/](instructions/)** - Setup and workflow instructions
  - `Cursor_Build_Lens.md` - Cursor build lens guide
  - `Cursor_Workflow.md` - Cursor workflow guide
  - `Spec_Process_Guide.md` - Specification process guide
  - `GITHUB_APP_SETUP.md` - GitHub app setup
  - `GITHUB_APP_LOCALHOST_SETUP.md` - GitHub app localhost setup

### Specifications (Implementation Specs)
- **[specs/dev/](specs/dev/)** - Development specifications (not formally verified)
  - **[implemented/](specs/dev/implemented/)** - Implemented feature specs
  - `Dev_Spec_Deconstruct_To_Units.md` - Unit deconstruction spec
  - `Dev_Spec_File_Operations.md` - File operations spec
  - `Dev_Spec_Project_Management.md` - Project management spec

### Templates
- **[templates/](templates/)** - Specification templates
  - `Guardian_07_Spec_Template.md` - Specification template
  - `Template_Architects_Canvas.md` - Architect's canvas template

### Reference Materials
- **[knowledge/](knowledge/)** - Reference materials
  - `dafny_ref.md` - Dafny reference

---

## Quick Links

### For Developers
- [Formally Verified Components](formally-verified/) - Dafny-verified specifications
- [API Endpoints](ARCHITECTURE.md#api-contracts) - API documentation
- [Security Setup](SECURITY.md#api-authentication) - Authentication and security
- [Local Development](../README.md#quick-start-recommended) - Setup guide

### For Deployment
- [Production Checklist](SECURITY.md#production-deployment-checklist) - Deployment guide
- [Environment Variables](SECURITY.md#environment-variables) - Configuration
- [Docker Setup](../README.md#quick-start-docker) - Docker deployment

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

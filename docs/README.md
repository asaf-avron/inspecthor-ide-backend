# Guardian Gateway Documentation

## Overview

Guardian Gateway is a backend API service for formal specification verification. It transforms English requirements into verified Dafny specifications using Google Gemini AI.

## Documentation Structure

### Core Documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture, components, and API contracts
- **[SECURITY.md](./SECURITY.md)** - Security practices, authentication, and deployment

### Architecture & Design
- **[architecture/](./architecture/)** - High-level design documents
  - `Guardian_02_Architecture_HLD.md` - Architecture high-level design
  - `Guardian_03_Methodology_Dafny.md` - Dafny methodology
  - `Guardian_09_Security_Integrity.md` - Security and integrity
  - `Guardian_10_Production_Roadmap.md` - Production roadmap

### Reports
- **[reports/](./reports/)** - Project reports and summaries
  - **[phases/](./reports/phases/)** - Phase completion reports
    - `PHASE1_REFACTORING_SUMMARY.md` - Phase 1 refactoring summary
    - `PHASE1_STATIC_SHIELD_REPORT.md` - Phase 1 static shield report
    - `PHASE2_INTEGRATION_NET_REPORT.md` - Phase 2 integration report
    - `PHASE2.5_STABILIZATION_REPORT.md` - Phase 2.5 stabilization report
    - `PHASE3_ORACLE_BRIDGE_SUMMARY.md` - Phase 3 oracle bridge summary
  - **[analysis/](./reports/analysis/)** - Analysis reports
    - `TESTING_GAP_ANALYSIS.md` - Testing gap analysis
    - `PROJECT_STRUCTURE_ANALYSIS.md` - Project structure analysis
    - `SQLITE_COMPATIBILITY_ISSUES.md` - SQLite compatibility issues
  - **[verification/](./reports/verification/)** - Verification and defense reports
    - `DEFENSE_COMPLETE.md` - Defense in depth implementation report
    - `PRAGMATIC_SHIELD_REPORT.md` - Pragmatic shield report
    - `CACHE_VERIFICATION_REPORT.md` - Docker cache verification report
    - `VERIFICATION_STATUS.md` - Verification status
    - `VERIFICATION_STATE_REPORT.md` - Verification state report
    - `Z3_AND_TESTING_FIXES.md` - Z3 solver and testing fixes
  - `FORMAL_VERIFICATION_PLAN.md` - Formal verification plan
  - `IMPLEMENTATION_SUMMARY.md` - Implementation summary

### Development & Integration
- **[development/](./development/)** - Development guides and integration docs
  - `UI_API_MAPPING.md` - UI functionality to API mapping
  - `UI_BACKEND_INTEGRATION_PLAN.md` - UI/backend integration plan

### Instructions & Setup
- **[instructions/](./instructions/)** - Setup and workflow instructions
  - `Cursor_Build_Lens.md` - Cursor build lens guide
  - `Cursor_Workflow.md` - Cursor workflow guide
  - `Spec_Process_Guide.md` - Specification process guide
  - `GITHUB_APP_SETUP.md` - GitHub app setup
  - `GITHUB_APP_LOCALHOST_SETUP.md` - GitHub app localhost setup

### Experts & Specifications
- **[experts/](./experts/)** - Expert requirements and specifications
  - `EXPERT_REQUIREMENTS.md` - Expert requirements
  - `SAMPLE_SPECS_FOR_EXPERTS.md` - Sample specifications for experts
  - `architect/SPEC_FIRST_TRANSITION_PLAN.md` - Architect spec-first transition plan
  - `oracle/SPEC_FIRST_TRANSITION_PLAN.md` - Oracle spec-first transition plan

### Specifications
- **[specs/](./specs/)** - Development specifications
  - **[dev/](./specs/dev/)** - Development specs
    - **[implemented/](./specs/dev/implemented/)** - Implemented specs
    - **[archive/](./specs/dev/archive/)** - Archived specs
  - `Draft_01_Rewards_System.md` - Draft rewards system
  - `Gap_Analysis_Report.md` - Gap analysis report

### Templates
- **[templates/](./templates/)** - Specification templates
  - `Guardian_07_Spec_Template.md` - Specification template
  - `Template_Architects_Canvas.md` - Architect's canvas template

### Reference Materials
- **[knowledge/](./knowledge/)** - Reference materials
  - `dafny_ref.md` - Dafny reference

## Quick Links

### For Developers
- [API Endpoints](./ARCHITECTURE.md#api-contracts)
- [Security Setup](./SECURITY.md#api-authentication)
- [Local Development](../README.md#quick-start-recommended)

### For Deployment
- [Production Checklist](./SECURITY.md#production-deployment-checklist)
- [Environment Variables](./SECURITY.md#environment-variables)
- [Docker Setup](../README.md#quick-start-docker)

## Core Modules

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

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed API contracts.

## Getting Help

- **Issues**: GitHub Issues
- **Security**: See [SECURITY.md](./SECURITY.md#contact)
- **API Docs**: http://localhost:8000/docs (when running)

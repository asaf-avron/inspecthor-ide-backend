# Guardian Gateway Documentation

## Overview

Guardian Gateway is a backend API service for formal specification verification. It transforms English requirements into verified Dafny specifications using Google Gemini AI.

## Documentation Structure

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture, components, and API contracts
- **[SECURITY.md](./SECURITY.md)** - Security practices, authentication, and deployment
- **[API_IMPLEMENTATION_PLAN.md](./API_IMPLEMENTATION_PLAN.md)** - Detailed plan for implementing UI-required APIs
- **[architecture/](./architecture/)** - High-level design documents
- **[knowledge/](./knowledge/)** - Reference materials (Dafny, etc.)

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

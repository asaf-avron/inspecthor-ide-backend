# Guardian Gateway

**Backend API for Formal Specification Verification**

## Overview

Guardian Gateway is a backend API service that transforms English requirements into formally verified Dafny specifications using Google Gemini AI. The backend is fully Dockerized and includes an isolated verification service with Dafny and Z3 solver—no local installation required.

**Note:** The IDE frontend is in a separate repository (`v0-guardian-gateway-ide`). This repository contains only the backend API and verification services.

## Formally Verified Components

This project includes **7 formally verified Dafny specifications** verified in CI:

- **Database Model** - Core data structures and state invariants
- **File Operations** - Create, update, delete files
- **Project Management** - Create projects and cascade deletion
- **Project Migration** - Anonymous → authenticated project migration
- **Crypto Contract** - Token encryption/decryption (Fernet)
- **Spec Generation** - LLM-based spec generation (partial)
- **Traceability** - Traceability link management (partial)

See [`docs/formally-verified/`](docs/formally-verified/) for complete documentation. All specifications are verified automatically via Docker-based verification service (`.github/workflows/verify-dafny.yml`).

## Quick Start (Docker - Recommended)

The backend is fully Dockerized. No local Dafny or Z3 installation required.

### Prerequisites
- Docker and Docker Compose
- Google Gemini API key

### Setup

```bash
# Clone repository
git clone <repository-url>
cd guardian-gateway

# Create .env file
cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_api_key_here

# Build and run all services (API + Verifier + Database)
docker-compose up --build

# Access
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Verifier: http://localhost:8001 (internal only)
```

The Docker setup includes:
- **API Service** (`api/`) - FastAPI backend on port 8000
- **Verifier Service** (`verifier/`) - Isolated Dafny/Z3 verification service on port 8001
- **PostgreSQL Database** - Optional (defaults to SQLite)

### Development Mode

```bash
# Run backend API locally (still uses Docker verifier)
python -m api.main

# Or use convenience script
./dev-backend.sh
```

**Note:** Even in local development, the verification service runs in Docker—no local Dafny/Z3 installation needed.

## Project Structure

```
guardian-gateway/
├── api/                       # FastAPI backend
│   ├── main.py               # API entry point
│   ├── core/                 # Core business logic
│   │   ├── models.py         # Database models (verified)
│   │   ├── file_operations.py # File ops (verified)
│   │   ├── project_management.py # Project ops (verified)
│   │   └── migration.py      # Migration (verified)
│   ├── services/             # Service layer
│   ├── verification/         # Dafny specifications (.dfy)
│   │   ├── models.dfy
│   │   ├── file_operations.dfy
│   │   ├── project_management.dfy
│   │   ├── project_migration.dfy
│   │   ├── crypto_contract.dfy
│   │   ├── spec_generation.dfy
│   │   └── traceability.dfy
│   └── requirements.txt
├── core/                     # Core modules (not verified)
│   ├── workflow.py          # Triage and structuring
│   ├── auditor.py            # Spec analysis with Gemini
│   ├── gateway.py            # Dafny verification interface
│   └── security/
│       └── crypto.py         # Crypto ops (verified)
├── verifier/                 # Verification service (Docker)
│   ├── Dockerfile            # Includes Dafny + Z3
│   ├── main.py               # FastAPI verifier service
│   └── runner.py             # Dafny execution
├── docs/                     # Documentation
│   ├── formally-verified/    # Verified component docs
│   ├── ARCHITECTURE.md       # System architecture
│   └── SECURITY.md           # Security practices
├── tests/                    # Test suite
├── scripts/                  # Utility scripts
├── docker-compose.yml        # Docker orchestration
└── Dockerfile.api            # API service Dockerfile
```

## Architecture

### Backend (Python + FastAPI)
- **REST API**: FastAPI server on port 8000
- **Core Modules**: 
  - `core/workflow.py`: Triage and structuring
  - `core/auditor.py`: Spec analysis with Gemini
  - `core/gateway.py`: Dafny verification interface
- **API Documentation**: Automatic Swagger/ReDoc generation

### Verification Service (Docker)
- **Isolated Container**: Dafny and Z3 solver pre-installed
- **No Local Installation**: All verification runs in Docker
- **Network Isolation**: Verifier only accessible internally
- **Stateless**: No credentials, no database access

### Database
- **SQLite** (default): File-based, no setup required
- **PostgreSQL** (optional): Configure via `DATABASE_URL` in docker-compose.yml

## Features

### Formally Verified (Dafny)
- ✅ Database model with relational integrity invariants
- ✅ File operations (create, update, delete)
- ✅ Project management with cascade deletion
- ✅ Anonymous → authenticated project migration
- ✅ Cryptographic token encryption/decryption

### Not Formally Verified
- API endpoints and routing
- GitHub integration
- LLM-based spec generation (partial spec exists)
- Traceability links (partial spec exists)
- Frontend IDE (separate repository)

## API Endpoints

- `GET /api/health` - Health check (public)
- `POST /api/generate/spec` - Generate Dafny from English (authenticated)
- `POST /api/assistant/chat` - AI debugging assistant (authenticated)

See full API documentation at http://localhost:8000/docs

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_files.py
```

### Verifying Dafny Specs

```bash
# Verify all specs (uses Docker verifier)
./scripts/verify_dafny.sh api/verification/models.dfy api/verification/file_operations.dfy

# Or verify via Docker directly
docker-compose exec verifier dafny verify api/verification/models.dfy
```

### Code Structure

- **Formally Verified**: `api/core/models.py`, `api/core/file_operations.py`, `api/core/project_management.py`, `api/core/migration.py`, `core/security/crypto.py`
- **Not Verified**: All other Python modules (API routes, services, GitHub integration, etc.)

## Documentation

- **[Formally Verified Components](docs/formally-verified/)** - Dafny-verified specifications
- **[Architecture](docs/ARCHITECTURE.md)** - System design and API contracts
- **[Security](docs/SECURITY.md)** - Security practices and deployment
- **[Complete Docs Index](docs/README.md)** - Full documentation structure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and verify Dafny specs
5. Submit a pull request

## License

[Add your license here]

## Support

- **Documentation**: [`docs/`](docs/)
- **Issues**: GitHub Issues
- **API Docs**: http://localhost:8000/docs (when running)

# Guardian Gateway

**Autonomous Infrastructure for Mathematical AI Verification**

## Overview

Guardian Gateway is a unified proof-driven IDE that enables developers to create formally verified specifications from English requirements. It combines:

- **English → Dafny workflow**: Automatic generation of formal specifications from natural language
- **Real-time verification**: Live proof obligation checking with Dafny
- **AI-powered debugging**: Gemini-based assistant for resolving verification failures
- **Modern IDE experience**: Next.js + shadcn/ui components with split-panel layout

## Architecture

### Frontend (Next.js IDE)
- **Left Panel**: Markdown editor for English requirements
- **Center Panel**: Generated Dafny code with syntax highlighting
- **Right Panel**: Verification results, audit gaps, AI assistant
- **Bottom Panel**: Terminal with solver output

### Backend (Python + FastAPI)
- **REST API**: FastAPI server on port 8000
- **Core Modules**: 
  - `core_workflow.py`: Triage and structuring
  - `core_auditor.py`: Spec analysis with Gemini
  - `core_gateway.py`: Dafny verification
- **API Documentation**: Automatic Swagger/ReDoc generation

## Quick Start (Recommended)

### Prerequisites
- Node.js 18+ and npm
- Python 3.10+
- Dafny CLI installed (see installation below)
- Google Gemini API key

### 1. Install Dafny

```bash
# Windows/Linux (requires .NET SDK 6.0+)
dotnet tool install --global dafny

# macOS
brew install dafny

# Verify installation
dafny --version
```

### 2. Setup Backend

```bash
# Install Python dependencies
pip install -r api/requirements.txt

# Create .env file with your API key
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### 3. Setup Frontend

```bash
cd frontend
npm install
```

### 4. Run Both Services

**Option A: Using convenience script (Linux/Mac)**
```bash
chmod +x dev-all.sh
./dev-all.sh
```

**Option B: Using convenience script (Windows)**
```cmd
dev-all.bat
```

**Option C: Manual (two terminals)**

Terminal 1 - Backend:
```bash
python -m api.main
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

### 5. Access the IDE

- **IDE**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Quick Start (Docker)

```bash
# Create .env file
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Build and run
docker-compose up --build

# Access
# - IDE: http://localhost:3000
# - API: http://localhost:8000
```

## Project Structure

```
guardian-gateway/
├── frontend/                  # Next.js IDE
│   ├── app/                   # Next.js pages
│   ├── components/            # React components
│   │   ├── ide/               # IDE-specific components
│   │   └── ui/                # UI primitives
│   ├── lib/                   # Utilities and API client
│   └── public/templates/      # Specification templates
├── api/                       # FastAPI backend
│   ├── main.py                # API entry point
│   ├── models.py              # Pydantic models
│   └── requirements.txt       # API dependencies
├── core_*.py                  # Core Python modules
├── docs/                      # Documentation
└── tests/                     # Test files
```

## Features

### Phase 1 (Current)
- ✅ Empty state with template gallery
- ✅ Markdown editor for requirements
- ✅ File management (browser storage)
- ✅ Specification generation (English → Dafny)
- ✅ Gap analysis and traceability matrix
- ✅ AI assistant chat interface
- 🔖 GitHub integration placeholders

### Phase 2 (Planned)
- GitHub OAuth login
- Create PR with contract files
- Repository sync
- File management via GitHub API

### Phase 3 (Future)
- GitHub App for CI/CD
- Automated PR verification
- Bot comments with proof results

## Development

### Backend API Endpoints

- `GET /api/health` - Health check
- `POST /api/generate/spec` - Generate Dafny from English
- `POST /api/assistant/chat` - AI debugging assistant

See full API documentation at http://localhost:8000/docs

### Frontend Development

```bash
cd frontend
npm run dev          # Development server
npm run build        # Production build
npm run lint         # Run linter
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[Add your license here]

## Support

- Documentation: `/docs`
- Issues: GitHub Issues
- Templates: `/frontend/public/templates`

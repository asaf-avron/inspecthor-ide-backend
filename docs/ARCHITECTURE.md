# Guardian Gateway Architecture

## System Overview

Guardian Gateway is a formal verification IDE that transforms English requirements into verified Dafny specifications. The system is split into two separate repositories:

- **Backend**: `guardian-gateway` - Python FastAPI server with core verification logic
- **Frontend**: `v0-guardian-gateway-ide` - Next.js web application with modern IDE interface

```mermaid
graph TB
    User[User] --\u003e Frontend[Next.js Frontend]
    Frontend --\u003e|HTTPS + API Key| Backend[FastAPI Backend]
    Backend --\u003e Gemini[Google Gemini API]
    Backend --\u003e Dafny[Dafny Verifier]
    
    subgraph "Frontend Repository"
        Frontend
        UI[shadcn/ui Components]
        APIClient[API Client]
    end
    
    subgraph "Backend Repository"
        Backend
        Workflow[core_workflow.py]
        Auditor[core_auditor.py]
        Gateway[core_gateway.py]
        Parser[core_parser.py]
    end
```

## Backend Components

### Core Modules

#### `core_workflow.py`
- **Triage**: Classifies input documents (spec, code, junk)
- **Structuring**: Organizes requirements into structured format
- Orchestrates the specification generation pipeline

#### `core_auditor.py`
- Analyzes specifications using Google Gemini
- Generates Dafny skeleton code
- Identifies gaps and ambiguities
- Creates traceability matrix

#### `core_gateway.py`
- Interfaces with Dafny verifier
- Executes verification checks
- Parses verification results

#### `core_parser.py`
- Parses various input formats
- Extracts requirements from documents

### API Layer

#### `api/main.py`
FastAPI application with endpoints:
- `GET /api/health` - Health check (public)
- `POST /api/generate/spec` - Generate Dafny from English (authenticated)
- `POST /api/assistant/chat` - AI debugging assistant (authenticated)

#### `api/middleware.py`
Security middleware:
- **APIKeyMiddleware**: Validates X-API-Key header
- **RateLimitMiddleware**: Limits requests per IP
- **RequestLoggingMiddleware**: Logs all requests

#### `api/models.py`
Pydantic models for request/response validation

## Frontend Components

### Pages

#### `app/page.tsx`
Main IDE interface with:
- Project explorer sidebar
- Markdown editor for requirements
- Dafny code editor
- Verification results panel
- Gemini Insight panel
- Terminal output

### Components

#### `components/ide/`
- `header.tsx` - Top navigation and actions
- `project-explorer.tsx` - File tree sidebar
- `markdown-editor.tsx` - Requirements editor
- `code-editor.tsx` - Dafny code viewer
- `verification-panel.tsx` - Verification results
- `gemini-insight-panel.tsx` - AI assistant chat
- `terminal-panel.tsx` - Command output

#### `components/ui/`
shadcn/ui primitives (buttons, dialogs, tabs, etc.)

### API Integration

#### `lib/api-client.ts`
TypeScript client for backend communication:
- Type-safe API calls
- Automatic authentication (API key in headers)
- Error handling and retry logic
- Request/response type definitions

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Middleware
    participant Backend
    
    User-\u003e\u003eFrontend: Enter requirements
    Frontend-\u003e\u003eMiddleware: POST /api/generate/spec<br/>X-API-Key: xxx
    Middleware-\u003e\u003eMiddleware: Validate API key
    Middleware-\u003e\u003eMiddleware: Check rate limit
    Middleware-\u003e\u003eBackend: Forward request
    Backend-\u003e\u003eFrontend: Return spec
    Frontend-\u003e\u003eUser: Display results
```

### Security Layers

1. **HTTPS/TLS**: All production traffic encrypted
2. **API Key Authentication**: X-API-Key header required
3. **CORS**: Whitelist of allowed frontend origins
4. **Rate Limiting**: Per-IP request limits
5. **Request Logging**: Audit trail of all API calls

## Deployment Architecture

### Development

```
┌─────────────────┐         ┌─────────────────┐
│  Frontend       │         │  Backend        │
│  localhost:3000 │ ◀─────\u003e │  localhost:8000 │
│  (npm run dev)  │  HTTP   │  (uvicorn)      │
└─────────────────┘         └─────────────────┘
```

### Production

```
┌─────────────────┐         ┌─────────────────┐
│  Frontend       │         │  Backend        │
│  Vercel         │ ◀─────\u003e │  Railway/Render │
│  (HTTPS)        │  HTTPS  │  (HTTPS)        │
└─────────────────┘         └─────────────────┘
```

**Recommended Platforms**:
- Frontend: Vercel (automatic HTTPS, edge deployment)
- Backend: Railway, Render, or Google Cloud Run (automatic HTTPS)

## API Contracts

### Generate Spec Endpoint

**Request**:
```typescript
POST /api/generate/spec
Headers: X-API-Key: <key>
Body: {
  english_spec: string
}
```

**Response**:
```typescript
{
  triage: {
    doc_type: string,
    confidence: number
  },
  structured_spec: string,
  dafny_skeleton: string,
  gaps: Array<{
    severity: string,
    description: string,
    location: string
  }>,
  ambiguities: string[],
  traceability_matrix: Array<{
    id: string,
    source_text: string,
    code_line: string,
    status: string
  }>
}
```

### Chat Endpoint

**Request**:
```typescript
POST /api/assistant/chat
Headers: X-API-Key: <key>
Body: {
  message: string,
  context?: string
}
```

**Response**:
```typescript
{
  content: string,
  suggestions: string[]
}
```

## Data Flow

1. **User Input**: User writes requirements in markdown editor
2. **API Request**: Frontend sends English spec to backend
3. **Triage**: Backend classifies document type
4. **Structure**: Backend organizes requirements
5. **Audit**: Gemini analyzes spec and generates Dafny
6. **Response**: Backend returns structured data
7. **Display**: Frontend renders Dafny code and analysis
8. **Verification** (future): User triggers Dafny verification
9. **Debugging** (future): AI assistant helps resolve issues

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **AI**: Google Gemini API
- **Verification**: Dafny CLI
- **Server**: Uvicorn (ASGI)
- **Validation**: Pydantic

### Frontend
- **Framework**: Next.js 16 (React 19)
- **Language**: TypeScript
- **UI**: shadcn/ui (Radix UI + Tailwind CSS)
- **State**: React hooks
- **API**: Native fetch with custom client

## Future Enhancements

1. **GitHub Integration**: OAuth login, PR creation, repo sync
2. **Real-time Collaboration**: WebSocket for multi-user editing
3. **CI/CD Integration**: GitHub App for automated verification
4. **Advanced Verification**: Live Dafny checking in editor
5. **Template Library**: Pre-built specification templates

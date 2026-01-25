# Guardian Gateway API

Backend REST API for the Guardian Gateway IDE.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables (create `.env` in project root):
```
GEMINI_API_KEY=your_api_key_here
```

3. Run the server:
```bash
python -m api.main
```

Or with uvicorn directly:
```bash
uvicorn api.main:app --reload --port 8000
```

## API Endpoints

### Health Check
- `GET /api/health` - Check API and service status

### Specification Generation
- `POST /api/generate/spec` - Generate Dafny specification from English requirements

### AI Assistant
- `POST /api/assistant/chat` - Chat with AI assistant for debugging

## Development

The API runs on `http://localhost:8000` by default.

API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

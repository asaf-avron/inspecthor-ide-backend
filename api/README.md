# Inspecthor API

Backend REST API for the [Inspecthor IDE](https://github.com/asaf-avron/inspecthor-ide-frontend). For the architecture and Docker quickstart, see the [main README](../README.md).

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

### Blueprint Management
- `POST /api/blueprints` - Create a new blueprint (bootstraps README.md)
- `GET /api/blueprints` - List all blueprints (paginated, sortable)
- `GET /api/blueprints/{blueprint_id}` - Get single blueprint details
- `GET /api/blueprints/{blueprint_id}/structure` - Get blueprint + file tree (optimized, single RTT)
- `PUT /api/blueprints/{blueprint_id}` - Update blueprint name/description
- `DELETE /api/blueprints/{blueprint_id}` - Delete blueprint (cascades to files and unit_links)
- `POST /api/blueprints/initialize` - Create a blueprint from a GitHub repository and scaffold it

### File Management
- `POST /api/files/save` - Save a file (requires blueprint_id)
- `GET /api/files/{file_id}` - Get file by ID
- `PUT /api/files/{file_id}` - Update file content (atomic)
- `GET /api/files` - List files (filterable by project_id, file_type)
- `DELETE /api/files/{file_id}` - Delete file

### Specification Generation
- `POST /api/generate/spec` - Generate Dafny specification from English requirements
- `POST /api/generate/find-gaps` - Run the Spec Auditor to find gaps without generating code
- `POST /api/generate/refine-spec` - Apply accepted gap suggestions to the spec

### Blueprints
- `POST /api/v1/blueprints/initialize` - Create a blueprint from an Architect's Canvas template

### Verification
- `POST /api/verify` - Verify Dafny code

### AI Assistant
- `POST /api/assistant/chat` - Chat with AI assistant for debugging

## Database Schema

The API uses SQLite by default (PostgreSQL optional) with the following main tables:

- **projects**: Project metadata (UUID primary key, owned by API key hash)
- **files**: Files belonging to projects (UUID primary key, foreign key to projects)
- **unit_links**: Links between root files, unit files, and Dafny files (for deconstruction feature)

All tables use UUID primary keys and cascade deletes for data integrity.

## Database Migrations

The project uses Alembic for database migrations:

```bash
# Run migrations
cd api
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Development

The API runs on `http://localhost:8000` by default.

API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

"""
File management endpoints for Guardian Gateway
Handles saving, loading, listing, updating, and deleting specification files
Files must belong to a project and ownership is verified through project ownership
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import icontract

from api.database import get_db, hash_api_key, File as DBFile, Project as DBProject, User
from api.models import (
    FileSaveRequest,
    FileSaveResponse,
    FileUpdateRequest,
    FileResponse,
    FileListResponse,
    FileListItem
)
from api.auth import get_current_user
from api.core import adapters
from api.core.models import FileType
from api.core import file_operations

router = APIRouter(prefix="/api/files", tags=["files"])


def map_error_to_status(error_kind: str) -> int:
    """
    Map Core error kind to HTTP status code (Oracle's mapping table).
    
    Mapping:
    - NotFound → 404
    - Unauthorized → 403
    - Conflict → 409
    - Precondition → 400
    """
    mapping = {
        "NotFound": 404,
        "Unauthorized": 403,
        "Conflict": 409,
        "Precondition": 400
    }
    return mapping.get(error_kind, 500)


def get_api_key_from_header(
    x_api_key: Optional[str] = Header(None),
    request: Request = None
) -> str:
    """
    Extract API key or generate anonymous session key.
    For anonymous users (local-first), creates a session key based on IP.
    For authenticated users, uses provided API key.
    """
    if x_api_key:
        return x_api_key
    
    # Anonymous user - generate session key from IP
    if request and request.client:
        client_ip = request.client.host
        return f"anon_{client_ip}"
    
    return "anon_default"


def get_project_owner_filter(user: Optional[User] = None, api_key_hash_value: Optional[str] = None):
    """
    Get SQLAlchemy filter for project ownership.
    Returns a filter that checks user_id (if authenticated) or api_key_hash (if anonymous).
    For authenticated users, also checks api_key_hash to include projects created before user auth was implemented.
    """
    from sqlalchemy import or_
    if user:
        # Check both user_id and api_key_hash for authenticated users (migration support)
        return or_(
            DBProject.user_id == user.user_id,
            DBProject.api_key_hash == api_key_hash_value
        )
    elif api_key_hash_value:
        return DBProject.api_key_hash == api_key_hash_value
    else:
        # Should not happen, but return a filter that matches nothing
        from sqlalchemy import false
        return false()


@icontract.require(
    lambda request, api_key, db, current_user:
        request is not None and
        request.project_id is not None and
        request.filename is not None and
        len(request.filename) > 0 and
        request.content is not None and
        len(request.content.encode('utf-8')) < 1000000 and  # Content size < 1MB (matching Dafny)
        db is not None,
    "Preconditions: Valid request, non-empty filename, content size < 1MB, db session exists"
)
@icontract.ensure(
    lambda result, request, api_key, db, current_user, OLD:
        result is not None and
        result.file_id is not None and
        result.filename == request.filename,
    "Postconditions: File saved successfully with matching filename"
)
@router.post("/save", response_model=FileSaveResponse)
async def save_file(
    request: FileSaveRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Save a specification or Dafny file.
    Files must belong to a project owned by the authenticated user or API key.
    
    Refactored to use Functional Core / Imperative Shell architecture.
    """
    api_key_hash_value = hash_api_key(api_key) if api_key else None
    
    # Determine owner identifier
    if current_user:
        owner_id = str(current_user.user_id)
    elif api_key_hash_value:
        owner_id = api_key_hash_value
    else:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    # 1. I/O: Load scoped state (project + all its files for uniqueness check)
    owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
    state = adapters.build_scoped_state(
        project_id=request.project_id,
        owner_filter=owner_filter,
        db=db
    )
    
    # 2. CORE: Generate UUID and call pure logic
    new_file_id = str(uuid.uuid4())
    
    # Convert file_type string to FileType enum
    file_type_map = {
        'md': FileType.MD,
        'dfy': FileType.DFY,
        'unit': FileType.UNIT
    }
    file_type = file_type_map.get(request.file_type, FileType.MD)
    
    new_state, result = file_operations.save_file_core(
        state,
        new_file_id,
        request.project_id,
        request.filename,
        request.content,
        file_type,
        owner_id
    )
    
    # 3. ADAPTER: Apply diff and map errors
    if not result.success:
        status_code = map_error_to_status(result.error_kind or "Precondition")
        raise HTTPException(status_code=status_code, detail=result.error_message)
    
    adapters.apply_state_diff(db, state, new_state)
    db.commit()
    
    # Load created file for response
    db_file = db.query(DBFile).filter(DBFile.file_id == new_file_id).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return FileSaveResponse(
        file_id=str(db_file.file_id),
        filename=str(db_file.filename),  # type: ignore[arg-type]
        saved_at=db_file.created_at.isoformat(),
        size_bytes=len(request.content.encode('utf-8'))
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Load a file by ID.
    Only returns files from projects owned by the authenticated user or API key.
    """
    api_key_hash_value = hash_api_key(api_key) if api_key else None
    
    # Join with project to verify ownership
    owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
    db_file = db.query(DBFile).join(DBProject).filter(
        DBFile.file_id == file_id,
        owner_filter
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_id=str(db_file.file_id),
        filename=str(db_file.filename),  # type: ignore[arg-type]
        content=str(db_file.content),  # type: ignore[arg-type]
        file_type=str(db_file.file_type),  # type: ignore[arg-type]
        project_id=str(db_file.project_id),
        created_at=db_file.created_at.isoformat(),
        updated_at=db_file.updated_at.isoformat(),
        size_bytes=len(db_file.content.encode('utf-8')),
        renamed=bool(db_file.renamed)  # type: ignore[arg-type]
    )


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: Optional[str] = None,
    file_type: Optional[str] = None,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all files from projects owned by the authenticated user or API key.
    Optionally filter by project_id and file_type.
    """
    api_key_hash_value = hash_api_key(api_key) if api_key else None
    
    # Join with project to verify ownership
    owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
    query = db.query(DBFile).join(DBProject).filter(owner_filter)
    
    if project_id:
        query = query.filter(DBFile.project_id == project_id)
    if file_type:
        query = query.filter(DBFile.file_type == file_type)
    
    files = query.order_by(DBFile.updated_at.desc()).all()
    
    file_items = [
        FileListItem(
            file_id=str(f.file_id),
            filename=str(f.filename),  # type: ignore[arg-type]
            file_type=str(f.file_type),  # type: ignore[arg-type]
            size_bytes=len(f.content.encode('utf-8')),
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat()
        )
        for f in files
    ]
    
    return FileListResponse(
        files=file_items,
        total=len(file_items)
    )


@icontract.require(
    lambda file_id, request, api_key, db, current_user:
        file_id is not None and
        len(file_id) > 0 and
        request is not None and
        request.content is not None and
        db is not None,
    "Preconditions: Valid file_id, non-empty content, db session exists"
)
@icontract.ensure(
    lambda result, file_id, request, api_key, db, current_user, OLD:
        result is not None and
        result.file_id == file_id and
        result.content == request.content,
    "Postconditions: File updated successfully with matching content"
)
@router.put("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: str,
    request: FileUpdateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update file content atomically.
    Optionally rename file if filename is provided.
    Only updates files from projects owned by the authenticated user or API key.
    
    Refactored to use Functional Core / Imperative Shell architecture.
    """
    api_key_hash_value = hash_api_key(api_key) if api_key else None
    
    # Determine owner identifier
    if current_user:
        owner_id = str(current_user.user_id)
    elif api_key_hash_value:
        owner_id = api_key_hash_value
    else:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    # 1. I/O: Load file to get project_id, then load scoped state
    db_file = db.query(DBFile).filter(DBFile.file_id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
    state = adapters.build_scoped_state(
        project_id=str(db_file.project_id),
        owner_filter=owner_filter,
        db=db
    )
    
    # 2. CORE: Call pure logic
    new_filename = request.filename if request.filename else ""
    new_state, result = file_operations.update_file_core(
        state,
        file_id,
        request.content,
        new_filename,
        owner_id
    )
    
    # 3. ADAPTER: Apply diff and map errors
    if not result.success:
        status_code = map_error_to_status(result.error_kind or "Precondition")
        raise HTTPException(status_code=status_code, detail=result.error_message)
    
    adapters.apply_state_diff(db, state, new_state)
    db.commit()
    db.refresh(db_file)
    
    return FileResponse(
        file_id=str(db_file.file_id),
        filename=str(db_file.filename),  # type: ignore[arg-type]
        content=str(db_file.content),  # type: ignore[arg-type]
        file_type=str(db_file.file_type),  # type: ignore[arg-type]
        project_id=str(db_file.project_id),
        created_at=db_file.created_at.isoformat(),
        updated_at=db_file.updated_at.isoformat(),
        size_bytes=len(db_file.content.encode('utf-8')),
        renamed=bool(db_file.renamed)  # type: ignore[arg-type]
    )


@icontract.require(
    lambda file_id, api_key, db, current_user:
        file_id is not None and
        len(file_id) > 0 and
        db is not None,
    "Preconditions: Valid file_id, db session exists"
)
@icontract.ensure(
    lambda result, file_id, api_key, db, current_user, OLD:
        result is not None and
        result.get("deleted") == True and
        result.get("file_id") == file_id,
    "Postconditions: File deleted successfully"
)
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a file by ID.
    Only deletes files from projects owned by the authenticated user or API key.
    
    Refactored to use Functional Core / Imperative Shell architecture.
    """
    api_key_hash_value = hash_api_key(api_key) if api_key else None
    
    # Determine owner identifier
    if current_user:
        owner_id = str(current_user.user_id)
    elif api_key_hash_value:
        owner_id = api_key_hash_value
    else:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    # 1. I/O: Load file to get project_id, then load scoped state
    db_file = db.query(DBFile).filter(DBFile.file_id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
    state = adapters.build_scoped_state(
        project_id=str(db_file.project_id),
        owner_filter=owner_filter,
        db=db
    )
    
    # 2. CORE: Call pure logic
    new_state, result = file_operations.delete_file_core(
        state,
        file_id,
        owner_id
    )
    
    # 3. ADAPTER: Apply diff and map errors
    if not result.success:
        status_code = map_error_to_status(result.error_kind or "Precondition")
        raise HTTPException(status_code=status_code, detail=result.error_message)
    
    adapters.apply_state_diff(db, state, new_state)
    db.commit()
    
    return {"deleted": True, "file_id": file_id}

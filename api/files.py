"""
File management endpoints for Guardian Gateway
Handles saving, loading, listing, updating, and deleting specification files
Files must belong to a project and ownership is verified through project ownership
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime

from api.database import get_db, hash_api_key, File as DBFile, Project as DBProject
from api.models import (
    FileSaveRequest,
    FileSaveResponse,
    FileUpdateRequest,
    FileResponse,
    FileListResponse,
    FileListItem
)

router = APIRouter(prefix="/api/files", tags=["files"])


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


@router.post("/save", response_model=FileSaveResponse)
async def save_file(
    request: FileSaveRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Save a specification or Dafny file.
    Files must belong to a project owned by the API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Validate project exists and is owned by API key
    project = db.query(DBProject).filter(
        DBProject.project_id == request.project_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")
    
    # Check filename uniqueness per project
    existing_file = db.query(DBFile).filter(
        DBFile.project_id == request.project_id,
        DBFile.filename == request.filename
    ).first()
    
    if existing_file:
        raise HTTPException(status_code=409, detail="Filename already exists in this project")
    
    size_bytes = len(request.content.encode('utf-8'))
    
    db_file = DBFile(
        project_id=request.project_id,
        filename=request.filename,
        content=request.content,
        file_type=request.file_type
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    return FileSaveResponse(
        file_id=str(db_file.file_id),
        filename=db_file.filename,
        saved_at=db_file.created_at.isoformat(),
        size_bytes=size_bytes
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Load a file by ID.
    Only returns files from projects owned by the requesting API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Join with project to verify ownership
    db_file = db.query(DBFile).join(DBProject).filter(
        DBFile.file_id == file_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_id=str(db_file.file_id),
        filename=db_file.filename,
        content=db_file.content,
        file_type=db_file.file_type,
        project_id=str(db_file.project_id),
        created_at=db_file.created_at.isoformat(),
        updated_at=db_file.updated_at.isoformat(),
        size_bytes=len(db_file.content.encode('utf-8'))
    )


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: Optional[str] = None,
    file_type: Optional[str] = None,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    List all files from projects owned by the requesting API key.
    Optionally filter by project_id and file_type.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Join with project to verify ownership
    query = db.query(DBFile).join(DBProject).filter(
        DBProject.api_key_hash == api_key_hash_value
    )
    
    if project_id:
        query = query.filter(DBFile.project_id == project_id)
    if file_type:
        query = query.filter(DBFile.file_type == file_type)
    
    files = query.order_by(DBFile.updated_at.desc()).all()
    
    file_items = [
        FileListItem(
            file_id=str(f.file_id),
            filename=f.filename,
            file_type=f.file_type,
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


@router.put("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: str,
    request: FileUpdateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Update file content atomically.
    Optionally rename file if filename is provided.
    Only updates files from projects owned by the requesting API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Join with project to verify ownership
    db_file = db.query(DBFile).join(DBProject).filter(
        DBFile.file_id == file_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update content
    db_file.content = request.content
    
    # Update filename if provided (with uniqueness check)
    if request.filename and request.filename != db_file.filename:
        existing = db.query(DBFile).filter(
            DBFile.project_id == db_file.project_id,
            DBFile.filename == request.filename,
            DBFile.file_id != file_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=409, detail="Filename already exists in this project")
        
        db_file.filename = request.filename
    
    # updated_at is auto-updated by SQLAlchemy
    db.commit()
    db.refresh(db_file)
    
    return FileResponse(
        file_id=str(db_file.file_id),
        filename=db_file.filename,
        content=db_file.content,
        file_type=db_file.file_type,
        project_id=str(db_file.project_id),
        created_at=db_file.created_at.isoformat(),
        updated_at=db_file.updated_at.isoformat(),
        size_bytes=len(db_file.content.encode('utf-8'))
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Delete a file by ID.
    Only deletes files from projects owned by the requesting API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Join with project to verify ownership
    db_file = db.query(DBFile).join(DBProject).filter(
        DBFile.file_id == file_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    db.delete(db_file)
    db.commit()
    
    return {"deleted": True, "file_id": file_id}

"""
File management endpoints for Guardian Gateway
Handles saving, loading, listing, and deleting specification files
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime

from api.database import get_db, hash_api_key, File as DBFile
from api.models import (
    FileSaveRequest,
    FileSaveResponse,
    FileResponse,
    FileListResponse,
    FileListItem
)

router = APIRouter(prefix="/api/files", tags=["files"])


def get_api_key_from_header(x_api_key: str = Header(...)) -> str:
    """Extract and validate API key from header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    return x_api_key


@router.post("/save", response_model=FileSaveResponse)
async def save_file(
    request: FileSaveRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Save a specification or Dafny file.
    Files are associated with the API key for access control.
    """
    file_id = str(uuid.uuid4())
    api_key_hash_value = hash_api_key(api_key)
    size_bytes = len(request.content.encode('utf-8'))
    
    db_file = DBFile(
        file_id=file_id,
        api_key_hash=api_key_hash_value,
        filename=request.filename,
        content=request.content,
        file_type=request.file_type,
        project_id=request.project_id,
        size_bytes=size_bytes
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    return FileSaveResponse(
        file_id=file_id,
        filename=request.filename,
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
    Only returns files owned by the requesting API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    db_file = db.query(DBFile).filter(
        DBFile.file_id == file_id,
        DBFile.api_key_hash == api_key_hash_value
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_id=db_file.file_id,
        filename=db_file.filename,
        content=db_file.content,
        file_type=db_file.file_type,
        created_at=db_file.created_at.isoformat(),
        updated_at=db_file.updated_at.isoformat(),
        size_bytes=db_file.size_bytes
    )


@router.get("", response_model=FileListResponse)
async def list_files(
    project_id: Optional[str] = None,
    file_type: Optional[str] = None,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    List all files owned by the requesting API key.
    Optionally filter by project_id and file_type.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    query = db.query(DBFile).filter(DBFile.api_key_hash == api_key_hash_value)
    
    if project_id:
        query = query.filter(DBFile.project_id == project_id)
    if file_type:
        query = query.filter(DBFile.file_type == file_type)
    
    files = query.order_by(DBFile.updated_at.desc()).all()
    
    file_items = [
        FileListItem(
            file_id=f.file_id,
            filename=f.filename,
            file_type=f.file_type,
            size_bytes=f.size_bytes,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat()
        )
        for f in files
    ]
    
    return FileListResponse(
        files=file_items,
        total=len(file_items)
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Delete a file by ID.
    Only deletes files owned by the requesting API key.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    db_file = db.query(DBFile).filter(
        DBFile.file_id == file_id,
        DBFile.api_key_hash == api_key_hash_value
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    db.delete(db_file)
    db.commit()
    
    return {"deleted": True, "file_id": file_id}

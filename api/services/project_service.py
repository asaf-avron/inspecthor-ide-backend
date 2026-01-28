"""
Project management service.
Handles project CRUD operations with strict separation between Shell (DB/HTTP) and Core (pure logic).
This service enforces the adapter barrier: SQLAlchemy objects are never passed to Core functions.
"""

import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from api.database import Project as DBProject, File as DBFile
from api.core import adapters, migration, project_management
from api.core.models import Owner
from api.models import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListResponse,
    ProjectStructureResponse,
    ProjectDeleteResponse,
    FileMetadata,
)
from api.files import get_project_owner_filter, hash_api_key

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Service for project management operations.
    
    This service orchestrates:
    1. Loading SQLAlchemy objects from DB
    2. Converting to Core models via adapters
    3. Calling Core functions (pure logic)
    4. Applying state diffs back to DB
    5. Converting results to response DTOs
    """
    
    def __init__(self, db: Session, current_user=None):
        """
        Initialize the service.
        
        Args:
            db: Database session
            current_user: Current authenticated user (optional)
        """
        self.db = db
        self.current_user = current_user
    
    def create_project(
        self,
        request: ProjectCreateRequest,
        api_key: str
    ) -> ProjectResponse:
        """
        Create a new project.
        
        Args:
            request: Project creation request
            api_key: API key for authentication
            
        Returns:
            ProjectResponse with project details
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        logger.info(f"Creating project: name='{request.name}', user_id={user_id}, api_key_hash={api_key_hash_value[:20] if api_key_hash_value else None}")
        
        # Validate name
        if not request.name:
            raise HTTPException(status_code=400, detail="Project name is required")
        
        name_trimmed = request.name.strip()
        if len(name_trimmed) == 0:
            raise HTTPException(status_code=400, detail="Project name cannot be empty")
        
        if len(name_trimmed) > 255:
            raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
        
        # Validate description length
        description = request.description or ""
        if len(description) > 1000:
            raise HTTPException(status_code=400, detail="Description too long (max 1000 characters)")
        
        # Determine owner
        if user_id:
            owner = Owner.authenticated(user_id)
        elif api_key_hash_value:
            owner = Owner.anonymous(api_key_hash_value)
        else:
            raise HTTPException(status_code=403, detail="Authentication required")
        
        # 1. I/O: Load all projects owned by this owner for uniqueness check
        owner_filter = get_project_owner_filter(self.current_user, api_key_hash_value)
        state = adapters.build_scoped_state(
            project_id=None,  # Load all projects for this owner
            owner_filter=owner_filter,
            db=self.db
        )
        
        # 2. CORE: Generate UUID and call pure logic
        new_project_id = str(uuid.uuid4())
        new_state, result = project_management.create_project_core(
            state,
            new_project_id,
            name_trimmed,
            description,
            owner
        )
        
        # 3. ADAPTER: Apply diff and map errors
        if not result.success:
            status_code = self._map_error_to_status(result.error_kind or "Precondition")
            raise HTTPException(status_code=status_code, detail=result.error_message)
        
        adapters.apply_state_diff(self.db, state, new_state)
        self.db.commit()
        
        # Load created project for response
        project = self.db.query(DBProject).filter(DBProject.project_id == new_project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectResponse(
            project_id=str(project.project_id),
            name=str(project.name),  # type: ignore[arg-type]
            description=str(project.description) if project.description else None,  # type: ignore[arg-type]
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            file_count=0,
            redirect_url=f"/app/{project.project_id}"
        )
    
    def list_projects(
        self,
        limit: int,
        offset: int,
        sort: str,
        order: str,
        api_key: str
    ) -> ProjectListResponse:
        """
        List all projects owned by the authenticated user or API key.
        
        Args:
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            sort: Field to sort by
            order: Sort order (asc/desc)
            api_key: API key for authentication
            
        Returns:
            ProjectListResponse with projects and pagination info
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        # Migrate anonymous projects to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_projects_to_user(api_key_hash_value)
        
        # Base query: filter by user_id (if authenticated) or api_key_hash (if anonymous)
        query = self.db.query(DBProject)
        if user_id:
            query = query.filter(DBProject.user_id == user_id)
        else:
            query = query.filter(DBProject.api_key_hash == api_key_hash_value)
        
        # Count total before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(DBProject, sort)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        projects = query.limit(limit).offset(offset).all()
        
        # Get file count for each project
        project_responses = []
        for project in projects:
            file_count = self.db.query(DBFile).filter(DBFile.project_id == project.project_id).count()
            project_responses.append(ProjectResponse(
                project_id=str(project.project_id),
                name=str(project.name),  # type: ignore[arg-type]
                description=str(project.description) if project.description else None,  # type: ignore[arg-type]
                created_at=project.created_at.isoformat(),
                updated_at=project.updated_at.isoformat(),
                file_count=file_count
            ))
        
        return ProjectListResponse(
            projects=project_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    def get_project_structure(
        self,
        project_id: str,
        api_key: str
    ) -> ProjectStructureResponse:
        """
        Get project metadata and file tree in one request.
        
        Args:
            project_id: Project ID
            api_key: API key for authentication
            
        Returns:
            ProjectStructureResponse with project and files
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        # Migrate anonymous projects to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_projects_to_user(api_key_hash_value)
        
        # Load project with ownership check
        query = self.db.query(DBProject).filter(DBProject.project_id == project_id)
        if user_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBProject.user_id == user_id,
                    DBProject.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBProject.api_key_hash == api_key_hash_value)
        
        project = query.first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # If project was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
            project.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(project)
        
        # Load all files in one query
        files = self.db.query(DBFile).filter(
            DBFile.project_id == project_id
        ).order_by(DBFile.filename).all()
        
        # Build response
        return ProjectStructureResponse(
            project=ProjectResponse(
                project_id=str(project.project_id),
                name=str(project.name),  # type: ignore[arg-type]
                description=str(project.description) if project.description else None,  # type: ignore[arg-type]
                created_at=project.created_at.isoformat(),
                updated_at=project.updated_at.isoformat(),
                file_count=len(files)
            ),
            files=[
                FileMetadata(
                    file_id=str(f.file_id),
                    filename=str(f.filename),  # type: ignore[arg-type]
                    file_type=str(f.file_type),  # type: ignore[arg-type]
                    updated_at=f.updated_at.isoformat(),
                    size_bytes=len(f.content.encode('utf-8'))
                ) for f in files
            ]
        )
    
    def get_project(
        self,
        project_id: str,
        api_key: str
    ) -> ProjectResponse:
        """
        Get single project details.
        
        Args:
            project_id: Project ID
            api_key: API key for authentication
            
        Returns:
            ProjectResponse with project details
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        # Migrate anonymous projects to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_projects_to_user(api_key_hash_value)
        
        query = self.db.query(DBProject).filter(DBProject.project_id == project_id)
        if user_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBProject.user_id == user_id,
                    DBProject.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBProject.api_key_hash == api_key_hash_value)
        
        project = query.first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # If project was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
            project.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(project)
        
        file_count = self.db.query(DBFile).filter(DBFile.project_id == project_id).count()
        
        return ProjectResponse(
            project_id=str(project.project_id),
            name=str(project.name),  # type: ignore[arg-type]
            description=str(project.description) if project.description else None,  # type: ignore[arg-type]
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            file_count=file_count
        )
    
    def update_project(
        self,
        project_id: str,
        request: ProjectUpdateRequest,
        api_key: str
    ) -> ProjectResponse:
        """
        Update project name and/or description.
        
        Args:
            project_id: Project ID
            request: Update request
            api_key: API key for authentication
            
        Returns:
            ProjectResponse with updated project details
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        # Migrate anonymous projects to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_projects_to_user(api_key_hash_value)
        
        # Load project with ownership check
        query = self.db.query(DBProject).filter(DBProject.project_id == project_id)
        if user_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBProject.user_id == user_id,
                    DBProject.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBProject.api_key_hash == api_key_hash_value)
        
        project = query.first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # If project was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
            project.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(project)
        
        # Validate at least one field is provided
        if request.name is None and request.description is None:
            raise HTTPException(status_code=400, detail="At least one field must be provided")
        
        # If name is provided, check uniqueness
        if request.name is not None:
            if len(request.name) < 1 or len(request.name) > 255:
                raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
            
            if request.name != project.name:
                existing_query = self.db.query(DBProject).filter(
                    func.lower(DBProject.name) == request.name.lower(),
                    DBProject.project_id != project_id
                )
                if user_id:
                    existing_query = existing_query.filter(DBProject.user_id == user_id)
                else:
                    existing_query = existing_query.filter(DBProject.api_key_hash == api_key_hash_value)
                
                existing = existing_query.first()
                
                if existing:
                    raise HTTPException(status_code=400, detail="Project name already exists")
                
                project.name = request.name  # type: ignore[assignment]
        
        # Update description if provided
        if request.description is not None:
            if len(request.description) > 1000:
                raise HTTPException(status_code=400, detail="Description too long (max 1000 characters)")
            project.description = request.description  # type: ignore[assignment]
        
        # Update timestamp (SQLAlchemy handles this with onupdate)
        self.db.commit()
        self.db.refresh(project)
        
        # Get file count
        file_count = self.db.query(DBFile).filter(DBFile.project_id == project_id).count()
        
        return ProjectResponse(
            project_id=str(project.project_id),
            name=str(project.name),  # type: ignore[arg-type]
            description=str(project.description) if project.description else None,  # type: ignore[arg-type]
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            file_count=file_count
        )
    
    def delete_project(
        self,
        project_id: str,
        api_key: str
    ) -> ProjectDeleteResponse:
        """
        Delete a project and all associated files atomically (cascade).
        
        Args:
            project_id: Project ID
            api_key: API key for authentication
            
        Returns:
            ProjectDeleteResponse with deletion confirmation
        """
        user_id, api_key_hash_value = self._get_project_owner_id(api_key)
        
        # Migrate anonymous projects to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_projects_to_user(api_key_hash_value)
        
        # Determine owner identifier
        if user_id:
            owner_id = user_id
        elif api_key_hash_value:
            owner_id = api_key_hash_value
        else:
            raise HTTPException(status_code=403, detail="Authentication required")
        
        # 1. I/O: Load project + all its files for cascade deletion
        owner_filter = get_project_owner_filter(self.current_user, api_key_hash_value)
        state = adapters.build_scoped_state(
            project_id=project_id,
            owner_filter=owner_filter,
            db=self.db
        )
        
        # Count files before deletion (for response)
        file_count = len([f for f in state.files.values() if f.project_id == project_id])
        
        # 2. CORE: Call pure logic (cascade handled in Core)
        new_state, result = project_management.delete_project_core(
            state,
            project_id,
            owner_id
        )
        
        # 3. ADAPTER: Apply diff and map errors
        if not result.success:
            status_code = self._map_error_to_status(result.error_kind or "Precondition")
            raise HTTPException(status_code=status_code, detail=result.error_message)
        
        adapters.apply_state_diff(self.db, state, new_state)
        self.db.commit()
        
        return ProjectDeleteResponse(
            deleted=True,
            project_id=str(project_id),
            files_deleted=file_count
        )
    
    def _get_project_owner_id(
        self,
        api_key: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get project owner identifier (user_id or api_key_hash).
        
        Args:
            api_key: API key string
            
        Returns:
            Tuple of (user_id, api_key_hash) - one will be None
        """
        if self.current_user:
            return (str(self.current_user.user_id), None)
        
        if api_key:
            api_key_hash_value = hash_api_key(api_key)
            return (None, api_key_hash_value)
        
        return (None, None)
    
    def _migrate_anonymous_projects_to_user(self, api_key_hash_value: str) -> int:
        """
        Migrate anonymous projects to authenticated user.
        
        Args:
            api_key_hash_value: API key hash
            
        Returns:
            Number of projects migrated
        """
        # 1. I/O: Fetch snapshot (all projects and files for full state)
        projects = self.db.query(DBProject).all()
        files = self.db.query(DBFile).all()
        
        # 2. ADAPTER: Build SystemState from SQLAlchemy objects
        old_state = adapters.build_system_state(projects, files)
        
        # Count projects that will be migrated (before migration)
        projects_to_migrate = [
            p for p in projects
            if p.api_key_hash == api_key_hash_value and p.user_id is None
        ]
        migrated_count = len(projects_to_migrate)
        
        if migrated_count == 0:
            return 0
        
        # 3. CORE: Call pure logic (matches Dafny MigrateAnonymousProjects)
        new_state = migration.migrate_anonymous_projects(
            old_state,
            str(self.current_user.user_id),
            api_key_hash_value
        )
        
        # 4. ADAPTER: Apply state diff back to database
        adapters.apply_state_diff(self.db, old_state, new_state)
        
        # 5. I/O: Commit changes
        self.db.commit()
        
        logger.info(f"Migrated {migrated_count} anonymous projects to user {self.current_user.user_id}")
        return migrated_count
    
    def _map_error_to_status(self, error_kind: str) -> int:
        """
        Map Core error kind to HTTP status code.
        
        Args:
            error_kind: Error kind from Core Result
            
        Returns:
            HTTP status code
        """
        mapping = {
            "NotFound": 404,
            "Unauthorized": 403,
            "Conflict": 409,
            "Precondition": 400
        }
        return mapping.get(error_kind, 500)

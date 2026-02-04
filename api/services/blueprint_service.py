"""
Blueprint management service.
Handles blueprint CRUD operations with strict separation between Shell (DB/HTTP) and Core (pure logic).
This service enforces the adapter barrier: SQLAlchemy objects are never passed to Core functions.
"""

import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from api.database import Blueprint as DBBlueprint, File as DBFile
from api.core import adapters, migration, blueprint_management, file_operations
from api.core.models import Owner, FileType
from api.models import (
    BlueprintCreateRequest,
    BlueprintUpdateRequest,
    BlueprintResponse,
    BlueprintListResponse,
    BlueprintStructureResponse,
    BlueprintDeleteResponse,
    BlueprintDeleteResponse,
    BlueprintInitRequest,
    BlueprintInitResponse,
    FileMetadata,
)
from api.github.api_client import GitHubStatelessClient
from api.files import get_blueprint_owner_filter, hash_api_key

logger = logging.getLogger(__name__)


class BlueprintService:
    """
    Service for blueprint management operations.
    
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
    
    def create_blueprint(
        self,
        request: BlueprintCreateRequest,
        api_key: str
    ) -> BlueprintResponse:
        """
        Create a new blueprint.
        
        Args:
            request: Blueprint creation request
            api_key: API key for authentication
            
        Returns:
            BlueprintResponse with blueprint details
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        logger.info(f"Creating blueprint: name='{request.name}', user_id={user_id}, api_key_hash={api_key_hash_value[:20] if api_key_hash_value else None}")
        
        # Validate name
        if not request.name:
            raise HTTPException(status_code=400, detail="Blueprint name is required")
        
        name_trimmed = request.name.strip()
        if len(name_trimmed) == 0:
            raise HTTPException(status_code=400, detail="Blueprint name cannot be empty")
        
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
        
        # 1. I/O: Load all blueprinte owned by this owner for uniqueness check
        owner_filter = get_blueprint_owner_filter(self.current_user, api_key_hash_value)
        state = adapters.build_scoped_state(
            blueprint_id=None,  # Load all blueprints for this owner
            owner_filter=owner_filter,
            db=self.db
        )
        
        # 2. CORE: Generate UUID and call pure logic
        new_blueprint_id = str(uuid.uuid4())
        new_state, result = blueprint_management.create_blueprint_core(
            state,
            new_blueprint_id,
            name_trimmed,
            description,
            owner
        )
        
        if not result.success:
             # Should not happen given preconditions check, but just in case
             status_code = self._map_error_to_status(result.error_kind or "Precondition")
             raise HTTPException(status_code=status_code, detail=result.error_message)

        # 2b. CORE: Add default README
        readme_id = str(uuid.uuid4())
        readme_content = f"# {name_trimmed}\n\n{description}"
        # Determine owner_id string for file operations
        owner_id_str = user_id if user_id else api_key_hash_value

        new_state, save_result = file_operations.save_file_core(
            new_state,
            readme_id,
            new_blueprint_id,
            "README.md",
            readme_content,
            FileType.MD,
            owner_id_str
        )
        
        print(f"DEBUG: save_file_core result: {save_result.success}, {save_result.error_message}")
        print(f"DEBUG: new_state.files keys: {list(new_state.files.keys())}")
        
        if not save_result.success:
             logger.error(f"Failed to create default README: {save_result.error_message}")
             raise Exception(f"SAVE FAILED: {save_result.error_kind}: {save_result.error_message}")
        
        # 3. ADAPTER: Apply diff and map errors
        if not result.success:
            status_code = self._map_error_to_status(result.error_kind or "Precondition")
            raise HTTPException(status_code=status_code, detail=result.error_message)
        
        adapters.apply_state_diff(self.db, state, new_state)

        # Generate component UUID for Brain architecture (Task #2)
        # The component_uuid is separate from blueprint_id to allow components to be tracked
        # independently of their Blueprint parent
        component_uuid = str(uuid.uuid4())

        # Set component UUID on the blueprint
        # Note: We don't initialize the Brain structure here by default to keep it optional
        # Users can explicitly call /api/brain/initialize when they're ready
        try:
            new_blueprint_id_uuid_temp = uuid.UUID(new_blueprint_id) if isinstance(new_blueprint_id, str) else new_blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=500, detail="Invalid blueprint ID format")

        blueprint_record = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == new_blueprint_id_uuid_temp).first()
        if blueprint_record:
            blueprint_record.component_uuid = component_uuid
            blueprint_record.sync_status = 'clean'  # Initial state

        self.db.commit()
        logger.info(f"Created blueprint with component_uuid: {component_uuid}")

        # Load created blueprint for response
        # Convert string UUID to UUID object for SQLite compatibility
        try:
            new_blueprint_id_uuid = uuid.UUID(new_blueprint_id) if isinstance(new_blueprint_id, str) else new_blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=500, detail="Invalid blueprint ID format")
        
        blueprint = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == new_blueprint_id_uuid).first()
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")
        
        return BlueprintResponse(
            blueprint_id=str(blueprint.blueprint_id),
            name=str(blueprint.name),  # type: ignore[arg-type]
            description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
            created_at=blueprint.created_at.isoformat(),
            updated_at=blueprint.updated_at.isoformat(),
            file_count=0,
            redirect_url=f"/app/{blueprint.blueprint_id}",
            repository_url=blueprint.repository_url,
            default_branch=blueprint.default_branch or "main",
            component_uuid=component_uuid,
            registry_path=blueprint.registry_path,
            sync_status=blueprint.sync_status or "clean"
        )
    
    def list_blueprints(
        self,
        limit: int,
        offset: int,
        sort: str,
        order: str,
        api_key: str
    ) -> BlueprintListResponse:
        """
        List all blueprints owned by the authenticated user or API key.
        
        Args:
            limit: Maximum number of blueprints to return
            offset: Number of blueprints to skip
            sort: Field to sort by
            order: Sort order (asc/desc)
            api_key: API key for authentication
            
        Returns:
            BlueprintListResponse with blueprints and pagination info
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # Migrate anonymous blueprints to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_blueprints_to_user(api_key_hash_value)
        
        # Base query: filter by user_id (if authenticated) or api_key_hash (if anonymous)
        # Convert string UUID to UUID object for SQLite compatibility
        user_id_uuid = None
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        query = self.db.query(DBBlueprint)
        if user_id_uuid:
            query = query.filter(DBBlueprint.user_id == user_id_uuid)
        else:
            query = query.filter(DBBlueprint.api_key_hash == api_key_hash_value)
        
        # Count total before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(DBBlueprint, sort)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        blueprints = query.limit(limit).offset(offset).all()
        
        # Get file count for each blueprint
        blueprint_responses = []
        for blueprint in blueprints:
            file_count = self.db.query(DBFile).filter(DBFile.blueprint_id == blueprint.blueprint_id).count()
            blueprint_responses.append(BlueprintResponse(
                blueprint_id=str(blueprint.blueprint_id),
                name=str(blueprint.name),  # type: ignore[arg-type]
                description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
                created_at=blueprint.created_at.isoformat(),
                updated_at=blueprint.updated_at.isoformat(),
                file_count=file_count,
                repository_url=blueprint.repository_url,
                default_branch=blueprint.default_branch or "main"
            ))
        
        return BlueprintListResponse(
            blueprints=blueprint_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    def get_blueprint_structure(
        self,
        blueprint_id: str,
        api_key: str
    ) -> BlueprintStructureResponse:
        """
        Get blueprint metadata and file tree in one request.
        
        Args:
            blueprint_id: Blueprint ID
            api_key: API key for authentication
            
        Returns:
            BlueprintStructureResponse with blueprint and files
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # Migrate anonymous blueprints to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_blueprints_to_user(api_key_hash_value)
        
        # Convert string UUID to UUID object for SQLite compatibility
        try:
            blueprint_id_uuid = uuid.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")
        
        # Convert string UUID to UUID object for SQLite compatibility (user_id)
        user_id_uuid = None
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Load blueprint with ownership check
        query = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_id_uuid)
        if user_id_uuid:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBBlueprint.user_id == user_id_uuid,
                    DBBlueprint.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBBlueprint.api_key_hash == api_key_hash_value)
        
        blueprint = query.first()
        
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")
        
        # If blueprint was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and blueprint.user_id is None and blueprint.api_key_hash == api_key_hash_value:
            blueprint.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(blueprint)
        
        # Load all files in one query
        # blueprint_id_uuid is already converted above
        files = self.db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_id_uuid
        ).order_by(DBFile.filename).all()
        
        # Build response
        return BlueprintStructureResponse(
            blueprint=BlueprintResponse(
                blueprint_id=str(blueprint.blueprint_id),
                name=str(blueprint.name),  # type: ignore[arg-type]
                description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
                created_at=blueprint.created_at.isoformat(),
                updated_at=blueprint.updated_at.isoformat(),
                file_count=len(files),
                repository_url=blueprint.repository_url,
                default_branch=blueprint.default_branch or "main"
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
    
    def get_blueprint(
        self,
        blueprint_id: str,
        api_key: str
    ) -> BlueprintResponse:
        """
        Get single blueprint details.
        
        Args:
            blueprint_id: Blueprint ID
            api_key: API key for authentication
            
        Returns:
            BlueprintResponse with blueprint details
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # Migrate anonymous blueprints to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_blueprints_to_user(api_key_hash_value)
        
        # Convert string UUID to UUID object for SQLite compatibility
        try:
            blueprint_id_uuid = uuid.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")
        
        query = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_id_uuid)
        if user_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBBlueprint.user_id == user_id,
                    DBBlueprint.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBBlueprint.api_key_hash == api_key_hash_value)
        
        blueprint = query.first()
        
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")
        
        # If blueprint was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and blueprint.user_id is None and blueprint.api_key_hash == api_key_hash_value:
            blueprint.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(blueprint)

        file_count = self.db.query(DBFile).filter(DBFile.blueprint_id == blueprint_id_uuid).count()

        return self._blueprint_to_response(blueprint, file_count)
    
    def update_blueprint(
        self,
        blueprint_id: str,
        request: BlueprintUpdateRequest,
        api_key: str
    ) -> BlueprintResponse:
        """
        Update blueprint name and/or description.
        
        Args:
            blueprint_id: Blueprint ID
            request: Update request
            api_key: API key for authentication
            
        Returns:
            BlueprintResponse with updated blueprint details
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # Migrate anonymous blueprints to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_blueprints_to_user(api_key_hash_value)
        
        # Convert string UUID to UUID object for SQLite compatibility
        try:
            blueprint_id_uuid = uuid.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")
        
        # Convert string UUID to UUID object for SQLite compatibility (user_id)
        user_id_uuid = None
        if user_id:
            try:
                user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Load blueprint with ownership check
        query = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_id_uuid)
        if user_id_uuid:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    DBBlueprint.user_id == user_id_uuid,
                    DBBlueprint.api_key_hash == api_key_hash_value
                )
            )
        else:
            query = query.filter(DBBlueprint.api_key_hash == api_key_hash_value)
        
        blueprint = query.first()
        
        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")
        
        # If blueprint was found via api_key_hash but user is authenticated, migrate it now
        if self.current_user and blueprint.user_id is None and blueprint.api_key_hash == api_key_hash_value:
            blueprint.user_id = self.current_user.user_id
            self.db.commit()
            self.db.refresh(blueprint)
        
        # Validate at least one field is provided
        if request.name is None and request.description is None:
            raise HTTPException(status_code=400, detail="At least one field must be provided")
        
        # If name is provided, check uniqueness
        if request.name is not None:
            if len(request.name) < 1 or len(request.name) > 255:
                raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
            
            if request.name != blueprint.name:
                existing_query = self.db.query(DBBlueprint).filter(
                    func.lower(DBBlueprint.name) == request.name.lower(),
                    DBBlueprint.blueprint_id != blueprint_id_uuid
                )
                # Convert user_id to UUID if needed
                user_id_uuid_for_check = None
                if user_id:
                    try:
                        user_id_uuid_for_check = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                    except (ValueError, TypeError):
                        raise HTTPException(status_code=400, detail="Invalid user ID format")
                
                if user_id_uuid_for_check:
                    existing_query = existing_query.filter(DBBlueprint.user_id == user_id_uuid_for_check)
                else:
                    existing_query = existing_query.filter(DBBlueprint.api_key_hash == api_key_hash_value)
                
                existing = existing_query.first()
                
                if existing:
                    raise HTTPException(status_code=400, detail="Blueprint name already exists")
                
                blueprint.name = request.name  # type: ignore[assignment]
        
        # Update description if provided
        if request.description is not None:
            if len(request.description) > 1000:
                raise HTTPException(status_code=400, detail="Description too long (max 1000 characters)")
            blueprint.description = request.description  # type: ignore[assignment]
        
        # Update timestamp (SQLAlchemy handles this with onupdate)
        self.db.commit()
        self.db.refresh(blueprint)
        
        # Get file count
        file_count = self.db.query(DBFile).filter(DBFile.blueprint_id == blueprint_id_uuid).count()
        
        return BlueprintResponse(
            blueprint_id=str(blueprint.blueprint_id),
            name=str(blueprint.name),  # type: ignore[arg-type]
            description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
            created_at=blueprint.created_at.isoformat(),
            updated_at=blueprint.updated_at.isoformat(),
            file_count=file_count,
            repository_url=blueprint.repository_url,
            default_branch=blueprint.default_branch or "main"
        )
    
    async def initialize_blueprint(
        self,
        request: BlueprintInitRequest,
        api_key: str
    ) -> BlueprintInitResponse:
        """
        Initialize a new blueprint from GitHub.
        
        Args:
            request: Initialization request
            api_key: API key for authentication
            
        Returns:
            BlueprintInitResponse with setup status
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # 1. Create local blueprint record
        # Reuse create_blueprint logic but we need to adapt the request
        create_req = BlueprintCreateRequest(
            name=request.blueprint_name,
            description=request.description
        )
        
        # Create blueprint in DB
        blueprint_resp = self.create_blueprint(create_req, api_key)
        
        # Update repository info
        try:
            blueprint_uuid = uuid.UUID(blueprint_resp.blueprint_id)
        except (ValueError, TypeError):
             raise HTTPException(status_code=500, detail="Invalid blueprint ID format from creation")

        blueprint = self.db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_uuid).first()
        if not blueprint:
             raise HTTPException(status_code=500, detail="Failed to retrieve created blueprint")
             
        blueprint.repository_url = f"https://github.com/{request.owner}/{request.repo_name}"
        blueprint.installation_id = request.installation_id
        # We don't store owner/repo separately in the model currently, but URL is enough
        
        self.db.commit()
        self.db.refresh(blueprint)
        
        # 2. Initialize GitHub Repository
        gh_client = GitHubStatelessClient()
        
        try:
            # files to create
            files_to_create = [
                {
                    "path": "blueprint.yaml",
                    "content": f"""name: {request.blueprint_name}
version: 0.1.0
description: {request.description or ''}
zones:
  kernel:
    type: verified
    language: dafny
    path: kernel/
  shell:
    type: unverified
    language: python
    path: shell/
"""
                },
                {
                    "path": "kernel/Main.dfy",
                    "content": """method Main() {
  print "Hello from Verified Kernel!";
}
"""
                },
                {
                    "path": "shell/main.py",
                    "content": """def main():
    print("Hello from I/O Shell!")

if __name__ == "__main__":
    main()
"""
                },
                {
                    "path": ".github/workflows/verify.yml",
                    "content": """name: Verify Blueprint

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Dafny
      uses: dafny-lang/setup-dafny-action@v1.6.0
      with:
        dafny-version: '4.4.0'
    - name: Verify Kernel
      run: dafny verify kernel/Main.dfy
"""
                }
            ]
            
            # Get default branch SHA
            default_branch = await gh_client.get_default_branch(
                request.installation_id,
                request.owner,
                request.repo_name
            )
            
            ref_info = await gh_client.get_ref(
                request.installation_id,
                request.owner,
                request.repo_name,
                f"heads/{default_branch}"
            )
            base_sha = ref_info["object"]["sha"]
            
            # Create Tree
            tree_res = await gh_client.create_tree(
                request.installation_id,
                request.owner,
                request.repo_name,
                base_sha,
                files_to_create
            )
            
            # Create Commit
            commit_res = await gh_client.create_commit(
                request.installation_id,
                request.owner,
                request.repo_name,
                f"Initialize blueprint: {request.blueprint_name}",
                tree_res["sha"],
                [base_sha]
            )
            
            # Create Branch
            branch_name = f"feature/blueprint-init-{str(uuid.uuid4())[:8]}"
            await gh_client.create_ref(
                request.installation_id,
                request.owner,
                request.repo_name,
                f"refs/heads/{branch_name}",
                commit_res["sha"]
            )
            
            # Create PR
            pr_res = await gh_client.create_pull_request(
                request.installation_id,
                request.owner,
                request.repo_name,
                f"Initialize Blueprint: {request.blueprint_name}",
                "Setting up the Trusted Kernel Architecture structure.",
                branch_name,
                default_branch
            )
            
            return BlueprintInitResponse(
                blueprint=BlueprintResponse(
                    blueprint_id=str(blueprint.blueprint_id),
                    name=str(blueprint.name),  # type: ignore[arg-type]
                    description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
                    created_at=blueprint.created_at.isoformat(),
                    updated_at=blueprint.updated_at.isoformat(),
                    file_count=blueprint_resp.file_count,
                    repository_url=blueprint.repository_url,
                    default_branch=blueprint.default_branch or "main"
                ),
                github_url=pr_res["url"],
                commit_sha=commit_res["sha"],
                files_created=[f["path"] for f in files_to_create],
                setup_status="success"
            )
            
        except Exception as e:
            logger.error(f"GitHub initialization failed: {e}")
            # Ensure we return success partial if local DB creation worked
            return BlueprintInitResponse(
                blueprint=BlueprintResponse(
                    blueprint_id=str(blueprint.blueprint_id),
                    name=str(blueprint.name),  # type: ignore[arg-type]
                    description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
                    created_at=blueprint.created_at.isoformat(),
                    updated_at=blueprint.updated_at.isoformat(),
                    file_count=blueprint_resp.file_count,
                    repository_url=blueprint.repository_url,
                    default_branch=blueprint.default_branch or "main"
                ),
                github_url="",
                setup_status="partial"
            )

    def delete_blueprint(
        self,
        blueprint_id: str,
        api_key: str
    ) -> BlueprintDeleteResponse:
        """
        Delete a blueprint and all associated files atomically (cascade).
        
        Args:
            blueprint_id: Blueprint ID
            api_key: API key for authentication
            
        Returns:
            BlueprintDeleteResponse with deletion confirmation
        """
        user_id, api_key_hash_value = self._get_blueprint_owner_id(api_key)
        
        # Migrate anonymous blueprints to authenticated user if logged in
        if self.current_user and api_key_hash_value:
            self._migrate_anonymous_blueprints_to_user(api_key_hash_value)
        
        # Determine owner identifier
        if user_id:
            owner_id = user_id
        elif api_key_hash_value:
            owner_id = api_key_hash_value
        else:
            raise HTTPException(status_code=403, detail="Authentication required")
        
        # 1. I/O: Load blueprint + all its files for cascade deletion
        owner_filter = get_blueprint_owner_filter(self.current_user, api_key_hash_value)
        state = adapters.build_scoped_state(
            blueprint_id=blueprint_id,
            owner_filter=owner_filter,
            db=self.db
        )
        
        # Count files before deletion (for response)
        file_count = len([f for f in state.files.values() if f.blueprint_id == blueprint_id])
        
        # 2. CORE: Call pure logic (cascade handled in Core)
        new_state, result = blueprint_management.delete_blueprint_core(
            state,
            blueprint_id,
            owner_id
        )
        
        # 3. ADAPTER: Apply diff and map errors
        if not result.success:
            status_code = self._map_error_to_status(result.error_kind or "Precondition")
            raise HTTPException(status_code=status_code, detail=result.error_message)
        
        adapters.apply_state_diff(self.db, state, new_state)
        self.db.commit()
        
        return BlueprintDeleteResponse(
            deleted=True,
            blueprint_id=str(blueprint_id),
            files_deleted=file_count
        )
    
    def _get_blueprint_owner_id(
        self,
        api_key: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get blueprint owner identifier (user_id or api_key_hash).
        
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
    
    def _migrate_anonymous_blueprints_to_user(self, api_key_hash_value: str) -> int:
        """
        Migrate anonymous blueprints to authenticated user.
        
        Args:
            api_key_hash_value: API key hash
            
        Returns:
            Number of blueprints migrated
        """
        # 1. I/O: Fetch snapshot (all blueprints and files for full state)
        blueprints = self.db.query(DBBlueprint).all()
        files = self.db.query(DBFile).all()
        
        # 2. ADAPTER: Build SystemState from SQLAlchemy objects
        old_state = adapters.build_system_state(blueprints, files)
        
        # Count blueprints that will be migrated (before migration)
        # blueprints_to_migrate = [
        #     p for p in blueprints
        #     if p.api_key_hash == api_key_hash_value and p.user_id is None
        # ]
        # migrated_count = len(blueprints_to_migrate)
        
        # 3. CORE: Call pure logic (matches Dafny MigrateAnonymousBlueprints)
        new_state = migration.migrate_anonymous_projects(
            old_state,
            str(self.current_user.user_id),
            api_key_hash_value
        )
        
        # Calculate diff to see how many were actually changed
        migrated_count = 0
        for pid, bp in new_state.blueprints.items():
            if bp.owner.is_authenticated() and bp.owner.user_id == str(self.current_user.user_id):
                 if pid in old_state.blueprints and old_state.blueprints[pid].owner.is_anonymous():
                     migrated_count += 1
        
        if migrated_count == 0:
            return 0

        # 4. ADAPTER: Apply state diff back to database
        adapters.apply_state_diff(self.db, old_state, new_state)
        
        # 5. I/O: Commit changes
        self.db.commit()
        
        logger.info(f"Migrated {migrated_count} anonymous blueprints to user {self.current_user.user_id}")
        return migrated_count

    def _blueprint_to_response(
        self,
        blueprint: DBBlueprint,
        file_count: Optional[int] = None
    ) -> BlueprintResponse:
        """
        Convert DBBlueprint to BlueprintResponse with Brain architecture fields.

        Args:
            blueprint: Database blueprint object
            file_count: Optional file count (if not provided, will be calculated)

        Returns:
            BlueprintResponse
        """
        # Calculate file count if not provided
        if file_count is None:
            file_count = self.db.query(DBFile).filter(DBFile.blueprint_id == blueprint.blueprint_id).count()

        return BlueprintResponse(
            blueprint_id=str(blueprint.blueprint_id),
            name=str(blueprint.name),  # type: ignore[arg-type]
            description=str(blueprint.description) if blueprint.description else None,  # type: ignore[arg-type]
            created_at=blueprint.created_at.isoformat(),
            updated_at=blueprint.updated_at.isoformat(),
            file_count=file_count,
            redirect_url=f"/app/{blueprint.blueprint_id}",
            repository_url=blueprint.repository_url,
            default_branch=blueprint.default_branch or "main",
            component_uuid=blueprint.component_uuid,
            registry_path=blueprint.registry_path,
            sync_status=blueprint.sync_status or "clean"
        )

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

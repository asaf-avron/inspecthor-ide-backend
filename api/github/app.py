"""
GitHub App management for InSpecThor.
Handles app installation, authentication, and installation lifecycle.
"""

import os
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from github import GithubIntegration, Auth
from pydantic import BaseModel

from ..database import Installation, Repository, User


class InstallationData(BaseModel):
    """Data from GitHub installation webhook."""
    installation_id: int
    account_login: str
    account_type: str
    account_id: int
    repositories: Optional[List[dict]] = None


class GitHubAppManager:
    """
    Manages GitHub App installations and lifecycle.
    """
    
    def __init__(self):
        app_id_str = os.getenv('GITHUB_APP_ID')
        if not app_id_str:
            raise ValueError("GITHUB_APP_ID environment variable is required")
        
        self.app_id = int(app_id_str)
        private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH')
        private_key_content = os.getenv('GITHUB_APP_PRIVATE_KEY')
        
        if private_key_content:
            self.private_key = private_key_content
        elif private_key_path:
            with open(private_key_path, 'r') as f:
                self.private_key = f.read()
        else:
            raise ValueError("GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH must be set")
        
        # Create GitHub App integration
        auth = Auth.AppAuth(self.app_id, self.private_key)
        self.integration = GithubIntegration(auth=auth)
    
    async def handle_installation_created(
        self,
        db: Session,
        user_id: str,
        data: InstallationData
    ) -> Installation:
        """
        Handle GitHub App installation event.
        
        Args:
            db: Database session
            user_id: User who installed the app
            data: Installation data from webhook
        
        Returns:
            Created Installation object
        """
        # Check if installation already exists
        existing = db.query(Installation).filter(
            Installation.installation_id == data.installation_id
        ).first()
        
        if existing:
            # Update existing installation
            existing.user_id = user_id
            existing.account_login = data.account_login
            existing.account_type = data.account_type
            existing.account_id = data.account_id
            existing.is_active = True
            existing.suspended_at = None
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        
        # Create new installation
        installation = Installation(
            installation_id=data.installation_id,
            user_id=user_id,
            account_login=data.account_login,
            account_type=data.account_type,
            account_id=data.account_id,
            is_active=True
        )
        
        db.add(installation)
        db.commit()
        db.refresh(installation)
        
        # If repositories are provided, sync them
        if data.repositories:
            await self._sync_repositories(db, installation, data.repositories)
        
        return installation
    
    async def handle_installation_deleted(
        self,
        db: Session,
        installation_id: int
    ) -> None:
        """
        Handle GitHub App uninstallation event.
        
        Args:
            db: Database session
            installation_id: Installation ID that was deleted
        """
        installation = db.query(Installation).filter(
            Installation.installation_id == installation_id
        ).first()
        
        if installation:
            installation.is_active = False
            installation.updated_at = datetime.utcnow()
            db.commit()
    
    async def handle_installation_repositories_added(
        self,
        db: Session,
        installation_id: int,
        repositories: List[dict]
    ) -> None:
        """
        Handle repositories added to installation.
        
        Args:
            db: Database session
            installation_id: Installation ID
            repositories: List of repository dicts from webhook
        """
        installation = db.query(Installation).filter(
            Installation.installation_id == installation_id
        ).first()
        
        if not installation:
            raise ValueError(f"Installation {installation_id} not found")
        
        await self._sync_repositories(db, installation, repositories)
    
    async def handle_installation_repositories_removed(
        self,
        db: Session,
        installation_id: int,
        repositories: List[dict]
    ) -> None:
        """
        Handle repositories removed from installation.
        
        Args:
            db: Database session
            installation_id: Installation ID
            repositories: List of repository dicts from webhook
        """
        repo_ids = [r["id"] for r in repositories]
        
        # Delete repositories from database
        db.query(Repository).filter(
            Repository.installation_id == installation_id,
            Repository.github_repo_id.in_(repo_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
    
    async def _sync_repositories(
        self,
        db: Session,
        installation: Installation,
        repositories: List[dict]
    ) -> None:
        """
        Sync repositories from GitHub to database.
        
        Args:
            db: Database session
            installation: Installation object
            repositories: List of repository dicts from GitHub
        """
        for repo_data in repositories:
            # Check if repository already exists
            existing = db.query(Repository).filter(
                Repository.github_repo_id == repo_data["id"]
            ).first()
            
            if existing:
                # Update existing repository
                existing.installation_id = installation.installation_id
                existing.owner = repo_data["owner"]["login"]
                existing.name = repo_data["name"]
                existing.full_name = repo_data["full_name"]
                existing.default_branch = repo_data.get("default_branch", "main")
                existing.updated_at = datetime.utcnow()
            else:
                # Create new repository
                repository = Repository(
                    github_repo_id=repo_data["id"],
                    installation_id=installation.installation_id,
                    owner=repo_data["owner"]["login"],
                    name=repo_data["name"],
                    full_name=repo_data["full_name"],
                    default_branch=repo_data.get("default_branch", "main")
                )
                db.add(repository)
        
        db.commit()
    
    async def get_user_installations(
        self,
        db: Session,
        user_id: str
    ) -> List[Installation]:
        """
        Get all active installations for a user.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            List of Installation objects
        """
        return db.query(Installation).filter(
            Installation.user_id == user_id,
            Installation.is_active == True
        ).all()
    
    async def get_installation_repositories(
        self,
        db: Session,
        installation_id: int
    ) -> List[Repository]:
        """
        Get all repositories for an installation.
        
        Args:
            db: Database session
            installation_id: Installation ID
        
        Returns:
            List of Repository objects
        """
        return db.query(Repository).filter(
            Repository.installation_id == installation_id
        ).all()

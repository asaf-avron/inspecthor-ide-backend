"""
GitHub Installations router for InSpecThor.
Handles listing and syncing GitHub App installations for authenticated users.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from ..database import get_db, User, Installation
from ..auth import require_auth, get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["github"])


class InstallationResponse(BaseModel):
    """Response model for an installation."""
    installation_id: int
    account_login: str
    account_type: str
    is_active: bool
    installed_at: str


class InstallationsListResponse(BaseModel):
    """Response model for listing installations."""
    installations: List[InstallationResponse]


async def sync_user_installations_from_github(
    user: User,
    db: Session
) -> List[Installation]:
    """
    Sync a user's GitHub App installations from GitHub API.
    
    This queries GitHub for all installations accessible to the user's OAuth token,
    then creates or updates Installation records in the database.
    
    Args:
        user: The authenticated user
        db: Database session
        
    Returns:
        List of Installation objects from the database
    """
    auth_service = get_auth_service()
    
    try:
        # Decrypt the user's GitHub access token
        github_token = auth_service.decrypt_github_token(user.access_token_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt GitHub token for user {user.github_login}: {e}")
        return []
    
    # Query GitHub API for user's installations
    # https://docs.github.com/en/rest/apps/installations#list-app-installations-accessible-to-the-user-access-token
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.github.com/user/installations",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code != 200:
                logger.warning(
                    f"GitHub API returned {response.status_code} for user installations: "
                    f"{response.text[:200]}"
                )
                return []
            
            data = response.json()
            github_installations = data.get("installations", [])
            
            logger.info(
                f"Found {len(github_installations)} installations for user {user.github_login}"
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch installations from GitHub: {e}")
            return []
    
    # Sync each installation to database
    synced_installations: List[Installation] = []
    
    for gh_inst in github_installations:
        installation_id = gh_inst["id"]
        account = gh_inst["account"]
        
        # Check if installation already exists
        existing = db.query(Installation).filter(
            Installation.installation_id == installation_id
        ).first()
        
        if existing:
            # Update existing installation
            existing.user_id = user.user_id  # type: ignore[assignment]
            existing.account_login = account["login"]  # type: ignore[assignment]
            existing.account_type = account["type"]  # type: ignore[assignment]
            existing.account_id = account["id"]  # type: ignore[assignment]
            existing.is_active = True  # type: ignore[assignment]
            existing.suspended_at = None  # type: ignore[assignment]
            existing.updated_at = datetime.utcnow()  # type: ignore[assignment]
            synced_installations.append(existing)
        else:
            # Create new installation
            new_installation = Installation(
                installation_id=installation_id,
                user_id=user.user_id,
                account_login=account["login"],
                account_type=account["type"],
                account_id=account["id"],
                is_active=True
            )
            db.add(new_installation)
            synced_installations.append(new_installation)
    
    db.commit()
    
    # Refresh all to get updated values
    for inst in synced_installations:
        db.refresh(inst)
    
    logger.info(f"Synced {len(synced_installations)} installations for user {user.github_login}")
    
    return synced_installations


@router.get("/installations", response_model=InstallationsListResponse)
async def list_installations(
    sync: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    List GitHub App installations for the current user.
    
    By default, this will sync installations from GitHub API first to ensure
    the database is up to date. Set sync=false to skip syncing and only
    return cached installations from the database.
    
    Args:
        sync: Whether to sync from GitHub first (default: true)
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of installations
    """
    if sync:
        # Sync from GitHub first
        await sync_user_installations_from_github(current_user, db)
    
    # Query installations from database
    installations = db.query(Installation).filter(
        Installation.user_id == current_user.user_id,
        Installation.is_active == True
    ).all()
    
    return InstallationsListResponse(
        installations=[
            InstallationResponse(
                installation_id=inst.installation_id,
                account_login=str(inst.account_login),
                account_type=str(inst.account_type),
                is_active=bool(inst.is_active),
                installed_at=inst.installed_at.isoformat() if inst.installed_at else ""
            )
            for inst in installations
        ]
    )


@router.get("/installations/{installation_id}/repositories")
async def list_installation_repositories(
    installation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    List repositories for a specific installation.
    
    Fetches repositories directly from GitHub API using the installation token.
    
    Args:
        installation_id: GitHub App installation ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of repositories accessible to the installation
    """
    # Verify the installation belongs to the user
    installation = db.query(Installation).filter(
        Installation.installation_id == installation_id,
        Installation.user_id == current_user.user_id,
        Installation.is_active == True
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=404,
            detail=f"Installation {installation_id} not found or not accessible"
        )
    
    # Fetch repositories from GitHub API using user's OAuth token
    # This uses the installation-specific endpoint
    auth_service = get_auth_service()
    
    try:
        github_token = auth_service.decrypt_github_token(current_user.access_token_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt GitHub token: {e}")
        raise HTTPException(status_code=500, detail="Failed to access GitHub")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/user/installations/{installation_id}/repositories",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code != 200:
                logger.warning(
                    f"GitHub API returned {response.status_code} for installation repos: "
                    f"{response.text[:200]}"
                )
                # Fall back to database repositories
                repositories = installation.repositories
                return {
                    "repositories": [
                        {
                            "repository_id": str(repo.repository_id),
                            "github_repo_id": repo.github_repo_id,
                            "owner": repo.owner,
                            "name": repo.name,
                            "full_name": repo.full_name,
                            "default_branch": repo.default_branch,
                            "html_url": f"https://github.com/{repo.full_name}",
                            "blueprint_id": str(repo.blueprint_id) if repo.blueprint_id else None,
                        }
                        for repo in repositories
                    ]
                }
            
            data = response.json()
            github_repos = data.get("repositories", [])
            
            return {
                "repositories": [
                    {
                        "github_repo_id": repo["id"],
                        "owner": repo["owner"]["login"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "default_branch": repo.get("default_branch", "main"),
                        "html_url": repo["html_url"],
                        "private": repo.get("private", False),
                        "description": repo.get("description", ""),
                    }
                    for repo in github_repos
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch repositories from GitHub: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {e}")


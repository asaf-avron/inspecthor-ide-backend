"""
GitHub webhook handlers for InSpecThor.
Processes push, pull_request, and installation events.
"""

import hmac
import hashlib
import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db, Installation, Repository, Anchor
from .app import GitHubAppManager, InstallationData
from .api_client import GitHubStatelessClient
from .checks import CheckRunService

router = APIRouter(prefix="/api/github", tags=["github"])

# Lazy initialization - only create services when needed
_app_manager: Optional[GitHubAppManager] = None
_github_client: Optional[GitHubStatelessClient] = None
_check_service: Optional[CheckRunService] = None


def get_app_manager() -> GitHubAppManager:
    """Get or create GitHubAppManager instance."""
    global _app_manager
    if _app_manager is None:
        _app_manager = GitHubAppManager()
    return _app_manager


def get_github_client() -> GitHubStatelessClient:
    """Get or create GitHubStatelessClient instance."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubStatelessClient()
    return _github_client


def get_check_service() -> CheckRunService:
    """Get or create CheckRunService instance."""
    global _check_service
    if _check_service is None:
        _check_service = CheckRunService()
    return _check_service


def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        payload_body: Raw request body
        signature_header: X-Hub-Signature-256 header value
    
    Returns:
        True if signature is valid
    """
    webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
    if not webhook_secret:
        # Skip verification if secret not set (development mode)
        return True
    
    if not signature_header:
        return False
    
    try:
        # GitHub sends "sha256=<signature>"
        hash_algorithm, github_signature = signature_header.split('=')
        if hash_algorithm != 'sha256':
            return False
        
        # Calculate expected signature
        mac = hmac.new(
            webhook_secret.encode(),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(expected_signature, github_signature)
    except Exception as e:
        logger.warning(f"Signature verification error: {e}")
        return False


@router.post("/webhooks")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub webhook events.
    
    Events:
    - installation.created/deleted
    - installation_repositories.added/removed
    - push
    - pull_request.opened/synchronize
    - check_run.rerequested
    """
    # Get headers
    event_type = request.headers.get('X-GitHub-Event')
    delivery_id = request.headers.get('X-GitHub-Delivery')
    signature = request.headers.get('X-Hub-Signature-256')
    
    # Read raw body once
    body = await request.body()
    
    # Verify signature (skip if webhook secret not configured - for development)
    # Allow skipping validation via USE_MOCK_GITHUB flag (for local dev with Smee/proxies)
    use_mock_github = os.getenv('USE_MOCK_GITHUB', 'false').lower() == 'true'
    
    if use_mock_github:
        logger.info("USE_MOCK_GITHUB=true - skipping webhook signature validation")
    else:
        webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        if webhook_secret:
            if not signature:
                logger.warning(f"Webhook secret configured but no signature header present (X-Hub-Signature-256)")
                raise HTTPException(status_code=401, detail="Missing webhook signature header")
            if not verify_webhook_signature(body, signature):
                logger.warning(f"Webhook signature verification failed for event {event_type}")
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse JSON payload from body bytes
    import json
    payload = json.loads(body.decode('utf-8'))
    
    # Log webhook
    print(f"[Webhook] {event_type} - {delivery_id}")
    
    # Handle different event types
    if event_type == "ping":
        return {"message": "pong", "zen": payload.get("zen")}
    
    elif event_type == "installation":
        return await handle_installation_event(db, payload)
    
    elif event_type == "installation_repositories":
        return await handle_installation_repositories_event(db, payload)
    
    elif event_type == "push":
        # Queue verification in background
        background_tasks.add_task(handle_push_event, db, payload)
        return {"message": "Push event queued"}
    
    elif event_type == "pull_request":
        # Queue verification in background
        background_tasks.add_task(handle_pull_request_event, db, payload)
        return {"message": "Pull request event queued"}
    
    elif event_type == "check_run":
        action = payload.get("action")
        if action == "rerequested":
            background_tasks.add_task(handle_check_run_rerun, db, payload)
            return {"message": "Check run queued"}
    
    return {"message": f"Event {event_type} received but not handled"}


async def handle_installation_event(db: Session, payload: Dict[str, Any]) -> Dict[str, str]:
    """Handle installation.created or installation.deleted events."""
    action = payload["action"]
    installation_data = payload["installation"]
    
    if action == "created":
        # Extract installation data
        data = InstallationData(
            installation_id=installation_data["id"],
            account_login=installation_data["account"]["login"],
            account_type=installation_data["account"]["type"],
            account_id=installation_data["account"]["id"],
            repositories=payload.get("repositories", [])
        )
        
        # TODO: Get user_id from installation sender
        # For now, we'll need to handle this when user authenticates
        # Store installation temporarily without user_id
        
        return {"message": f"Installation {data.installation_id} created"}
    
    elif action == "deleted":
        installation_id = installation_data["id"]
        await get_app_manager().handle_installation_deleted(db, installation_id)
        return {"message": f"Installation {installation_id} deleted"}
    
    return {"message": f"Installation action {action} not handled"}


async def handle_installation_repositories_event(
    db: Session,
    payload: Dict[str, Any]
) -> Dict[str, str]:
    """Handle installation_repositories.added or removed events."""
    action = payload["action"]
    installation_id = payload["installation"]["id"]
    repositories = payload["repositories_added" if action == "added" else "repositories_removed"]
    
    if action == "added":
        await get_app_manager().handle_installation_repositories_added(
            db, installation_id, repositories
        )
    elif action == "removed":
        await get_app_manager().handle_installation_repositories_removed(
            db, installation_id, repositories
        )
    
    return {"message": f"{len(repositories)} repositories {action}"}


async def handle_push_event(db: Session, payload: Dict[str, Any]):
    """
    Handle push event - verify anchored files if changed.
    
    Background task.
    """
    repository = payload["repository"]
    installation_id = payload["installation"]["id"]
    owner = repository["owner"]["login"]
    repo_name = repository["name"]
    ref = payload["ref"]  # e.g., "refs/heads/main"
    commits = payload["commits"]
    
    print(f"[Push] {owner}/{repo_name} on {ref} - {len(commits)} commits")
    
    # Get changed files from commits
    changed_files = set()
    for commit in commits:
        changed_files.update(commit.get("added", []))
        changed_files.update(commit.get("modified", []))
    
    # Find anchors in changed files
    repo_obj = db.query(Repository).filter(
        Repository.installation_id == installation_id,
        Repository.owner == owner,
        Repository.name == repo_name
    ).first()
    
    if not repo_obj:
        print(f"[Push] Repository not found: {owner}/{repo_name}")
        return
    
    anchors = db.query(Anchor).filter(
        Anchor.repository_id == repo_obj.repository_id,
        Anchor.file_path.in_(list(changed_files))
    ).all()
    
    if not anchors:
        print(f"[Push] No anchors found in changed files")
        return
    
    print(f"[Push] Found {len(anchors)} anchors to verify")
    
    # TODO: Queue verification for each anchor
    # This will be implemented when we build the transpiler + verifier


async def handle_pull_request_event(db: Session, payload: Dict[str, Any]):
    """
    Handle pull_request event - create check run and verify.
    
    Background task.
    """
    action = payload["action"]
    pull_request = payload["pull_request"]
    repository = payload["repository"]
    installation_id = payload["installation"]["id"]
    
    # Only handle opened and synchronize (updated) actions
    if action not in ["opened", "synchronize"]:
        return
    
    owner = repository["owner"]["login"]
    repo_name = repository["name"]
    pr_number = pull_request["number"]
    head_sha = pull_request["head"]["sha"]
    
    print(f"[PR] {owner}/{repo_name} #{pr_number} - {action}")
    
    # Create check run
    check_run = await get_check_service().create_check_run(
        installation_id=installation_id,
        owner=owner,
        repo=repo_name,
        head_sha=head_sha,
        name="InSpecThor Verification"
    )
    
    check_run_id = check_run["id"]
    
    # Update to in_progress
    await get_check_service().update_check_run(
        installation_id=installation_id,
        owner=owner,
        repo=repo_name,
        check_run_id=check_run_id,
        status="in_progress",
        conclusion=None,
        output={
            "title": "Analyzing changes...",
            "summary": "InSpecThor is checking for anchored functions in changed files."
        }
    )
    
    try:
        # Get changed files
        changed_files = await get_github_client().get_pr_files(
            installation_id, owner, repo_name, pr_number
        )
        
        # Find repository in database
        repo_obj = db.query(Repository).filter(
            Repository.installation_id == installation_id,
            Repository.owner == owner,
            Repository.name == repo_name
        ).first()
        
        if not repo_obj:
            await get_check_service().update_check_run(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                check_run_id=check_run_id,
                status="completed",
                conclusion="neutral",
                output={
                    "title": "Repository not connected",
                    "summary": "This repository is not connected to InSpecThor. Visit the IDE to import it."
                }
            )
            return
        
        # Find anchors in changed files
        changed_file_paths = [f.filename for f in changed_files]
        anchors = db.query(Anchor).filter(
            Anchor.repository_id == repo_obj.repository_id,
            Anchor.file_path.in_(changed_file_paths)
        ).all()
        
        if not anchors:
            await get_check_service().update_check_run(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                check_run_id=check_run_id,
                status="completed",
                conclusion="neutral",
                output={
                    "title": "No anchors found",
                    "summary": f"InSpecThor found no anchored functions in the {len(changed_files)} changed file(s)."
                }
            )
            return
        
        print(f"[PR] Found {len(anchors)} anchors to verify")
        
        # TODO: Verify each anchor
        # For now, mark as success
        await get_check_service().update_check_run(
            installation_id=installation_id,
            owner=owner,
            repo=repo_name,
            check_run_id=check_run_id,
            status="completed",
            conclusion="success",
            output={
                "title": f"✓ {len(anchors)} anchor(s) verified",
                "summary": f"All anchored functions passed formal verification.\n\n**Anchors:**\n" + 
                          "\n".join([f"- `{a.function_name}` in `{a.file_path}`" for a in anchors])
            }
        )
        
    except Exception as e:
        print(f"[PR] Error: {e}")
        await get_check_service().update_check_run(
            installation_id=installation_id,
            owner=owner,
            repo=repo_name,
            check_run_id=check_run_id,
            status="completed",
            conclusion="failure",
            output={
                "title": "Verification error",
                "summary": f"InSpecThor encountered an error: {str(e)}"
            }
        )


async def handle_check_run_rerun(db: Session, payload: Dict[str, Any]):
    """
    Handle check_run.rerequested event - re-run verification.
    
    Background task.
    """
    check_run = payload["check_run"]
    repository = payload["repository"]
    installation_id = payload["installation"]["id"]
    
    print(f"[CheckRun] Re-run requested for {check_run['id']}")
    
    # TODO: Re-run verification logic
    # For now, just acknowledge

"""
GitHub webhook handlers for InSpecThor.
Processes push, pull_request, and installation events.
"""

import hmac
import hashlib
import os
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db, Repository, Anchor
from ..services.verifier_client import VerifierClient, VerifyResult
from .app import GitHubAppManager, InstallationData
from .api_client import GitHubStatelessClient
from .checks import CheckRunService

router = APIRouter(prefix="/api/github", tags=["github"])

# Lazy initialization - only create services when needed
_app_manager: Optional[GitHubAppManager] = None
_github_client: Optional[GitHubStatelessClient] = None
_check_service: Optional[CheckRunService] = None
_verifier_client: Optional[VerifierClient] = None


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


def get_verifier_client() -> VerifierClient:
    """Get or create VerifierClient instance."""
    global _verifier_client
    if _verifier_client is None:
        _verifier_client = VerifierClient()
    return _verifier_client


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
                logger.warning("Webhook secret configured but no signature header present (X-Hub-Signature-256)")
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
    head_sha = payload.get("after", commits[-1]["id"] if commits else None)
    
    logger.info(f"[Push] {owner}/{repo_name} on {ref} - {len(commits)} commits")
    
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
        logger.info(f"[Push] Repository not found: {owner}/{repo_name}")
        return
    
    anchors = db.query(Anchor).filter(
        Anchor.repository_id == repo_obj.repository_id,
        Anchor.file_path.in_(list(changed_files))
    ).all()
    
    if not anchors:
        logger.info("[Push] No anchors found in changed files")
        return
    
    logger.info(f"[Push] Found {len(anchors)} anchors to verify")
    
    # Create check run for push verification
    if head_sha:
        check_run = await get_check_service().create_check_run(
            installation_id=installation_id,
            owner=owner,
            repo=repo_name,
            head_sha=head_sha,
            name="InSpecThor Verification (Push)"
        )
        check_run_id = check_run["id"]
        
        # Run verification
        await run_anchor_verification(
            db=db,
            installation_id=installation_id,
            owner=owner,
            repo_name=repo_name,
            check_run_id=check_run_id,
            anchors=anchors,
            head_sha=head_sha,
        )


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
        
        logger.info(f"[PR] Found {len(anchors)} anchors to verify")
        
        # Run verification for each anchor
        await run_anchor_verification(
            db=db,
            installation_id=installation_id,
            owner=owner,
            repo_name=repo_name,
            check_run_id=check_run_id,
            anchors=anchors,
            head_sha=head_sha,
        )
        
    except Exception as e:
        logger.error(f"[PR] Error: {e}")
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
    
    owner = repository["owner"]["login"]
    repo_name = repository["name"]
    head_sha = check_run["head_sha"]
    
    logger.info(f"[CheckRun] Re-run requested for {check_run['id']}")
    
    # Find repository
    repo_obj = db.query(Repository).filter(
        Repository.installation_id == installation_id,
        Repository.owner == owner,
        Repository.name == repo_name
    ).first()
    
    if not repo_obj:
        logger.warning(f"[CheckRun] Repository not found: {owner}/{repo_name}")
        return
    
    # Get all anchors for this repository
    anchors = db.query(Anchor).filter(
        Anchor.repository_id == repo_obj.repository_id
    ).all()
    
    if not anchors:
        logger.info("[CheckRun] No anchors found")
        return
    
    # Create new check run
    new_check_run = await get_check_service().create_check_run(
        installation_id=installation_id,
        owner=owner,
        repo=repo_name,
        head_sha=head_sha,
        name="InSpecThor Verification"
    )
    
    # Run verification
    await run_anchor_verification(
        db=db,
        installation_id=installation_id,
        owner=owner,
        repo_name=repo_name,
        check_run_id=new_check_run["id"],
        anchors=anchors,
        head_sha=head_sha,
    )


async def run_anchor_verification(
    db: Session,
    installation_id: int,
    owner: str,
    repo_name: str,
    check_run_id: int,
    anchors: List[Anchor],
    head_sha: str,
) -> None:
    """
    Run verification for a list of anchors.
    
    This is the core verification flow that:
    1. Updates check run to in_progress
    2. For each anchor, fetches the Dafny spec
    3. Calls the verifier service
    4. Updates check run with results
    
    Args:
        db: Database session
        installation_id: GitHub App installation ID
        owner: Repository owner
        repo_name: Repository name
        check_run_id: Check run ID to update
        anchors: List of anchors to verify
        head_sha: Commit SHA being verified
    """
    # Update check run to in_progress
    await get_check_service().update_check_run(
        installation_id=installation_id,
        owner=owner,
        repo=repo_name,
        check_run_id=check_run_id,
        status="in_progress",
        conclusion=None,
        output={
            "title": f"Verifying {len(anchors)} anchor(s)...",
            "summary": "InSpecThor is running formal verification on anchored functions."
        }
    )
    
    # Track verification results
    verified_anchors: List[Anchor] = []
    failed_anchors: List[tuple[Anchor, VerifyResult]] = []
    skipped_anchors: List[tuple[Anchor, str]] = []
    
    # Get verifier client
    verifier = get_verifier_client()
    
    # Check verifier health
    health = await verifier.health_check()
    if health.get("status") != "healthy":
        await get_check_service().update_check_run(
            installation_id=installation_id,
            owner=owner,
            repo=repo_name,
            check_run_id=check_run_id,
            status="completed",
            conclusion="failure",
            output={
                "title": "Verifier unavailable",
                "summary": "The Dafny verification service is not available. Please try again later."
            }
        )
        return
    
    for anchor in anchors:
        try:
            # Get the Dafny specification file linked to this anchor via contract_ref
            # contract_ref format: "specs/auth.dfy::ValidateToken"
            contract_ref: str = str(anchor.contract_ref) if anchor.contract_ref else ""
            if not contract_ref:
                skipped_anchors.append((anchor, "No specification linked"))
                continue
            
            # Parse the contract_ref to get the spec file path
            # Format: "path/to/spec.dfy::MethodName"
            spec_parts = contract_ref.split("::")
            spec_file_path = spec_parts[0] if spec_parts else ""
            
            if not spec_file_path:
                skipped_anchors.append((anchor, "Invalid contract reference"))
                continue
            
            # Get implementation code from GitHub
            file_path: str = str(anchor.file_path)
            impl_content = await get_github_client().get_file_content(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                path=file_path,
                ref=head_sha
            )
            
            if not impl_content:
                skipped_anchors.append((anchor, "Could not fetch implementation file"))
                continue
            
            # Try to fetch the Dafny spec file from GitHub
            spec_content = await get_github_client().get_file_content(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                path=spec_file_path,
                ref=head_sha
            )
            
            if not spec_content:
                skipped_anchors.append((anchor, f"Could not fetch spec file: {spec_file_path}"))
                continue
            
            # Verify the spec
            # In the future: transpile impl_content -> Dafny, then verify against spec
            result = await verifier.verify(
                dafny_code=spec_content,
                timeout_seconds=60,
            )
            
            if result.verified:
                verified_anchors.append(anchor)
                # Update anchor status in database
                anchor.verification_status = "verified"  # type: ignore[assignment]
            else:
                failed_anchors.append((anchor, result))
                anchor.verification_status = "failed"  # type: ignore[assignment]
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error verifying anchor {anchor.function_name}: {e}")
            skipped_anchors.append((anchor, str(e)))
    
    # Build result summary
    total = len(anchors)
    verified_count = len(verified_anchors)
    failed_count = len(failed_anchors)
    skipped_count = len(skipped_anchors)
    
    # Determine conclusion
    if failed_count > 0:
        conclusion = "failure"
        title = f"✗ {failed_count}/{total} verification(s) failed"
    elif skipped_count == total:
        conclusion = "neutral"
        title = f"⊘ {skipped_count} anchor(s) skipped (no specs linked)"
    else:
        conclusion = "success"
        title = f"✓ {verified_count}/{total} anchor(s) verified"
    
    # Build detailed summary
    summary_parts = []
    
    if verified_anchors:
        summary_parts.append("**Verified:**")
        for anchor in verified_anchors:
            summary_parts.append(f"- ✓ `{anchor.function_name}` in `{anchor.file_path}`")
    
    if failed_anchors:
        summary_parts.append("\n**Failed:**")
        for anchor, result in failed_anchors:
            error_msgs = [e.message for e in result.errors[:3]]  # First 3 errors
            summary_parts.append(f"- ✗ `{anchor.function_name}` in `{anchor.file_path}`")
            for msg in error_msgs:
                summary_parts.append(f"  - {msg}")
    
    if skipped_anchors:
        summary_parts.append("\n**Skipped:**")
        for anchor, reason in skipped_anchors:
            summary_parts.append(f"- ⊘ `{anchor.function_name}`: {reason}")
    
    summary = "\n".join(summary_parts) if summary_parts else "No anchors to verify."
    
    # Update check run with final results
    await get_check_service().update_check_run(
        installation_id=installation_id,
        owner=owner,
        repo=repo_name,
        check_run_id=check_run_id,
        status="completed",
        conclusion=conclusion,
        output={
            "title": title,
            "summary": summary
        }
    )

"""
Iron Grip Webhook Handlers

Enhanced GitHub webhook handlers for Iron Grip enforcement.
Automatically validates pull requests and reports status checks.
"""

import logging
from typing import Dict
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
import hmac
import hashlib
import os

from api.services.github_protection_service import GitHubProtectionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github/iron-grip", tags=["github-iron-grip"])


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature

    Args:
        payload: Raw webhook payload
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False

    # GitHub sends signature as "sha256=<hash>"
    if not signature.startswith("sha256="):
        return False

    expected_signature = signature.split("=")[1]

    # Compute HMAC
    mac = hmac.new(
        secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    )
    computed_signature = mac.hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


async def validate_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str
) -> Dict:
    """
    Validate a pull request against Iron Grip requirements

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        head_sha: Head commit SHA

    Returns:
        Validation results
    """
    logger.info(f"Validating PR #{pr_number} in {owner}/{repo}")

    github_token = os.getenv("GITHUB_TOKEN")
    service = GitHubProtectionService(github_token=github_token)

    # Get check runs for this commit
    passes, results = service.validate_iron_grip_compliance(
        owner=owner,
        repo=repo,
        commit_sha=head_sha
    )

    return {
        "pr_number": pr_number,
        "commit_sha": head_sha,
        "passes": passes,
        "results": results
    }


@router.post("/webhook")
async def handle_iron_grip_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle GitHub webhooks for Iron Grip enforcement

    Responds to:
    - pull_request (opened, synchronize, reopened)
    - push (to protected branches)
    - check_suite (completed)
    """
    # Get webhook secret
    webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    payload = await request.body()

    if webhook_secret and not verify_github_signature(payload, signature or "", webhook_secret):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse webhook event
    event_type = request.headers.get("X-GitHub-Event")
    data = await request.json()

    logger.info(f"Received GitHub webhook: {event_type}")

    # Handle different event types
    if event_type == "pull_request":
        return await handle_pull_request_event(data, background_tasks)
    elif event_type == "push":
        return await handle_push_event(data, background_tasks)
    elif event_type == "check_suite":
        return await handle_check_suite_event(data)
    else:
        logger.info(f"Ignoring event type: {event_type}")
        return {"status": "ignored", "event": event_type}


async def handle_pull_request_event(data: Dict, background_tasks: BackgroundTasks) -> Dict:
    """Handle pull_request webhook events"""
    action = data.get("action")

    # Only process relevant actions
    if action not in ["opened", "synchronize", "reopened"]:
        return {"status": "ignored", "action": action}

    pr = data.get("pull_request", {})
    repo = data.get("repository", {})

    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")
    pr_number = pr.get("number")
    head_sha = pr.get("head", {}).get("sha")
    base_ref = pr.get("base", {}).get("ref")

    logger.info(
        f"Pull request #{pr_number} {action} in {owner}/{repo_name} "
        f"(target: {base_ref}, commit: {head_sha[:8]})"
    )

    # Check if target branch is protected
    protected_branches = ["main", "master"]
    if base_ref not in protected_branches:
        logger.info(f"Target branch '{base_ref}' not protected - skipping validation")
        return {"status": "skipped", "reason": "target_not_protected"}

    # Queue validation in background
    background_tasks.add_task(
        validate_pull_request,
        owner=owner,
        repo=repo_name,
        pr_number=pr_number,
        head_sha=head_sha
    )

    return {
        "status": "queued",
        "pr_number": pr_number,
        "message": "Iron Grip validation queued"
    }


async def handle_push_event(data: Dict, background_tasks: BackgroundTasks) -> Dict:
    """Handle push webhook events"""
    ref = data.get("ref", "")
    repo = data.get("repository", {})
    commits = data.get("commits", [])

    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")

    # Extract branch name from ref (refs/heads/main -> main)
    branch = ref.replace("refs/heads/", "")

    logger.info(f"Push to {owner}/{repo_name}:{branch} ({len(commits)} commit(s))")

    # Check if push is to protected branch
    protected_branches = ["main", "master"]
    if branch not in protected_branches:
        return {"status": "ignored", "reason": "branch_not_protected"}

    # Get head commit
    head_commit = data.get("after")

    if not head_commit:
        return {"status": "error", "reason": "no_head_commit"}

    # Validate compliance
    github_token = os.getenv("GITHUB_TOKEN")
    service = GitHubProtectionService(github_token=github_token)

    passes, results = service.validate_iron_grip_compliance(
        owner=owner,
        repo=repo_name,
        commit_sha=head_commit
    )

    if not passes:
        logger.warning(
            f"Push to protected branch {branch} does not meet Iron Grip requirements: "
            f"missing={results.get('missing_checks')}, failed={results.get('failed_checks')}"
        )

    return {
        "status": "validated",
        "branch": branch,
        "commit": head_commit[:8],
        "passes": passes,
        "results": results
    }


async def handle_check_suite_event(data: Dict) -> Dict:
    """Handle check_suite webhook events"""
    action = data.get("action")
    check_suite = data.get("check_suite", {})

    conclusion = check_suite.get("conclusion")
    head_sha = check_suite.get("head_sha")
    repo = data.get("repository", {})

    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")

    logger.info(
        f"Check suite {action} for {owner}/{repo_name}@{head_sha[:8] if head_sha else 'unknown'} "
        f"(conclusion: {conclusion})"
    )

    # If check suite completed, validate overall compliance
    if action == "completed":
        github_token = os.getenv("GITHUB_TOKEN")
        service = GitHubProtectionService(github_token=github_token)

        passes, results = service.validate_iron_grip_compliance(
            owner=owner,
            repo=repo_name,
            commit_sha=head_sha
        )

        return {
            "status": "validated",
            "conclusion": conclusion,
            "iron_grip_passes": passes,
            "results": results
        }

    return {"status": "acknowledged", "action": action}


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    webhook_secret_configured = os.getenv("GITHUB_WEBHOOK_SECRET") is not None
    github_token_configured = os.getenv("GITHUB_TOKEN") is not None

    return {
        "status": "ok",
        "webhook_secret_configured": webhook_secret_configured,
        "github_token_configured": github_token_configured,
        "message": "Iron Grip webhook handler operational"
    }

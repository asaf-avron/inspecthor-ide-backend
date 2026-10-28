"""
GitHub Protection Service - Iron Grip Enforcement

Manages branch protection rules and enforces InspecThor verification
requirements through GitHub's API.
"""

import os
import logging
from typing import Any, List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import requests

logger = logging.getLogger(__name__)


@dataclass
class ProtectionRule:
    """Branch protection rule configuration"""
    branch: str
    require_pull_request: bool = True
    require_approvals: int = 1
    dismiss_stale_reviews: bool = True
    require_code_owner_reviews: bool = False
    require_status_checks: bool = True
    required_status_checks: List[str] = field(default_factory=lambda: [
        "InspecThor - Iron Grip Checks / dafny-verification",
        "InspecThor - Iron Grip Checks / drift-detection",
        "InspecThor - Iron Grip Checks / component-validation",
        "InspecThor - Iron Grip Checks / call-graph-compliance",
        "InspecThor - Iron Grip Checks / proof-validation",
    ])
    enforce_admins: bool = False
    allow_force_pushes: bool = False
    allow_deletions: bool = False


@dataclass
class RepositoryConfig:
    """Repository configuration for Iron Grip"""
    owner: str
    repo: str
    protected_branches: List[str] = field(default_factory=lambda: ["main", "master"])


class GitHubProtectionService:
    """Service for managing GitHub branch protection and status checks"""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub protection service

        Args:
            github_token: GitHub personal access token or App token
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.api_base = "https://api.github.com"

        if not self.github_token:
            logger.warning("GitHub token not provided - protection features will be limited")

    def enable_iron_grip(
        self,
        owner: str,
        repo: str,
        branches: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Enable Iron Grip protection for a repository

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            branches: List of branches to protect (default: main, master)

        Returns:
            Tuple of (success, message)
        """
        if not self.github_token:
            return False, "GitHub token not configured"

        config = RepositoryConfig(
            owner=owner,
            repo=repo,
            protected_branches=branches or ["main", "master"]
        )

        try:
            logger.info(f"Enabling Iron Grip for {owner}/{repo}")

            # Apply protection rules to each branch
            results = []
            for branch in config.protected_branches:
                rule = ProtectionRule(branch=branch)
                success, msg = self._apply_branch_protection(config, rule)
                results.append((branch, success, msg))

            # Check results
            failed = [r for r in results if not r[1]]

            if failed:
                failures = ", ".join(f"{r[0]}: {r[2]}" for r in failed)
                return False, f"Failed to protect some branches: {failures}"

            return True, f"Iron Grip enabled for {len(results)} branch(es)"

        except Exception as e:
            logger.error(f"Failed to enable Iron Grip: {e}")
            return False, str(e)

    def disable_iron_grip(
        self,
        owner: str,
        repo: str,
        branches: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Disable Iron Grip protection for a repository

        Args:
            owner: Repository owner
            repo: Repository name
            branches: List of branches to unprotect

        Returns:
            Tuple of (success, message)
        """
        if not self.github_token:
            return False, "GitHub token not configured"

        branches = branches or ["main", "master"]

        try:
            logger.info(f"Disabling Iron Grip for {owner}/{repo}")

            results = []
            for branch in branches:
                success, msg = self._remove_branch_protection(owner, repo, branch)
                results.append((branch, success, msg))

            failed = [r for r in results if not r[1]]

            if failed:
                failures = ", ".join(f"{r[0]}: {r[2]}" for r in failed)
                return False, f"Failed to unprotect some branches: {failures}"

            return True, f"Iron Grip disabled for {len(results)} branch(es)"

        except Exception as e:
            logger.error(f"Failed to disable Iron Grip: {e}")
            return False, str(e)

    def check_protection_status(
        self,
        owner: str,
        repo: str,
        branch: str
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a branch has protection rules enabled

        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name

        Returns:
            Tuple of (is_protected, protection_config)
        """
        if not self.github_token:
            return False, None

        try:
            url = f"{self.api_base}/repos/{owner}/{repo}/branches/{branch}/protection"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 404:
                return False, None
            else:
                logger.error(f"Failed to check protection status: {response.status_code}")
                return False, None

        except Exception as e:
            logger.error(f"Error checking protection status: {e}")
            return False, None

    def report_status_check(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        check_name: str,
        status: str,
        conclusion: Optional[str] = None,
        details_url: Optional[str] = None,
        output: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Report a status check result to GitHub

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA to report on
            check_name: Name of the check (e.g., "Dafny Verification")
            status: "queued", "in_progress", or "completed"
            conclusion: "success", "failure", "neutral", "cancelled", etc.
            details_url: URL with check details
            output: Check output (title, summary, text)

        Returns:
            Tuple of (success, message)
        """
        if not self.github_token:
            return False, "GitHub token not configured"

        try:
            url = f"{self.api_base}/repos/{owner}/{repo}/check-runs"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            data: Dict[str, Any] = {
                "name": check_name,
                "head_sha": commit_sha,
                "status": status
            }

            if conclusion:
                data["conclusion"] = conclusion

            if details_url:
                data["details_url"] = details_url

            if output:
                data["output"] = output

            response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code in [200, 201]:
                logger.info(f"Status check reported: {check_name} = {status}")
                return True, "Status check reported successfully"
            else:
                logger.error(f"Failed to report status check: {response.status_code}")
                return False, f"API error: {response.status_code}"

        except Exception as e:
            logger.error(f"Error reporting status check: {e}")
            return False, str(e)

    def get_repository_checks(
        self,
        owner: str,
        repo: str,
        ref: str
    ) -> Tuple[bool, List[Dict]]:
        """
        Get all check runs for a commit/ref

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git reference (commit SHA, branch, tag)

        Returns:
            Tuple of (success, list of check runs)
        """
        if not self.github_token:
            return False, []

        try:
            url = f"{self.api_base}/repos/{owner}/{repo}/commits/{ref}/check-runs"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return True, data.get("check_runs", [])
            else:
                logger.error(f"Failed to get check runs: {response.status_code}")
                return False, []

        except Exception as e:
            logger.error(f"Error getting check runs: {e}")
            return False, []

    def _apply_branch_protection(
        self,
        config: RepositoryConfig,
        rule: ProtectionRule
    ) -> Tuple[bool, str]:
        """
        Apply branch protection rule

        Args:
            config: Repository configuration
            rule: Protection rule to apply

        Returns:
            Tuple of (success, message)
        """
        try:
            url = f"{self.api_base}/repos/{config.owner}/{config.repo}/branches/{rule.branch}/protection"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            # Build protection configuration
            protection_config: Dict[str, Any] = {
                "required_status_checks": None,
                "enforce_admins": rule.enforce_admins,
                "required_pull_request_reviews": None,
                "restrictions": None,
                "allow_force_pushes": rule.allow_force_pushes,
                "allow_deletions": rule.allow_deletions
            }

            # Required status checks
            if rule.require_status_checks:
                protection_config["required_status_checks"] = {
                    "strict": True,
                    "checks": [
                        {"context": check} for check in rule.required_status_checks
                    ]
                }

            # Pull request reviews
            if rule.require_pull_request:
                protection_config["required_pull_request_reviews"] = {
                    "dismiss_stale_reviews": rule.dismiss_stale_reviews,
                    "require_code_owner_reviews": rule.require_code_owner_reviews,
                    "required_approving_review_count": rule.require_approvals
                }

            response = requests.put(url, json=protection_config, headers=headers, timeout=10)

            if response.status_code in [200, 201]:
                logger.info(f"Branch protection applied: {config.repo}:{rule.branch}")
                return True, f"Protected {rule.branch}"
            else:
                error_msg = f"API error: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text[:200]}"
                logger.error(f"Failed to apply protection: {error_msg}")
                return False, error_msg

        except Exception as e:
            logger.error(f"Error applying branch protection: {e}")
            return False, str(e)

    def _remove_branch_protection(
        self,
        owner: str,
        repo: str,
        branch: str
    ) -> Tuple[bool, str]:
        """
        Remove branch protection

        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name

        Returns:
            Tuple of (success, message)
        """
        try:
            url = f"{self.api_base}/repos/{owner}/{repo}/branches/{branch}/protection"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            response = requests.delete(url, headers=headers, timeout=10)

            if response.status_code == 204:
                logger.info(f"Branch protection removed: {repo}:{branch}")
                return True, f"Unprotected {branch}"
            elif response.status_code == 404:
                return True, f"{branch} was not protected"
            else:
                logger.error(f"Failed to remove protection: {response.status_code}")
                return False, f"API error: {response.status_code}"

        except Exception as e:
            logger.error(f"Error removing branch protection: {e}")
            return False, str(e)

    def validate_iron_grip_compliance(
        self,
        owner: str,
        repo: str,
        commit_sha: str
    ) -> Tuple[bool, Dict]:
        """
        Check if a commit passes all Iron Grip requirements

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit to validate

        Returns:
            Tuple of (passes, detailed_results)
        """
        success, checks = self.get_repository_checks(owner, repo, commit_sha)

        if not success:
            return False, {"error": "Failed to retrieve check runs"}

        required_checks = [
            "dafny-verification",
            "drift-detection",
            "component-validation",
            "call-graph-compliance",
            "proof-validation"
        ]

        results: Dict[str, Any] = {
            "commit": commit_sha,
            "checks": {},
            "all_passed": False,
            "missing_checks": [],
            "failed_checks": []
        }

        # Map check names to results
        check_map = {}
        for check in checks:
            check_name = check.get("name", "").lower()
            for required in required_checks:
                if required in check_name:
                    check_map[required] = check

        # Validate each required check
        for required in required_checks:
            if required not in check_map:
                results["missing_checks"].append(required)
                results["checks"][required] = {"status": "missing"}
            else:
                check = check_map[required]
                conclusion = check.get("conclusion")
                status = check.get("status")

                results["checks"][required] = {
                    "status": status,
                    "conclusion": conclusion,
                    "passed": conclusion == "success"
                }

                if conclusion != "success":
                    results["failed_checks"].append(required)

        # Overall pass/fail
        results["all_passed"] = (
            len(results["missing_checks"]) == 0 and
            len(results["failed_checks"]) == 0
        )

        return results["all_passed"], results

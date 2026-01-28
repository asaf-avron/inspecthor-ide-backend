"""
GitHub Check Runs API for InSpecThor.
Creates and updates check runs on pull requests.
"""

from typing import Dict, Any, Optional
from .api_client import GitHubStatelessClient


class CheckRunService:
    """
    Service for creating and updating GitHub Check Runs.
    """
    
    def __init__(self):
        self._client: Optional[GitHubStatelessClient] = None
    
    @property
    def client(self) -> GitHubStatelessClient:
        """Get or create GitHubStatelessClient instance."""
        if self._client is None:
            self._client = GitHubStatelessClient()
        return self._client
    
    async def create_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        head_sha: str,
        name: str = "InSpecThor Verification"
    ) -> Dict[str, Any]:
        """
        Create a new check run for a commit.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            head_sha: Commit SHA to create check for
            name: Check run name
        
        Returns:
            Dict with check run metadata
        """
        github_repo = self.client._get_repo(installation_id, owner, repo)
        
        check_run = github_repo.create_check_run(
            name=name,
            head_sha=head_sha,
            status="queued",
            output={
                "title": "Verification pending",
                "summary": "InSpecThor is analyzing your changes..."
            }
        )
        
        return {
            "id": check_run.id,
            "name": check_run.name,
            "status": check_run.status,
            "conclusion": check_run.conclusion,
            "html_url": check_run.html_url
        }
    
    async def update_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        check_run_id: int,
        status: str,
        conclusion: Optional[str],
        output: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Update an existing check run.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            check_run_id: Check run ID to update
            status: "queued", "in_progress", or "completed"
            conclusion: "success", "failure", "neutral", "cancelled", "skipped", "timed_out", "action_required" (only if status=completed)
            output: Dict with title and summary
        
        Returns:
            Dict with updated check run metadata
        """
        github_repo = self.client._get_repo(installation_id, owner, repo)
        check_run = github_repo.get_check_run(check_run_id)
        
        # Build update kwargs
        update_kwargs = {
            "status": status,
            "output": output
        }
        
        if conclusion:
            update_kwargs["conclusion"] = conclusion
        
        check_run.edit(**update_kwargs)  # type: ignore[arg-type]
        
        return {
            "id": check_run.id,
            "name": check_run.name,
            "status": check_run.status,
            "conclusion": check_run.conclusion,
            "html_url": check_run.html_url
        }
    
    async def create_failure_comment(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
        anchor_info: Dict[str, Any],
        counterexample: Dict[str, Any]
    ) -> None:
        """
        Post a comment on PR with verification failure details.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            anchor_info: Dict with function_name, file_path, spec_id
            counterexample: Dict with input values and violated constraint
        """
        github_repo = self.client._get_repo(installation_id, owner, repo)
        pr = github_repo.get_pull(pr_number)
        
        # Build failure comment
        comment_body = f"""## InSpecThor Verification Failed

**Function:** `{anchor_info['function_name']}` in `{anchor_info['file_path']}:{anchor_info.get('line', '?')}`
**Spec:** {anchor_info['spec_id']}

### Counterexample Found

The following input violates the specification:

"""
        
        # Add counterexample inputs table
        if 'inputs' in counterexample:
            comment_body += "| Input | Value |\n|-------|-------|\n"
            for input_name, input_value in counterexample['inputs'].items():
                comment_body += f"| `{input_name}` | `{input_value}` |\n"
            comment_body += "\n"
        
        # Add violated constraint
        if 'violated_constraint' in counterexample:
            comment_body += f"""### Specification Violated

```dafny
{counterexample['violated_constraint']}
```

"""
        
        # Add suggested fix if available
        if 'suggestion' in counterexample:
            comment_body += f"""### Suggested Fix

{counterexample['suggestion']}

"""
        
        comment_body += """---
*Verified by [InSpecThor](https://inspecthor.dev)*
"""
        
        pr.create_issue_comment(comment_body)

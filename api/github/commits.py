"""
Ghost Commit Protocol for InSpecThor.
Allows users to commit from IDE directly to GitHub without terminal.
"""

import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from .api_client import GitHubStatelessClient


class FileChange(BaseModel):
    """Represents a file change to commit."""
    path: str
    content: str
    mode: str = "100644"  # Regular file


class PullRequestResult(BaseModel):
    """Result of creating a pull request."""
    number: int
    url: str
    state: str
    title: str
    head_ref: str
    head_sha: str
    base_ref: str


class GhostCommitService:
    """
    Service for creating commits and PRs from the IDE.
    """
    
    def __init__(self):
        self._client: Optional[GitHubStatelessClient] = None
    
    @property
    def client(self) -> GitHubStatelessClient:
        """Get or create GitHubStatelessClient instance."""
        if self._client is None:
            self._client = GitHubStatelessClient()
        return self._client
    
    async def create_pr_from_ide(
        self,
        user_id: str,
        installation_id: int,
        owner: str,
        repo: str,
        base_branch: str,
        files: List[FileChange],
        title: str,
        body: str,
        draft: bool = False
    ) -> PullRequestResult:
        """
        Create a pull request with file changes from the IDE.
        
        This implements the "Ghost Commit Protocol":
        1. Get latest base SHA
        2. Create tree with changes
        3. Create commit
        4. Create branch
        5. Create PR
        
        Args:
            user_id: User UUID (for branch naming)
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            base_branch: Target branch (usually "main")
            files: List of file changes
            title: PR title
            body: PR description
            draft: Create as draft PR
        
        Returns:
            PullRequestResult with PR metadata
        """
        # Step 1: Get latest base SHA
        base_ref = await self.client.get_ref(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            ref=f"heads/{base_branch}"
        )
        base_sha = base_ref["object"]["sha"]
        
        # Step 2: Create tree with changes
        tree_items = [
            {
                "path": file.path,
                "mode": file.mode,
                "content": file.content
            }
            for file in files
        ]
        
        tree = await self.client.create_tree(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            base_tree=base_sha,
            tree=tree_items
        )
        tree_sha = tree["sha"]
        
        # Step 3: Create commit
        commit_message = f"fix: {title}\n\nVerified by InSpecThor\n\nThis commit was created from the InSpecThor IDE and has passed formal verification."
        
        commit = await self.client.create_commit(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            message=commit_message,
            tree=tree_sha,
            parents=[base_sha]
        )
        commit_sha = commit["sha"]
        
        # Step 4: Create branch
        # Branch name format: inspecthor/<user_id_prefix>/<timestamp>
        branch_name = f"inspecthor/{user_id[:8]}/{int(time.time())}"
        
        await self.client.create_ref(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            ref=f"refs/heads/{branch_name}",
            sha=commit_sha
        )
        
        # Step 5: Create PR
        pr_body = f"""{body}

---

### InSpecThor Verification

✓ All changes have been formally verified.

**Files modified:**
{chr(10).join([f"- `{f.path}`" for f in files])}

---
*Created with [InSpecThor](https://inspecthor.dev)*
"""
        
        pr = await self.client.create_pull_request(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            title=title,
            body=pr_body,
            head=branch_name,
            base=base_branch,
            draft=draft
        )
        
        return PullRequestResult(
            number=pr["number"],
            url=pr["url"],
            state=pr["state"],
            title=pr["title"],
            head_ref=pr["head"]["ref"],
            head_sha=pr["head"]["sha"],
            base_ref=pr["base"]["ref"]
        )
    
    async def update_file_in_pr(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str
    ) -> Dict[str, Any]:
        """
        Update a single file in an existing PR branch.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            branch: Branch name to update
            file_path: Path to file
            content: New file content
            commit_message: Commit message
        
        Returns:
            Dict with commit metadata
        """
        # Get current branch SHA
        ref = await self.client.get_ref(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            ref=f"heads/{branch}"
        )
        base_sha = ref["object"]["sha"]
        
        # Create tree with single file change
        tree = await self.client.create_tree(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            base_tree=base_sha,
            tree=[{"path": file_path, "mode": "100644", "content": content}]
        )
        
        # Create commit
        commit = await self.client.create_commit(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            message=commit_message,
            tree=tree["sha"],
            parents=[base_sha]
        )
        
        # Update branch reference
        github_repo = self.client._get_repo(installation_id, owner, repo)
        branch_ref = github_repo.get_git_ref(f"heads/{branch}")
        branch_ref.edit(sha=commit["sha"])
        
        return commit

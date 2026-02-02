"""
Stateless GitHub API client for InSpecThor.
Fetches files without cloning repositories.
"""

import base64
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from github import Github, GithubIntegration, Auth, InputGitTreeElement
from github.Repository import Repository
from pydantic import BaseModel


class TreeEntry(BaseModel):
    """Represents a file/directory in a Git tree."""
    path: str
    mode: str
    type: str  # "blob" (file) or "tree" (directory)
    sha: str
    size: Optional[int] = None
    url: str


class PullRequestFile(BaseModel):
    """Represents a file changed in a pull request."""
    filename: str
    status: str  # "added", "removed", "modified", "renamed"
    additions: int
    deletions: int
    changes: int
    blob_url: str
    raw_url: str
    contents_url: str
    patch: Optional[str] = None


class GitHubStatelessClient:
    """
    Stateless GitHub API client that fetches files without cloning.
    Uses GitHub App authentication with installation tokens.
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
        
        # Cache for installation tokens (they expire after 1 hour)
        self._token_cache: Dict[int, tuple[str, datetime]] = {}
    
    def _get_installation_token(self, installation_id: int) -> str:
        """
        Get installation access token (cached).
        Tokens expire after 1 hour, so we cache them.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        now = datetime.utcnow()
        
        # Check cache - use same token for all calls in a session
        if installation_id in self._token_cache:
            token, expires_at = self._token_cache[installation_id]
            if now < expires_at - timedelta(minutes=5):  # Refresh 5 min before expiry
                logger.info(f"Using cached token for installation {installation_id}")
                return token
        
        # Get new token
        logger.info(f"Getting fresh token for installation {installation_id}")
        token = self.integration.get_access_token(installation_id).token
        logger.info(f"Got token: {token[:15]}...")
        expires_at = now + timedelta(hours=1)
        self._token_cache[installation_id] = (token, expires_at)
        
        return token
    
    def _get_client(self, installation_id: int) -> Github:
        """Get authenticated GitHub client for installation."""
        token = self._get_installation_token(installation_id)
        return Github(token)
    
    def _get_repo(self, installation_id: int, owner: str, repo: str) -> Repository:
        """Get repository object."""
        client = self._get_client(installation_id)
        return client.get_repo(f"{owner}/{repo}")
    
    async def get_file_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main"
    ) -> str:
        """
        Fetch file content from GitHub.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            ref: Branch/tag/commit SHA (default: "main")
        
        Returns:
            File content as string
        
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        repository = self._get_repo(installation_id, owner, repo)
        
        try:
            contents = repository.get_contents(path, ref=ref)
            
            if isinstance(contents, list):
                raise ValueError(f"Path '{path}' is a directory, not a file")
            
            # Decode base64 content
            content = base64.b64decode(contents.content).decode('utf-8')
            return content
            
        except Exception as e:
            if "404" in str(e):
                raise FileNotFoundError(f"File not found: {path} at ref {ref}")
            raise
    
    async def get_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        tree_sha: str,
        recursive: bool = True
    ) -> List[TreeEntry]:
        """
        Get Git tree (file list) for a commit/branch.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            tree_sha: Tree SHA or branch name
            recursive: Recursively fetch subdirectories
        
        Returns:
            List of TreeEntry objects
        """
        repository = self._get_repo(installation_id, owner, repo)
        
        # Get tree
        tree = repository.get_git_tree(tree_sha, recursive=recursive)
        
        return [
            TreeEntry(
                path=item.path,
                mode=item.mode,
                type=item.type,
                sha=item.sha,
                size=item.size,
                url=item.url
            )
            for item in tree.tree
        ]
    
    async def get_pr_files(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[PullRequestFile]:
        """
        Get list of files changed in a pull request.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
        
        Returns:
            List of PullRequestFile objects
        """
        repository = self._get_repo(installation_id, owner, repo)
        pr = repository.get_pull(pr_number)
        
        files = []
        for file in pr.get_files():
            files.append(PullRequestFile(
                filename=file.filename,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                changes=file.changes,
                blob_url=file.blob_url,
                raw_url=file.raw_url,
                contents_url=file.contents_url,
                patch=file.patch
            ))
        
        return files
    
    async def get_pr_changed_files_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int
    ) -> Dict[str, str]:
        """
        Get content of all changed files in a PR.
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
        
        Returns:
            Dict mapping filename to content
        """
        repository = self._get_repo(installation_id, owner, repo)
        pr = repository.get_pull(pr_number)
        
        # Get PR head SHA
        head_sha = pr.head.sha
        
        # Get changed files
        changed_files = await self.get_pr_files(installation_id, owner, repo, pr_number)
        
        # Fetch content for each file (skip deleted files)
        contents = {}
        for file in changed_files:
            if file.status != "removed":
                try:
                    content = await self.get_file_content(
                        installation_id, owner, repo, file.filename, ref=head_sha
                    )
                    contents[file.filename] = content
                except FileNotFoundError:
                    # File might be renamed/deleted
                    pass
        
        return contents
    
    async def get_default_branch(
        self,
        installation_id: int,
        owner: str,
        repo: str
    ) -> str:
        """Get repository's default branch name."""
        repository = self._get_repo(installation_id, owner, repo)
        return str(repository.default_branch)  # type: ignore[no-any-return]
    
    async def get_ref(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str
    ) -> Dict[str, Any]:
        """
        Get reference (branch/tag) information.
        
        Args:
            ref: Reference name (e.g., "heads/main", "tags/v1.0.0")
        
        Returns:
            Dict with ref metadata including SHA
        """
        repository = self._get_repo(installation_id, owner, repo)
        git_ref = repository.get_git_ref(ref)
        
        return {
            "ref": git_ref.ref,
            "url": git_ref.url,
            "object": {
                "sha": git_ref.object.sha,
                "type": git_ref.object.type,
                "url": git_ref.object.url
            }
        }
    
    async def create_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        base_tree: str,
        tree: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Create a new Git tree with file changes.
        
        Args:
            base_tree: Base tree SHA to build upon
            tree: List of file changes [{"path": ..., "mode": "100644", "content": ...}]
        
        Returns:
            Dict with new tree SHA
        """
        import logging
        import requests
        logger = logging.getLogger(__name__)
        
        # Get fresh token for this specific operation
        token = self._get_installation_token(installation_id)
        
        # Build tree elements for API call
        tree_elements_json = []
        for item in tree:
            tree_elements_json.append({
                "path": item["path"],
                "mode": item.get("mode", "100644"),
                "type": "blob",
                "content": item["content"]
            })
        
        # Build request body
        body = {"tree": tree_elements_json}
        if base_tree:
            body["base_tree"] = base_tree
        
        logger.info(f"Creating tree with {len(tree_elements_json)} elements, base_tree={base_tree}")
        
        # Use direct API call instead of PyGithub (PyGithub has token caching issues)
        resp = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            json=body
        )
        
        if resp.status_code != 201:
            logger.error(f"create_tree failed: {resp.status_code} {resp.text[:200]}")
            raise Exception(f"Failed to create tree: {resp.status_code} {resp.text}")
        
        result = resp.json()
        return {
            "sha": result["sha"],
            "url": result["url"]
        }
    
    async def create_commit(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        message: str,
        tree: str,
        parents: List[str]
    ) -> Dict[str, Any]:
        """
        Create a new Git commit.
        
        Args:
            message: Commit message
            tree: Tree SHA
            parents: List of parent commit SHAs
        
        Returns:
            Dict with new commit SHA
        """
        import logging
        import requests
        logger = logging.getLogger(__name__)
        
        # Get fresh token for this specific operation
        token = self._get_installation_token(installation_id)
        
        # Build request body
        body = {
            "message": message,
            "tree": tree,
            "parents": parents
        }
        
        logger.info(f"Creating commit with tree={tree}, parents={parents}")
        
        # Use direct API call instead of PyGithub
        resp = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/commits",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            json=body
        )
        
        if resp.status_code != 201:
            logger.error(f"create_commit failed: {resp.status_code} {resp.text[:200]}")
            raise Exception(f"Failed to create commit: {resp.status_code} {resp.text}")
        
        result = resp.json()
        return {
            "sha": result["sha"],
            "url": result["url"],
            "message": result["message"]
        }
    
    async def create_ref(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
        sha: str
    ) -> Dict[str, Any]:
        """
        Create a new reference (branch/tag).
        
        Args:
            ref: Reference name (e.g., "refs/heads/feature-branch")
            sha: Commit SHA to point to
        
        Returns:
            Dict with ref metadata
        """
        import logging
        import requests
        logger = logging.getLogger(__name__)
        
        # Get fresh token for this specific operation
        token = self._get_installation_token(installation_id)
        
        logger.info(f"Creating ref={ref} pointing to {sha}")
        
        # Use direct API call instead of PyGithub
        resp = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            json={"ref": ref, "sha": sha}
        )
        
        if resp.status_code != 201:
            logger.error(f"create_ref failed: {resp.status_code} {resp.text[:200]}")
            raise Exception(f"Failed to create ref: {resp.status_code} {resp.text}")
        
        result = resp.json()
        return {
            "ref": result["ref"],
            "url": result["url"],
            "object": {
                "sha": result["object"]["sha"],
                "type": result["object"]["type"]
            }
        }
    
    async def create_pull_request(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            title: PR title
            body: PR description
            head: Branch with changes
            base: Target branch
            draft: Create as draft PR
        
        Returns:
            Dict with PR metadata
        """
        repository = self._get_repo(installation_id, owner, repo)
        pr = repository.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
            draft=draft
        )
        
        return {
            "number": pr.number,
            "url": pr.html_url,
            "state": pr.state,
            "title": pr.title,
            "body": pr.body,
            "head": {
                "ref": pr.head.ref,
                "sha": pr.head.sha
            },
            "base": {
                "ref": pr.base.ref,
                "sha": pr.base.sha
            }
        }

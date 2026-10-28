"""
Blueprint Genesis Service for InspecThor.
Initializes empty GitHub repositories with the Trusted Kernel Architecture.
"""

import logging
from typing import Dict, Optional, List
from pydantic import BaseModel

from api.github.api_client import GitHubStatelessClient

logger = logging.getLogger(__name__)


class GenesisResult(BaseModel):
    """Result of repository initialization."""
    commit_sha: str
    commit_url: str
    files_created: List[str]
    default_branch: str


class BlueprintGenesisService:
    """
    Service for initializing repositories with the Trusted Kernel Architecture.
    
    The Genesis Event:
    1. Verify repository is empty (or contains only README/LICENSE)
    2. Generate template files (blueprint.yaml, kernel/, shell/, etc.)
    3. Push all files in a single commit
    4. Return commit information
    """
    
    def __init__(self):
        self._client: Optional[GitHubStatelessClient] = None
    
    @property
    def client(self) -> GitHubStatelessClient:
        """Get or create GitHubStatelessClient instance."""
        if self._client is None:
            self._client = GitHubStatelessClient()
        return self._client
    
    def _generate_genesis_files(self, blueprint_name: str, domain: str = "custom") -> Dict[str, str]:
        """
        Generate all template files for repository initialization.
        
        Args:
            blueprint_name: Human-readable name for the blueprint
            domain: Domain preset (banking, healthcare, authentication, custom)
        
        Returns:
            Dict mapping file paths to content
        """
        return {
            "blueprint.yaml": f'''# InspecThor Blueprint Manifest
# THE LAW - This file defines the verified system structure

version: "1.0"
name: "{blueprint_name}"
domain: "{domain}"

invariants: []

claims: []

kernel:
  entry: "kernel/Main.dfy"

shell:
  entry: "shell/main.py"
  runtime: "python3.11"

verification:
  solver: "z3"
  timeout_seconds: 120
''',
            
            "kernel/Main.dfy": '''// InspecThor Kernel - Formally Verified Zone
// All business logic goes here. This code is verified by Dafny.

module Kernel {
    // Entry point - replace with actual verified logic
    method Init() 
        ensures true  // Replace with actual postconditions
    {
        // Your verified implementation here
    }
}
''',
            
            "shell/main.py": '''#!/usr/bin/env python3
"""
InspecThor Shell - Unverified I/O Zone

This layer handles:
- HTTP requests/responses
- Database operations
- External API calls
- File I/O

It MUST NOT contain business logic.
Business logic belongs in kernel/ (verified Dafny).

After verification, import from generated/kernel.py:
    from generated.kernel import Kernel
"""

def main():
    # Import and call kernel methods after compilation
    # from generated.kernel import Kernel
    # kernel = Kernel()
    # kernel.Init()
    pass


if __name__ == "__main__":
    main()
''',
            
            "claims/README.md": '''# Claims Directory

Write your specifications here as structured Markdown files.

## Claim Format

```markdown
# Claim: [ID] [Title]

## Preconditions
- Condition that must be true before operation

## Postconditions
- Condition that must be true after operation

## Invariants
- Condition that must always be true
```

## Example

```markdown
# Claim: REQ-101 Transfer Funds

## Preconditions
- Sender balance >= transfer amount
- Sender account is active
- Receiver account exists

## Postconditions
- Sender balance decreased by transfer amount
- Receiver balance increased by transfer amount
- Total system balance unchanged

## Invariants
- No account balance is ever negative
```
''',
            
            "generated/.gitkeep": "# Auto-generated files - do not edit\n",
            
            ".inspecthor/config.yaml": '''# InspecThor Local Configuration
cache_enabled: true
auto_verify: false
''',
            
            ".github/workflows/verify.yml": '''# InspecThor Verification Pipeline
# Auto-generated - ensures all PRs are formally verified

name: InspecThor Verify

on:
  push:
    branches: [main]
    paths:
      - 'kernel/**'
      - 'claims/**'
  pull_request:
    branches: [main]
    paths:
      - 'kernel/**'
      - 'claims/**'

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Dafny
        run: |
          wget -q https://github.com/dafny-lang/dafny/releases/download/v4.4.0/dafny-4.4.0-x64-ubuntu-20.04.zip
          unzip -q dafny-4.4.0-x64-ubuntu-20.04.zip -d /opt/dafny
          echo "/opt/dafny/dafny" >> $GITHUB_PATH
      
      - name: Verify Kernel
        run: dafny verify kernel/Main.dfy
      
      - name: Compile to Python
        run: dafny build --target:py kernel/Main.dfy -o generated/kernel
        
      - name: Upload Verified Kernel
        uses: actions/upload-artifact@v4
        with:
          name: verified-kernel
          path: generated/kernel.py
'''
        }
    
    async def check_repo_is_empty(
        self,
        installation_id: int,
        owner: str,
        repo: str
    ) -> bool:
        """
        Check if repository is empty or only contains allowed files.
        
        Allowed files in "empty" repo: README.md, LICENSE, .gitignore
        
        Returns:
            True if repo is safe to initialize
        """
        try:
            default_branch = await self.client.get_default_branch(
                installation_id=installation_id,
                owner=owner,
                repo=repo
            )
            
            tree = await self.client.get_tree(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                tree_sha=default_branch,
                recursive=True
            )
            
            allowed_files = {"readme.md", "license", "license.md", ".gitignore"}
            for entry in tree:
                if entry.path.lower() not in allowed_files:
                    logger.warning(f"Repo {owner}/{repo} has existing file: {entry.path}")
                    return False
            
            return True
            
        except Exception as e:
            # If we can't get tree, repo might be truly empty (no commits)
            logger.info(f"Could not get tree for {owner}/{repo}: {e}. Assuming empty repo.")
            return True
    
    async def initialize_repository(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        blueprint_name: str,
        domain: str = "custom",
        force: bool = False
    ) -> GenesisResult:
        """
        Initialize a repository with the Trusted Kernel Architecture.
        
        The Genesis Event pushes:
        - blueprint.yaml (manifest)
        - kernel/Main.dfy (verified zone)
        - shell/main.py (I/O zone)
        - claims/README.md (specification templates)
        - generated/.gitkeep (output directory)
        - .inspecthor/config.yaml (local settings)
        - .github/workflows/verify.yml (CI enforcement)
        
        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            blueprint_name: Human-readable blueprint name
            domain: Domain preset (banking, healthcare, authentication, custom)
            force: If True, skip empty repo check
        
        Returns:
            GenesisResult with commit information
        
        Raises:
            ValueError: If repo is not empty and force=False
        """
        logger.info(f"Genesis: Initializing {owner}/{repo} as blueprint '{blueprint_name}'")
        
        # Step 1: Check if repo is empty (unless forced)
        if not force:
            is_empty = await self.check_repo_is_empty(installation_id, owner, repo)
            if not is_empty:
                raise ValueError(
                    f"Repository {owner}/{repo} is not empty. "
                    "Use force=True to overwrite existing files."
                )
        
        # Step 2: Generate template files
        genesis_files = self._generate_genesis_files(blueprint_name, domain)
        files_created = list(genesis_files.keys())
        
        # Step 3: Get default branch and current HEAD
        default_branch = await self.client.get_default_branch(
            installation_id=installation_id,
            owner=owner,
            repo=repo
        )
        
        try:
            base_ref = await self.client.get_ref(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                ref=f"heads/{default_branch}"
            )
            base_sha = base_ref["object"]["sha"]
        except Exception:
            # Empty repo has no commits - we'll create first commit
            base_sha = None
        
        # Step 4: Create tree with all genesis files
        tree_items = [
            {"path": path, "mode": "100644", "content": content}
            for path, content in genesis_files.items()
        ]
        
        if base_sha:
            tree = await self.client.create_tree(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                base_tree=base_sha,
                tree=tree_items
            )
        else:
            # For truly empty repo, create tree without base
            tree = await self.client.create_tree(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                base_tree="",  # Empty base for first commit
                tree=tree_items
            )
        
        tree_sha = tree["sha"]
        
        # Step 5: Create genesis commit
        commit_message = f"""🏛️ InspecThor: Initialize Trusted Kernel Architecture

Blueprint: {blueprint_name}
Domain: {domain}

This commit establishes the formally verified project structure:
- kernel/ - Verified Dafny logic
- shell/ - Unverified I/O layer  
- claims/ - Specification documents
- generated/ - Compiled output

All future changes to kernel/ will be verified by Dafny.
"""
        
        parents = [base_sha] if base_sha else []
        
        commit = await self.client.create_commit(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            message=commit_message,
            tree=tree_sha,
            parents=parents
        )
        
        commit_sha = commit["sha"]
        
        # Step 6: Update branch reference
        github_repo = self.client._get_repo(installation_id, owner, repo)
        
        if base_sha:
            # Update existing branch
            branch_ref = github_repo.get_git_ref(f"heads/{default_branch}")
            branch_ref.edit(sha=commit_sha)
        else:
            # Create main branch for empty repo
            github_repo.create_git_ref(
                ref=f"refs/heads/{default_branch}",
                sha=commit_sha
            )
        
        logger.info(f"Genesis complete: {owner}/{repo} @ {commit_sha[:7]}")
        
        return GenesisResult(
            commit_sha=commit_sha,
            commit_url=f"https://github.com/{owner}/{repo}/commit/{commit_sha}",
            files_created=files_created,
            default_branch=default_branch
        )

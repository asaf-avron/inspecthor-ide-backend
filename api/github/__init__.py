"""
GitHub integration module for InSpecThor.
Handles App installation, webhooks, and stateless file operations.
"""

from .api_client import GitHubStatelessClient
from .app import GitHubAppManager

__all__ = ['GitHubStatelessClient', 'GitHubAppManager']

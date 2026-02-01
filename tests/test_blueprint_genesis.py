"""
Tests for Blueprint Genesis Service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.blueprint_genesis import BlueprintGenesisService, GenesisResult
from api.blueprints import parse_github_url


class TestParseGitHubUrl:
    """Test GitHub URL parsing."""
    
    def test_parse_https_url(self):
        owner, repo = parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_https_url_with_git_suffix(self):
        owner, repo = parse_github_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_https_url_with_trailing_slash(self):
        owner, repo = parse_github_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_ssh_url(self):
        owner, repo = parse_github_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_invalid_url_raises(self):
        with pytest.raises(ValueError):
            parse_github_url("https://gitlab.com/owner/repo")
    
    def test_parse_malformed_url_raises(self):
        with pytest.raises(ValueError):
            parse_github_url("not-a-url")


class TestBlueprintGenesisService:
    """Test Blueprint Genesis Service."""
    
    def test_generate_genesis_files_returns_all_required_files(self):
        """Verify all template files are generated."""
        service = BlueprintGenesisService()
        files = service._generate_genesis_files("Test Blueprint", "banking")
        
        required_files = [
            "blueprint.yaml",
            "kernel/Main.dfy",
            "shell/main.py",
            "claims/README.md",
            "generated/.gitkeep",
            ".inspecthor/config.yaml",
            ".github/workflows/verify.yml"
        ]
        
        for required_file in required_files:
            assert required_file in files, f"Missing file: {required_file}"
    
    def test_generate_genesis_files_includes_blueprint_name(self):
        """Verify blueprint name appears in manifest."""
        service = BlueprintGenesisService()
        files = service._generate_genesis_files("My Test Blueprint", "custom")
        
        assert 'name: "My Test Blueprint"' in files["blueprint.yaml"]
    
    def test_generate_genesis_files_includes_domain(self):
        """Verify domain appears in manifest."""
        service = BlueprintGenesisService()
        files = service._generate_genesis_files("Test", "healthcare")
        
        assert 'domain: "healthcare"' in files["blueprint.yaml"]
    
    def test_genesis_files_include_github_action(self):
        """Verify GitHub Actions workflow is included."""
        service = BlueprintGenesisService()
        files = service._generate_genesis_files("Test", "custom")
        
        workflow = files[".github/workflows/verify.yml"]
        assert "dafny verify" in workflow
        assert "dafny build --target:py" in workflow
    
    def test_kernel_file_is_valid_dafny(self):
        """Verify kernel template is valid Dafny syntax."""
        service = BlueprintGenesisService()
        files = service._generate_genesis_files("Test", "custom")
        
        kernel = files["kernel/Main.dfy"]
        assert "module Kernel" in kernel
        assert "method Init()" in kernel
        assert "ensures true" in kernel


@pytest.mark.asyncio
class TestBlueprintGenesisIntegration:
    """Integration tests for genesis workflow."""
    
    async def test_check_repo_is_empty_returns_true_for_empty(self):
        """Verify empty repo detection works."""
        service = BlueprintGenesisService()
        
        # Mock the client methods
        with patch.object(service, 'client') as mock_client:
            mock_client.get_default_branch.return_value = "main"
            mock_client.get_tree.return_value = []
            
            result = await service.check_repo_is_empty(123, "owner", "repo")
            assert result is True
    
    async def test_check_repo_is_empty_returns_true_for_readme_only(self):
        """Verify repo with only README is considered empty."""
        service = BlueprintGenesisService()
        
        with patch.object(service, 'client') as mock_client:
            mock_client.get_default_branch.return_value = "main"
            
            # Mock tree entry with README
            readme_entry = MagicMock()
            readme_entry.path = "README.md"
            mock_client.get_tree.return_value = [readme_entry]
            
            result = await service.check_repo_is_empty(123, "owner", "repo")
            assert result is True
    
    async def test_check_repo_is_empty_returns_false_for_non_empty(self):
        """Verify repo with code files is not considered empty."""
        service = BlueprintGenesisService()
        
        with patch.object(service, 'client') as mock_client:
            mock_client.get_default_branch.return_value = "main"
            
            # Mock tree entry with code file
            code_entry = MagicMock()
            code_entry.path = "src/main.py"
            mock_client.get_tree.return_value = [code_entry]
            
            result = await service.check_repo_is_empty(123, "owner", "repo")
            assert result is False
    
    async def test_initialize_repository_fails_on_non_empty_repo(self):
        """Verify genesis fails for non-empty repos when force=False."""
        service = BlueprintGenesisService()
        
        with patch.object(service, 'check_repo_is_empty', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            
            with pytest.raises(ValueError, match="not empty"):
                await service.initialize_repository(
                    installation_id=123,
                    owner="owner",
                    repo="repo",
                    blueprint_name="Test",
                    domain="custom",
                    force=False
                )
    
    async def test_initialize_repository_succeeds_with_force(self):
        """Verify genesis works for non-empty repos when force=True."""
        service = BlueprintGenesisService()
        
        with patch.object(service, 'client') as mock_client:
            # Mock all required methods
            mock_client.get_default_branch.return_value = "main"
            mock_client.get_ref = AsyncMock(return_value={"object": {"sha": "abc123"}})
            mock_client.create_tree = AsyncMock(return_value={"sha": "tree123"})
            mock_client.create_commit = AsyncMock(return_value={"sha": "commit456"})
            
            mock_repo = MagicMock()
            mock_ref = MagicMock()
            mock_repo.get_git_ref.return_value = mock_ref
            mock_client._get_repo.return_value = mock_repo
            
            result = await service.initialize_repository(
                installation_id=123,
                owner="owner",
                repo="repo",
                blueprint_name="Test Blueprint",
                domain="banking",
                force=True
            )
            
            assert result.commit_sha == "commit456"
            assert "github.com/owner/repo" in result.commit_url
            assert "blueprint.yaml" in result.files_created
            assert "kernel/Main.dfy" in result.files_created

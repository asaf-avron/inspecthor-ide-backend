"""
Tests for GitHub Protection Service (Task #6 - Iron Grip)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from api.services.github_protection_service import (
    GitHubProtectionService,
    ProtectionRule,
    RepositoryConfig
)


class TestGitHubProtectionService:
    """Test GitHub branch protection and Iron Grip enforcement"""

    def setup_method(self):
        """Create service for tests"""
        self.service = GitHubProtectionService(github_token="test_token_123")

    def test_initialization_with_token(self):
        """Test service initialization with token"""
        service = GitHubProtectionService(github_token="my_token")
        assert service.github_token == "my_token"
        assert service.api_base == "https://api.github.com"

    def test_initialization_without_token(self):
        """Test service initialization without token"""
        service = GitHubProtectionService()
        # Token should be None if not provided and env var not set
        assert service.github_token is None or isinstance(service.github_token, str)

    def test_protection_rule_defaults(self):
        """Test ProtectionRule default values"""
        rule = ProtectionRule(branch="main")

        assert rule.branch == "main"
        assert rule.require_pull_request == True
        assert rule.require_status_checks == True
        assert len(rule.required_status_checks) > 0
        assert any("dafny-verification" in check for check in rule.required_status_checks)

    def test_repository_config_defaults(self):
        """Test RepositoryConfig default values"""
        config = RepositoryConfig(owner="myorg", repo="myrepo")

        assert config.owner == "myorg"
        assert config.repo == "myrepo"
        assert "main" in config.protected_branches
        assert "master" in config.protected_branches

    @patch('requests.put')
    def test_enable_iron_grip_success(self, mock_put):
        """Test successfully enabling Iron Grip"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        success, message = self.service.enable_iron_grip(
            owner="testorg",
            repo="testrepo",
            branches=["main"]
        )

        assert success == True
        assert "enabled" in message.lower()
        assert mock_put.called

    @patch('requests.put')
    def test_enable_iron_grip_failure(self, mock_put):
        """Test Iron Grip enable failure"""
        # Mock failed API response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_put.return_value = mock_response

        success, message = self.service.enable_iron_grip(
            owner="testorg",
            repo="testrepo"
        )

        assert success == False
        assert "failed" in message.lower() or "403" in message

    def test_enable_iron_grip_without_token(self):
        """Test enabling Iron Grip without token"""
        service = GitHubProtectionService(github_token=None)

        success, message = service.enable_iron_grip(
            owner="testorg",
            repo="testrepo"
        )

        assert success == False
        assert "token" in message.lower()

    @patch('requests.delete')
    def test_disable_iron_grip_success(self, mock_delete):
        """Test successfully disabling Iron Grip"""
        # Mock successful deletion
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        success, message = self.service.disable_iron_grip(
            owner="testorg",
            repo="testrepo",
            branches=["main"]
        )

        assert success == True
        assert "disabled" in message.lower()

    @patch('requests.delete')
    def test_disable_iron_grip_not_protected(self, mock_delete):
        """Test disabling Iron Grip on unprotected branch"""
        # Mock 404 response (not found = not protected)
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        success, message = self.service.disable_iron_grip(
            owner="testorg",
            repo="testrepo",
            branches=["main"]
        )

        assert success == True
        assert "not protected" in message.lower() or "disabled" in message.lower()

    @patch('requests.get')
    def test_check_protection_status_protected(self, mock_get):
        """Test checking protection status for protected branch"""
        # Mock protected branch response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "required_status_checks": {
                "strict": True,
                "checks": []
            }
        }
        mock_get.return_value = mock_response

        is_protected, config = self.service.check_protection_status(
            owner="testorg",
            repo="testrepo",
            branch="main"
        )

        assert is_protected == True
        assert config is not None
        assert "required_status_checks" in config

    @patch('requests.get')
    def test_check_protection_status_unprotected(self, mock_get):
        """Test checking protection status for unprotected branch"""
        # Mock 404 response (not protected)
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        is_protected, config = self.service.check_protection_status(
            owner="testorg",
            repo="testrepo",
            branch="develop"
        )

        assert is_protected == False
        assert config is None

    @patch('requests.post')
    def test_report_status_check_success(self, mock_post):
        """Test successfully reporting a status check"""
        # Mock successful check creation
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        success, message = self.service.report_status_check(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123",
            check_name="Dafny Verification",
            status="completed",
            conclusion="success"
        )

        assert success == True
        assert "success" in message.lower()
        assert mock_post.called

    @patch('requests.post')
    def test_report_status_check_with_output(self, mock_post):
        """Test reporting check with detailed output"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        output = {
            "title": "Dafny Verification",
            "summary": "All specifications verified",
            "text": "Details here"
        }

        success, message = self.service.report_status_check(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123",
            check_name="Dafny Verification",
            status="completed",
            conclusion="success",
            output=output
        )

        assert success == True

        # Verify output was included in request
        call_args = mock_post.call_args
        assert call_args is not None
        json_data = call_args[1]['json']
        assert 'output' in json_data

    @patch('requests.get')
    def test_get_repository_checks_success(self, mock_get):
        """Test getting repository check runs"""
        # Mock check runs response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "check_runs": [
                {
                    "name": "dafny-verification",
                    "status": "completed",
                    "conclusion": "success"
                },
                {
                    "name": "drift-detection",
                    "status": "completed",
                    "conclusion": "success"
                }
            ]
        }
        mock_get.return_value = mock_response

        success, checks = self.service.get_repository_checks(
            owner="testorg",
            repo="testrepo",
            ref="main"
        )

        assert success == True
        assert len(checks) == 2
        assert checks[0]["name"] == "dafny-verification"

    @patch('requests.get')
    def test_validate_iron_grip_compliance_passing(self, mock_get):
        """Test compliance validation when all checks pass"""
        # Mock all checks passing
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "check_runs": [
                {
                    "name": "InspecThor - dafny-verification",
                    "status": "completed",
                    "conclusion": "success"
                },
                {
                    "name": "InspecThor - drift-detection",
                    "status": "completed",
                    "conclusion": "success"
                },
                {
                    "name": "InspecThor - component-validation",
                    "status": "completed",
                    "conclusion": "success"
                },
                {
                    "name": "InspecThor - call-graph-compliance",
                    "status": "completed",
                    "conclusion": "success"
                },
                {
                    "name": "InspecThor - proof-validation",
                    "status": "completed",
                    "conclusion": "success"
                }
            ]
        }
        mock_get.return_value = mock_response

        passes, results = self.service.validate_iron_grip_compliance(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123"
        )

        assert passes == True
        assert len(results["missing_checks"]) == 0
        assert len(results["failed_checks"]) == 0
        assert results["all_passed"] == True

    @patch('requests.get')
    def test_validate_iron_grip_compliance_failing(self, mock_get):
        """Test compliance validation when checks fail"""
        # Mock some checks failing
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "check_runs": [
                {
                    "name": "InspecThor - dafny-verification",
                    "status": "completed",
                    "conclusion": "failure"
                },
                {
                    "name": "InspecThor - drift-detection",
                    "status": "completed",
                    "conclusion": "success"
                }
            ]
        }
        mock_get.return_value = mock_response

        passes, results = self.service.validate_iron_grip_compliance(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123"
        )

        assert passes == False
        assert len(results["failed_checks"]) > 0
        assert results["all_passed"] == False

    @patch('requests.get')
    def test_validate_iron_grip_compliance_missing_checks(self, mock_get):
        """Test compliance validation with missing checks"""
        # Mock response with no checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"check_runs": []}
        mock_get.return_value = mock_response

        passes, results = self.service.validate_iron_grip_compliance(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123"
        )

        assert passes == False
        assert len(results["missing_checks"]) > 0
        assert results["all_passed"] == False

    def test_report_status_check_without_token(self):
        """Test reporting status check without token"""
        service = GitHubProtectionService(github_token=None)

        success, message = service.report_status_check(
            owner="testorg",
            repo="testrepo",
            commit_sha="abc123",
            check_name="Test Check",
            status="completed"
        )

        assert success == False
        assert "token" in message.lower()

    @patch('requests.put')
    def test_apply_branch_protection_with_all_options(self, mock_put):
        """Test applying branch protection with all options enabled"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        config = RepositoryConfig(owner="testorg", repo="testrepo")
        rule = ProtectionRule(
            branch="main",
            require_pull_request=True,
            require_approvals=2,
            dismiss_stale_reviews=True,
            require_code_owner_reviews=True,
            enforce_admins=True
        )

        success, message = self.service._apply_branch_protection(config, rule)

        assert success == True

        # Verify API was called with correct data
        call_args = mock_put.call_args
        json_data = call_args[1]['json']

        assert json_data['enforce_admins'] == True
        assert json_data['required_pull_request_reviews'] is not None
        assert json_data['required_pull_request_reviews']['required_approving_review_count'] == 2


if __name__ == "__main__":
    print("\n[TEST] Running GitHub Protection Service Tests\n")
    print("=" * 60)

    service = GitHubProtectionService(github_token="test_token")

    print("\n[1] Testing service initialization...")
    test = TestGitHubProtectionService()
    test.setup_method()
    test.test_initialization_with_token()
    print("[OK] Service initialization works")

    print("\n[2] Testing protection rule defaults...")
    test.test_protection_rule_defaults()
    print("[OK] Protection rules configured correctly")

    print("\n[3] Testing repository config...")
    test.test_repository_config_defaults()
    print("[OK] Repository config works")

    print("\n" + "=" * 60)
    print("[OK] All GitHub protection service tests completed!\n")

"""
Tests for file operations endpoints.

These tests cover the file CRUD operations including:
- Save file (create)
- Get file (read)
- List files
- Update file
- Delete file

Special focus on error cases that were previously missed:
- Saving to non-existent project
- Saving to project owned by another user
- Operating on files in projects you don't own
"""

import pytest
from fastapi.testclient import TestClient
import uuid

from api.main import app
from api.database import get_db, hash_api_key, Project, File


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_db():
    """Get test database session."""
    db = next(get_db())
    yield db
    db.rollback()


@pytest.fixture
def test_project(test_db):
    """Create a test project owned by dev_key_1."""
    project = Project(
        project_id=uuid.uuid4(),
        name="Test Project for Files",
        description="Testing file operations",
        api_key_hash=hash_api_key("dev_key_1")
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    yield project
    # Cleanup
    test_db.delete(project)
    test_db.commit()


@pytest.fixture
def other_user_project(test_db):
    """Create a test project owned by a different user."""
    project = Project(
        project_id=uuid.uuid4(),
        name="Other User Project",
        description="Owned by someone else",
        api_key_hash=hash_api_key("other_user_key")
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    yield project
    # Cleanup
    test_db.delete(project)
    test_db.commit()


class TestFileSave:
    """Tests for POST /api/files/save endpoint."""
    
    def test_save_file_success(self, client, test_project):
        """Successfully save a file to an owned project."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},
            json={
                "project_id": str(test_project.project_id),
                "filename": "test.md",
                "content": "# Test Content",
                "file_type": "md"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.md"
        assert "file_id" in data
    
    def test_save_file_nonexistent_project(self, client):
        """Saving to non-existent project should return 404."""
        fake_project_id = str(uuid.uuid4())
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},
            json={
                "project_id": fake_project_id,
                "filename": "test.md",
                "content": "# Test",
                "file_type": "md"
            }
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_save_file_wrong_owner(self, client, other_user_project):
        """Saving to project owned by another user should return 404 (project not visible)."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},  # Not the owner
            json={
                "project_id": str(other_user_project.project_id),
                "filename": "test.md",
                "content": "# Test",
                "file_type": "md"
            }
        )
        # Returns 404 because project is not visible to this user
        assert response.status_code == 404
    
    def test_save_file_empty_filename(self, client, test_project):
        """Saving with empty filename should fail validation."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},
            json={
                "project_id": str(test_project.project_id),
                "filename": "",
                "content": "# Test",
                "file_type": "md"
            }
        )
        # icontract precondition on Shell should catch this
        assert response.status_code in [400, 500]  # Either validation error or precondition
    
    def test_save_file_duplicate_filename(self, client, test_project, test_db):
        """Saving with duplicate filename in same project should fail."""
        # First, create a file
        existing_file = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="existing.md",
            content="# Existing",
            file_type="md"
        )
        test_db.add(existing_file)
        test_db.commit()
        
        try:
            response = client.post(
                "/api/files/save",
                headers={"X-API-Key": "dev_key_1"},
                json={
                    "project_id": str(test_project.project_id),
                    "filename": "existing.md",  # Duplicate
                    "content": "# Test",
                    "file_type": "md"
                }
            )
            assert response.status_code == 409  # Conflict
        finally:
            test_db.delete(existing_file)
            test_db.commit()


class TestFileGet:
    """Tests for GET /api/files/{file_id} endpoint."""
    
    def test_get_file_success(self, client, test_project, test_db):
        """Successfully get a file."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="getme.md",
            content="# Get Me",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "dev_key_1"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["filename"] == "getme.md"
            assert data["content"] == "# Get Me"
        finally:
            test_db.delete(file)
            test_db.commit()
    
    def test_get_file_not_found(self, client):
        """Getting non-existent file should return 404."""
        fake_file_id = str(uuid.uuid4())
        response = client.get(
            f"/api/files/{fake_file_id}",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert response.status_code == 404
    
    def test_get_file_wrong_owner(self, client, other_user_project, test_db):
        """Getting file from another user's project should return 404."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=other_user_project.project_id,
            filename="private.md",
            content="# Private",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "dev_key_1"}  # Wrong owner
            )
            assert response.status_code == 404
        finally:
            test_db.delete(file)
            test_db.commit()


class TestFileUpdate:
    """Tests for PUT /api/files/{file_id} endpoint."""
    
    def test_update_file_success(self, client, test_project, test_db):
        """Successfully update a file."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="update.md",
            content="# Original",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.put(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "dev_key_1"},
                json={"content": "# Updated Content"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["content"] == "# Updated Content"
        finally:
            test_db.delete(file)
            test_db.commit()
    
    def test_update_file_not_found(self, client):
        """Updating non-existent file should return 404."""
        fake_file_id = str(uuid.uuid4())
        response = client.put(
            f"/api/files/{fake_file_id}",
            headers={"X-API-Key": "dev_key_1"},
            json={"content": "# Updated"}
        )
        assert response.status_code == 404
    
    def test_update_file_wrong_owner(self, client, other_user_project, test_db):
        """Updating file from another user's project should return 403."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=other_user_project.project_id,
            filename="private.md",
            content="# Private",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.put(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "dev_key_1"},  # Wrong owner
                json={"content": "# Hacked!"}
            )
            assert response.status_code == 403
        finally:
            test_db.delete(file)
            test_db.commit()


class TestFileDelete:
    """Tests for DELETE /api/files/{file_id} endpoint."""
    
    def test_delete_file_success(self, client, test_project, test_db):
        """Successfully delete a file."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="deleteme.md",
            content="# Delete Me",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        response = client.delete(
            f"/api/files/{file.file_id}",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
    
    def test_delete_file_not_found(self, client):
        """Deleting non-existent file should return 404."""
        fake_file_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/files/{fake_file_id}",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert response.status_code == 404
    
    def test_delete_file_wrong_owner(self, client, other_user_project, test_db):
        """Deleting file from another user's project should return 403."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=other_user_project.project_id,
            filename="protected.md",
            content="# Protected",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.delete(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "dev_key_1"}  # Wrong owner
            )
            assert response.status_code == 403
        finally:
            # File should still exist
            test_db.refresh(file)
            test_db.delete(file)
            test_db.commit()


class TestFileList:
    """Tests for GET /api/files endpoint."""
    
    def test_list_files_empty(self, client, test_project):
        """List files when project has no files."""
        response = client.get(
            f"/api/files?project_id={test_project.project_id}",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["files"] == []
    
    def test_list_files_with_files(self, client, test_project, test_db):
        """List files when project has files."""
        file1 = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="file1.md",
            content="# File 1",
            file_type="md"
        )
        file2 = File(
            file_id=uuid.uuid4(),
            project_id=test_project.project_id,
            filename="file2.dfy",
            content="method Test() {}",
            file_type="dfy"
        )
        test_db.add(file1)
        test_db.add(file2)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files?project_id={test_project.project_id}",
                headers={"X-API-Key": "dev_key_1"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
        finally:
            test_db.delete(file1)
            test_db.delete(file2)
            test_db.commit()
    
    def test_list_files_other_user_project(self, client, other_user_project, test_db):
        """List files should not show files from other user's projects."""
        file = File(
            file_id=uuid.uuid4(),
            project_id=other_user_project.project_id,
            filename="secret.md",
            content="# Secret",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files?project_id={other_user_project.project_id}",
                headers={"X-API-Key": "dev_key_1"}  # Wrong owner
            )
            assert response.status_code == 200
            data = response.json()
            # Should not see the file
            assert data["total"] == 0
        finally:
            test_db.delete(file)
            test_db.commit()


class TestProjectStructureRefresh:
    """Tests for project structure endpoint reflecting file changes."""
    
    def test_project_structure_reflects_new_files(self, client, test_project, test_db):
        """Verify that project structure endpoint returns newly created files immediately."""
        # Get initial project structure
        initial_response = client.get(
            f"/api/projects/{test_project.project_id}/structure",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert initial_response.status_code == 200
        initial_data = initial_response.json()
        initial_file_count = len(initial_data["files"])
        
        # Create a new markdown file via API
        create_md_response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},
            json={
                "project_id": str(test_project.project_id),
                "filename": "new_file.md",
                "content": "# New File",
                "file_type": "md"
            }
        )
        assert create_md_response.status_code == 200
        md_file_id = create_md_response.json()["file_id"]
        
        # Get updated project structure
        updated_response = client.get(
            f"/api/projects/{test_project.project_id}/structure",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert updated_response.status_code == 200
        updated_data = updated_response.json()
        
        # Verify the new file appears in the structure
        assert len(updated_data["files"]) == initial_file_count + 1
        new_file = next((f for f in updated_data["files"] if f["file_id"] == md_file_id), None)
        assert new_file is not None
        assert new_file["filename"] == "new_file.md"
        assert new_file["file_type"] == "md"
        
        # Create a new Dafny file
        create_dfy_response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "dev_key_1"},
            json={
                "project_id": str(test_project.project_id),
                "filename": "spec.dfy",
                "content": "method Test() {}",
                "file_type": "dfy"
            }
        )
        assert create_dfy_response.status_code == 200
        dfy_file_id = create_dfy_response.json()["file_id"]
        
        # Get updated project structure again
        final_response = client.get(
            f"/api/projects/{test_project.project_id}/structure",
            headers={"X-API-Key": "dev_key_1"}
        )
        assert final_response.status_code == 200
        final_data = final_response.json()
        
        # Verify both new files appear in the structure
        assert len(final_data["files"]) == initial_file_count + 2
        dfy_file = next((f for f in final_data["files"] if f["file_id"] == dfy_file_id), None)
        assert dfy_file is not None
        assert dfy_file["filename"] == "spec.dfy"
        assert dfy_file["file_type"] == "dfy"
        
        # Cleanup
        client.delete(f"/api/files/{md_file_id}", headers={"X-API-Key": "dev_key_1"})
        client.delete(f"/api/files/{dfy_file_id}", headers={"X-API-Key": "dev_key_1"})


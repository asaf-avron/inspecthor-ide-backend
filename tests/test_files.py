"""
Tests for file operations endpoints.

These tests cover the file CRUD operations including:
- Save file (create)
- Get file (read)
- List files
- Update file
- Delete file

Special focus on error cases that were previously missed:
- Saving to non-existent blueprint
- Saving to blueprint owned by another user
- Operating on files in blueprints you don't own
"""

import pytest
import uuid

from api.database import hash_api_key, Blueprint, File


@pytest.fixture
def test_db(db_session):
    """Use the per-test SQLite session from conftest (tables are created and dropped per test)."""
    yield db_session
    db_session.rollback()


@pytest.fixture
def test_blueprint(test_db):
    """Create a test blueprint owned by test_api_key_123."""
    blueprint = Blueprint(
        blueprint_id=uuid.uuid4(),
        name="Test Blueprint for Files",
        description="Testing file operations",
        api_key_hash=hash_api_key("test_api_key_123")
    )
    test_db.add(blueprint)
    test_db.commit()
    test_db.refresh(blueprint)
    yield blueprint
    # Cleanup
    test_db.delete(blueprint)
    test_db.commit()


@pytest.fixture
def other_user_blueprint(test_db):
    """Create a test blueprint owned by a different user."""
    blueprint = Blueprint(
        blueprint_id=uuid.uuid4(),
        name="Other User Blueprint",
        description="Owned by someone else",
        api_key_hash=hash_api_key("other_user_key")
    )
    test_db.add(blueprint)
    test_db.commit()
    test_db.refresh(blueprint)
    yield blueprint
    # Cleanup
    test_db.delete(blueprint)
    test_db.commit()


class TestFileSave:
    """Tests for POST /api/files/save endpoint."""
    
    def test_save_file_success(self, client, test_blueprint):
        """Successfully save a file to an owned blueprint."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "test_api_key_123"},
            json={
                "blueprint_id": str(test_blueprint.blueprint_id),
                "filename": "test.md",
                "content": "# Test Content",
                "file_type": "md"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.md"
        assert "file_id" in data
    
    def test_save_file_nonexistent_blueprint(self, client):
        """Saving to non-existent blueprint should return 404."""
        fake_blueprint_id = str(uuid.uuid4())
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "test_api_key_123"},
            json={
                "blueprint_id": fake_blueprint_id,
                "filename": "test.md",
                "content": "# Test",
                "file_type": "md"
            }
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_save_file_wrong_owner(self, client, other_user_blueprint):
        """Saving to blueprint owned by another user should return 404 (blueprint not visible)."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "test_api_key_123"},  # Not the owner
            json={
                "blueprint_id": str(other_user_blueprint.blueprint_id),
                "filename": "test.md",
                "content": "# Test",
                "file_type": "md"
            }
        )
        # Returns 404 because blueprint is not visible to this user
        assert response.status_code == 404
    
    def test_save_file_empty_filename(self, client, test_blueprint):
        """Saving with empty filename should fail validation."""
        response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "test_api_key_123"},
            json={
                "blueprint_id": str(test_blueprint.blueprint_id),
                "filename": "",
                "content": "# Test",
                "file_type": "md"
            }
        )
        # icontract precondition on Shell should catch this
        assert response.status_code in [400, 500]  # Either validation error or precondition
    
    def test_save_file_duplicate_filename(self, client, test_blueprint, test_db):
        """Saving with duplicate filename in same blueprint should fail."""
        # First, create a file
        existing_file = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="existing.md",
            content="# Existing",
            file_type="md"
        )
        test_db.add(existing_file)
        test_db.commit()
        
        try:
            response = client.post(
                "/api/files/save",
                headers={"X-API-Key": "test_api_key_123"},
                json={
                    "blueprint_id": str(test_blueprint.blueprint_id),
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
    
    def test_get_file_success(self, client, test_blueprint, test_db):
        """Successfully get a file."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="getme.md",
            content="# Get Me",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "test_api_key_123"}
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
            headers={"X-API-Key": "test_api_key_123"}
        )
        assert response.status_code == 404
    
    def test_get_file_wrong_owner(self, client, other_user_blueprint, test_db):
        """Getting file from another user's blueprint should return 404."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=other_user_blueprint.blueprint_id,
            filename="private.md",
            content="# Private",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "test_api_key_123"}  # Wrong owner
            )
            assert response.status_code == 404
        finally:
            test_db.delete(file)
            test_db.commit()


class TestFileUpdate:
    """Tests for PUT /api/files/{file_id} endpoint."""
    
    def test_update_file_success(self, client, test_blueprint, test_db):
        """Successfully update a file."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="update.md",
            content="# Original",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.put(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "test_api_key_123"},
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
            headers={"X-API-Key": "test_api_key_123"},
            json={"content": "# Updated"}
        )
        assert response.status_code == 404
    
    def test_update_file_wrong_owner(self, client, other_user_blueprint, test_db):
        """Updating file from another user's blueprint should return 403."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=other_user_blueprint.blueprint_id,
            filename="private.md",
            content="# Private",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.put(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "test_api_key_123"},  # Wrong owner
                json={"content": "# Hacked!"}
            )
            assert response.status_code == 403
        finally:
            test_db.delete(file)
            test_db.commit()


class TestFileDelete:
    """Tests for DELETE /api/files/{file_id} endpoint."""
    
    def test_delete_file_success(self, client, test_blueprint, test_db):
        """Successfully delete a file."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="deleteme.md",
            content="# Delete Me",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        response = client.delete(
            f"/api/files/{file.file_id}",
            headers={"X-API-Key": "test_api_key_123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
    
    def test_delete_file_not_found(self, client):
        """Deleting non-existent file should return 404."""
        fake_file_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/files/{fake_file_id}",
            headers={"X-API-Key": "test_api_key_123"}
        )
        assert response.status_code == 404
    
    def test_delete_file_wrong_owner(self, client, other_user_blueprint, test_db):
        """Deleting file from another user's blueprint should return 403."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=other_user_blueprint.blueprint_id,
            filename="protected.md",
            content="# Protected",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.delete(
                f"/api/files/{file.file_id}",
                headers={"X-API-Key": "test_api_key_123"}  # Wrong owner
            )
            assert response.status_code == 403
        finally:
            # File should still exist
            test_db.refresh(file)
            test_db.delete(file)
            test_db.commit()


class TestFileList:
    """Tests for GET /api/files endpoint."""
    
    def test_list_files_empty(self, client, test_blueprint):
        """List files when blueprint has no files."""
        response = client.get(
            f"/api/files?blueprint_id={test_blueprint.blueprint_id}",
            headers={"X-API-Key": "test_api_key_123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["files"] == []
    
    def test_list_files_with_files(self, client, test_blueprint, test_db):
        """List files when blueprint has files."""
        file1 = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="file1.md",
            content="# File 1",
            file_type="md"
        )
        file2 = File(
            file_id=uuid.uuid4(),
            blueprint_id=test_blueprint.blueprint_id,
            filename="file2.dfy",
            content="method Test() {}",
            file_type="dfy"
        )
        test_db.add(file1)
        test_db.add(file2)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files?blueprint_id={test_blueprint.blueprint_id}",
                headers={"X-API-Key": "test_api_key_123"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
        finally:
            test_db.delete(file1)
            test_db.delete(file2)
            test_db.commit()
    
    def test_list_files_other_user_blueprint(self, client, other_user_blueprint, test_db):
        """List files should not show files from other user's blueprints."""
        file = File(
            file_id=uuid.uuid4(),
            blueprint_id=other_user_blueprint.blueprint_id,
            filename="secret.md",
            content="# Secret",
            file_type="md"
        )
        test_db.add(file)
        test_db.commit()
        
        try:
            response = client.get(
                f"/api/files?blueprint_id={other_user_blueprint.blueprint_id}",
                headers={"X-API-Key": "test_api_key_123"}  # Wrong owner
            )
            assert response.status_code == 200
            data = response.json()
            # Should not see the file
            assert data["total"] == 0
        finally:
            test_db.delete(file)
            test_db.commit()


class TestBlueprintStructureRefresh:
    """Tests for blueprint structure endpoint reflecting file changes."""
    
    def test_blueprint_structure_reflects_new_files(self, client, test_blueprint, test_db):
        """Verify that blueprint structure endpoint returns newly created files immediately."""
        # Get initial blueprint structure
        initial_response = client.get(
            f"/api/blueprints/{test_blueprint.blueprint_id}/structure",
            headers={"X-API-Key": "test_api_key_123"}
        )
        assert initial_response.status_code == 200
        initial_data = initial_response.json()
        initial_file_count = len(initial_data["files"])
        
        # Create a new markdown file via API
        create_md_response = client.post(
            "/api/files/save",
            headers={"X-API-Key": "test_api_key_123"},
            json={
                "blueprint_id": str(test_blueprint.blueprint_id),
                "filename": "new_file.md",
                "content": "# New File",
                "file_type": "md"
            }
        )
        assert create_md_response.status_code == 200
        md_file_id = create_md_response.json()["file_id"]
        
        # Get updated blueprint structure
        updated_response = client.get(
            f"/api/blueprints/{test_blueprint.blueprint_id}/structure",
            headers={"X-API-Key": "test_api_key_123"}
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
            headers={"X-API-Key": "test_api_key_123"},
            json={
                "blueprint_id": str(test_blueprint.blueprint_id),
                "filename": "spec.dfy",
                "content": "method Test() {}",
                "file_type": "dfy"
            }
        )
        assert create_dfy_response.status_code == 200
        dfy_file_id = create_dfy_response.json()["file_id"]
        
        # Get updated blueprint structure again
        final_response = client.get(
            f"/api/blueprints/{test_blueprint.blueprint_id}/structure",
            headers={"X-API-Key": "test_api_key_123"}
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
        client.delete(f"/api/files/{md_file_id}", headers={"X-API-Key": "test_api_key_123"})
        client.delete(f"/api/files/{dfy_file_id}", headers={"X-API-Key": "test_api_key_123"})

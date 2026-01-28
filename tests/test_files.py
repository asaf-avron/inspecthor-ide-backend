"""
Integration tests for File Management API endpoints
Tests the full HTTP stack to catch import errors, missing dependencies, etc.
"""

import pytest
from fastapi.testclient import TestClient
import uuid


def test_save_file_endpoint(client, headers, db_session):
    """Test saving a file - catches import errors and basic functionality"""
    # First create a project
    project_response = client.post(
        "/api/projects/",
        json={"name": "Test Project", "description": "Test"},
        headers=headers
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["project_id"]
    
    # Now save a file
    file_response = client.post(
        "/api/files/save",
        json={
            "project_id": project_id,
            "filename": "test.dfy",
            "content": "module Test { }",
            "file_type": "dfy"
        },
        headers=headers
    )
    
    # Should succeed (200 or 201)
    assert file_response.status_code in [200, 201], \
        f"Expected success status, got {file_response.status_code}: {file_response.text}"
    
    data = file_response.json()
    assert "file_id" in data
    assert data["filename"] == "test.dfy"


def test_update_file_endpoint(client, headers, db_session):
    """Test updating a file - catches import errors"""
    # Create project and file
    project_response = client.post(
        "/api/projects/",
        json={"name": "Test Project", "description": "Test"},
        headers=headers
    )
    project_id = project_response.json()["project_id"]
    
    # Save initial file
    save_response = client.post(
        "/api/files/save",
        json={
            "project_id": project_id,
            "filename": "test.dfy",
            "content": "module Test { }",
            "file_type": "dfy"
        },
        headers=headers
    )
    assert save_response.status_code in [200, 201]
    file_id = save_response.json()["file_id"]
    
    # Update file
    update_response = client.put(
        f"/api/files/{file_id}",
        json={
            "content": "module Test { method Test() { } }",
            "filename": "test.dfy"
        },
        headers=headers
    )
    
    assert update_response.status_code == 200
    data = update_response.json()
    assert "method Test()" in data["content"]


def test_delete_file_endpoint(client, headers, db_session):
    """Test deleting a file - catches import errors"""
    # Create project and file
    project_response = client.post(
        "/api/projects/",
        json={"name": "Test Project", "description": "Test"},
        headers=headers
    )
    project_id = project_response.json()["project_id"]
    
    # Save file
    save_response = client.post(
        "/api/files/save",
        json={
            "project_id": project_id,
            "filename": "test.dfy",
            "content": "module Test { }",
            "file_type": "dfy"
        },
        headers=headers
    )
    assert save_response.status_code in [200, 201]
    file_id = save_response.json()["file_id"]
    
    # Delete file
    delete_response = client.delete(
        f"/api/files/{file_id}",
        headers=headers
    )
    
    assert delete_response.status_code == 200


def test_list_files_endpoint(client, headers, db_session):
    """Test listing files - catches import errors"""
    # Create project
    project_response = client.post(
        "/api/projects/",
        json={"name": "Test Project", "description": "Test"},
        headers=headers
    )
    project_id = project_response.json()["project_id"]
    
    # Save a file
    save_response = client.post(
        "/api/files/save",
        json={
            "project_id": project_id,
            "filename": "test.dfy",
            "content": "module Test { }",
            "file_type": "dfy"
        },
        headers=headers
    )
    assert save_response.status_code in [200, 201]
    
    # List files
    list_response = client.get(
        f"/api/files?project_id={project_id}",
        headers=headers
    )
    
    assert list_response.status_code == 200
    data = list_response.json()
    assert "files" in data
    assert len(data["files"]) >= 1  # At least README + our file

"""
Tests for Project Management API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import uuid

from api.database import Project, File, UnitLink

# Import shared fixtures from conftest.py
# These are automatically available to all test files

def test_create_project(client, headers, db_session):
    """Test creating a project with bootstrap README"""
    response = client.post(
        "/api/projects/",
        json={"name": "Test Project", "description": "A test project"},
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["file_count"] == 1
    assert "redirect_url" in data
    assert data["redirect_url"].startswith("/app/")
    
    # Verify README was created
    project_id = data["project_id"]
    files = db_session.query(File).filter(File.project_id == project_id).all()
    assert len(files) == 1
    assert files[0].filename == "README.md"
    assert files[0].file_type == "md"
    assert "Test Project" in files[0].content

def test_create_project_duplicate_name(client, headers, db_session):
    """Test that duplicate project names are rejected (case-insensitive)"""
    # Create first project
    response1 = client.post(
        "/api/projects/",
        json={"name": "My Project"},
        headers=headers
    )
    assert response1.status_code == 201
    
    # Try to create duplicate (case-insensitive)
    response2 = client.post(
        "/api/projects/",
        json={"name": "my project"},  # Different case
        headers=headers
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()

def test_list_projects(client, headers, db_session, api_key_hash):
    """Test listing projects with pagination"""
    # Create multiple projects
    for i in range(5):
        project = Project(
            name=f"Project {i}",
            api_key_hash=api_key_hash
        )
        db_session.add(project)
    db_session.commit()
    
    response = client.get("/api/projects/", headers=headers, params={"limit": 3, "offset": 0})
    assert response.status_code == 200
    data = response.json()
    assert len(data["projects"]) == 3
    assert data["total"] == 5
    assert data["limit"] == 3
    assert data["offset"] == 0

def test_get_project_structure(client, headers, db_session, api_key_hash):
    """Test getting project structure (project + files in one RTT)"""
    # Create project with files
    project = Project(name="Test Project", api_key_hash=api_key_hash)
    db_session.add(project)
    db_session.flush()
    
    file1 = File(project_id=project.project_id, filename="file1.md", content="content1", file_type="md")
    file2 = File(project_id=project.project_id, filename="file2.dfy", content="content2", file_type="dfy")
    db_session.add_all([file1, file2])
    db_session.commit()
    
    response = client.get(f"/api/projects/{project.project_id}/structure", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["project"]["name"] == "Test Project"
    assert len(data["files"]) == 2
    assert data["files"][0]["filename"] in ["file1.md", "file2.dfy"]
    assert "content" not in data["files"][0]  # Should not include content

def test_get_project(client, headers, db_session, api_key_hash):
    """Test getting single project"""
    project = Project(name="Test Project", api_key_hash=api_key_hash)
    db_session.add(project)
    db_session.commit()
    
    response = client.get(f"/api/projects/{project.project_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["file_count"] == 0

def test_update_project(client, headers, db_session, api_key_hash):
    """Test updating project name and description"""
    project = Project(name="Old Name", description="Old desc", api_key_hash=api_key_hash)
    db_session.add(project)
    db_session.commit()
    
    response = client.put(
        f"/api/projects/{project.project_id}",
        json={"name": "New Name", "description": "New desc"},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "New desc"
    
    # Verify in database
    db_session.refresh(project)
    assert project.name == "New Name"
    assert project.description == "New desc"

def test_delete_project_cascade(client, headers, db_session, api_key_hash):
    """Test deleting project cascades to files and unit_links"""
    # Create project with files and unit links
    project = Project(name="Test Project", api_key_hash=api_key_hash)
    db_session.add(project)
    db_session.flush()
    
    file1 = File(project_id=project.project_id, filename="file1.md", content="content", file_type="md")
    file2 = File(project_id=project.project_id, filename="file2.dfy", content="content", file_type="dfy")
    db_session.add_all([file1, file2])
    db_session.flush()
    
    unit_link = UnitLink(
        root_file_id=file1.file_id,
        unit_file_id=file1.file_id,
        dafny_file_id=file2.file_id,
        start_line=1,
        end_line=10
    )
    db_session.add(unit_link)
    db_session.commit()
    
    # Delete project
    response = client.delete(f"/api/projects/{project.project_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["files_deleted"] == 2
    
    # Verify cascade delete
    assert db_session.query(Project).filter(Project.project_id == project.project_id).first() is None
    assert db_session.query(File).filter(File.project_id == project.project_id).count() == 0
    assert db_session.query(UnitLink).filter(UnitLink.link_id == unit_link.link_id).first() is None

def test_project_ownership_isolation(client, db_session):
    """Test that projects are isolated by API key"""
    api_key1 = "key1"
    api_key2 = "key2"
    headers1 = {"X-API-Key": api_key1}
    headers2 = {"X-API-Key": api_key2}
    
    # Create project with key1
    response1 = client.post(
        "/api/projects/",
        json={"name": "Project 1"},
        headers=headers1
    )
    assert response1.status_code == 201
    project_id = response1.json()["project_id"]
    
    # Try to access with key2
    response2 = client.get(f"/api/projects/{project_id}", headers=headers2)
    assert response2.status_code == 404  # Should not find (ownership isolation)

def test_project_name_validation(client, headers):
    """Test project name validation"""
    # Empty name
    response = client.post("/api/projects/", json={"name": ""}, headers=headers)
    assert response.status_code == 400
    
    # Name too long
    long_name = "a" * 256
    response = client.post("/api/projects/", json={"name": long_name}, headers=headers)
    assert response.status_code == 400

def test_project_description_validation(client, headers):
    """Test project description validation"""
    # Description too long
    long_desc = "a" * 1001
    response = client.post(
        "/api/projects/",
        json={"name": "Test", "description": long_desc},
        headers=headers
    )
    assert response.status_code == 400

def test_list_projects_sorting(client, headers, db_session, api_key_hash):
    """Test project list sorting"""
    # Create projects with different names
    project1 = Project(name="Alpha", api_key_hash=api_key_hash)
    project2 = Project(name="Beta", api_key_hash=api_key_hash)
    project3 = Project(name="Gamma", api_key_hash=api_key_hash)
    db_session.add_all([project1, project2, project3])
    db_session.commit()
    
    # Sort by name ascending
    response = client.get("/api/projects/", headers=headers, params={"sort": "name", "order": "asc"})
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert projects[0]["name"] == "Alpha"
    assert projects[1]["name"] == "Beta"
    assert projects[2]["name"] == "Gamma"

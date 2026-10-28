"""
Tests for Blueprint Management API endpoints
"""

import uuid

from api.database import Blueprint, File, UnitLink

# Import shared fixtures from conftest.py
# These are automatically available to all test files

def test_create_blueprint(client, headers, db_session):
    """Test creating a blueprint with bootstrap README"""
    response = client.post(
        "/api/blueprints",
        json={"name": "Test Blueprint", "description": "A test blueprint"},
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Blueprint"
    assert data["description"] == "A test blueprint"
    assert data["file_count"] == 1
    assert "redirect_url" in data
    assert data["redirect_url"].startswith("/app/")
    
    # Verify README was created
    blueprint_id = data["blueprint_id"]
    files = db_session.query(File).filter(File.blueprint_id == uuid.UUID(blueprint_id)).all()
    assert len(files) == 1
    assert files[0].filename == "README.md"
    assert files[0].file_type == "md"
    assert "Test Blueprint" in files[0].content

def test_create_blueprint_duplicate_name(client, headers, db_session):
    """Test that duplicate blueprint names are rejected (case-insensitive)"""
    # Create first blueprint
    response1 = client.post(
        "/api/blueprints",
        json={"name": "My Blueprint"},
        headers=headers
    )
    assert response1.status_code == 201
    
    # Try to create duplicate (case-insensitive)
    response2 = client.post(
        "/api/blueprints",
        json={"name": "my blueprint"},  # Different case
        headers=headers
    )
    assert response2.status_code == 409
    assert "name taken" in response2.json()["detail"].lower()

def test_list_blueprints(client, headers, db_session, api_key_hash):
    """Test listing blueprints with pagination"""
    # Create multiple blueprints
    for i in range(5):
        blueprint = Blueprint(
            name=f"Blueprint {i}",
            api_key_hash=api_key_hash
        )
        db_session.add(blueprint)
    db_session.commit()
    
    response = client.get("/api/blueprints/", headers=headers, params={"limit": 3, "offset": 0})
    assert response.status_code == 200
    data = response.json()
    assert len(data["blueprints"]) == 3
    assert data["total"] == 5
    assert data["limit"] == 3
    assert data["offset"] == 0

def test_get_blueprint_structure(client, headers, db_session, api_key_hash):
    """Test getting blueprint structure (blueprint + files in one RTT)"""
    # Create blueprint with files
    blueprint = Blueprint(name="Test Blueprint", api_key_hash=api_key_hash)
    db_session.add(blueprint)
    db_session.flush()
    
    file1 = File(blueprint_id=blueprint.blueprint_id, filename="file1.md", content="content1", file_type="md")
    file2 = File(blueprint_id=blueprint.blueprint_id, filename="file2.dfy", content="content2", file_type="dfy")
    db_session.add_all([file1, file2])
    db_session.commit()
    
    response = client.get(f"/api/blueprints/{blueprint.blueprint_id}/structure", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["blueprint"]["name"] == "Test Blueprint"
    assert len(data["files"]) == 2
    assert data["files"][0]["filename"] in ["file1.md", "file2.dfy"]
    assert "content" not in data["files"][0]  # Should not include content

def test_get_blueprint(client, headers, db_session, api_key_hash):
    """Test getting single blueprint"""
    blueprint = Blueprint(name="Test Blueprint", api_key_hash=api_key_hash)
    db_session.add(blueprint)
    db_session.commit()
    
    response = client.get(f"/api/blueprints/{blueprint.blueprint_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Blueprint"
    assert data["blueprint_id"] == str(blueprint.blueprint_id)

def test_update_blueprint(client, headers, db_session, api_key_hash):
    """Test updating blueprint details"""
    blueprint = Blueprint(name="Old Name", description="Old Desc", api_key_hash=api_key_hash)
    db_session.add(blueprint)
    db_session.commit()
    
    response = client.put(
        f"/api/blueprints/{blueprint.blueprint_id}",
        json={"name": "New Name", "description": "New Desc"},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "New Desc"
    
    # Verify in DB
    db_session.refresh(blueprint)
    assert blueprint.name == "New Name"
    assert blueprint.description == "New Desc"

def test_delete_blueprint(client, headers, db_session, api_key_hash):
    """Test deleting blueprint and its files"""
    blueprint = Blueprint(name="Delete Me", api_key_hash=api_key_hash)
    db_session.add(blueprint)
    db_session.flush()
    
    file = File(blueprint_id=blueprint.blueprint_id, filename="test.md", content="content", file_type="md")
    db_session.add(file)
    db_session.commit()
    
    # Verify it exists
    assert db_session.query(Blueprint).count() == 1
    assert db_session.query(File).count() == 1
    
    response = client.delete(f"/api/blueprints/{blueprint.blueprint_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["files_deleted"] == 1
    
    # Verify it's gone
    assert db_session.query(Blueprint).count() == 0
    assert db_session.query(File).count() == 0

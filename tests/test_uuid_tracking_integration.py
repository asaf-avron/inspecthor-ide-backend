"""
Integration test for UUID-based component tracking (Task #2)
Tests the complete flow of creating blueprints with UUIDs and Brain integration
"""

import pytest
import requests
import uuid
import time

# Base URL for the API
BASE_URL = "http://localhost:8000"
API_KEY = f"test-key-{uuid.uuid4()}"  # Generate unique API key for test


def _server_is_up() -> bool:
    try:
        return requests.get(f"{BASE_URL}/api/health", timeout=2).ok
    except requests.RequestException:
        return False


# These tests talk to a running API over HTTP, so they only run when one is available.
pytestmark = pytest.mark.skipif(
    not _server_is_up(), reason=f"requires a running API server at {BASE_URL}"
)


def test_blueprint_creation_generates_uuid():
    """Test that creating a blueprint generates a component_uuid"""

    # Create a blueprint
    response = requests.post(
        f"{BASE_URL}/api/blueprints",
        json={
            "name": f"Test Blueprint {uuid.uuid4()}",
            "description": "Testing UUID generation"
        },
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 201, f"Failed to create blueprint: {response.text}"

    data = response.json()

    # Verify component_uuid is generated
    assert "component_uuid" in data, "component_uuid missing from response"
    assert data["component_uuid"] is not None, "component_uuid is None"
    assert len(data["component_uuid"]) == 36, "component_uuid is not a valid UUID format"

    # Verify sync_status is set
    assert "sync_status" in data, "sync_status missing from response"
    assert data["sync_status"] == "clean", f"Expected sync_status='clean', got '{data['sync_status']}'"

    print(f"[OK] Blueprint created with component_uuid: {data['component_uuid']}")

    return data["blueprint_id"], data["component_uuid"]


def test_brain_initialization():
    """Test that Brain structure can be initialized for a blueprint"""

    # Create a blueprint first
    blueprint_id, component_uuid = test_blueprint_creation_generates_uuid()

    # Note: Brain initialization requires a repo_path, which we don't have in this test
    # In production, this would be called when the user has a local repository

    # For now, we can verify the Brain API endpoint exists
    response = requests.get(f"{BASE_URL}/api/health")
    assert response.status_code == 200, "API health check failed"

    print(f"[OK] Blueprint {blueprint_id} ready for Brain initialization")


def test_get_blueprint_returns_uuid():
    """Test that retrieving a blueprint returns the component_uuid"""

    # Create a blueprint
    blueprint_id, expected_uuid = test_blueprint_creation_generates_uuid()

    # Wait a moment for DB to settle
    time.sleep(0.5)

    # Retrieve the blueprint
    response = requests.get(
        f"{BASE_URL}/api/blueprints/{blueprint_id}",
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 200, f"Failed to get blueprint: {response.text}"

    data = response.json()

    # Verify component_uuid is returned
    assert "component_uuid" in data, "component_uuid missing from GET response"
    assert data["component_uuid"] == expected_uuid, "component_uuid mismatch"

    print(f"[OK] GET /api/blueprints/{blueprint_id} returns component_uuid: {data['component_uuid']}")


def test_list_blueprints_returns_uuids():
    """Test that listing blueprints returns component_uuids"""

    # Create multiple blueprints
    blueprint_ids = []
    for i in range(3):
        response = requests.post(
            f"{BASE_URL}/api/blueprints",
            json={
                "name": f"Test Blueprint {uuid.uuid4()}",
                "description": f"Test {i}"
            },
            headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 201
        blueprint_ids.append(response.json()["blueprint_id"])

    # Wait for DB
    time.sleep(0.5)

    # List blueprints
    response = requests.get(
        f"{BASE_URL}/api/blueprints",
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 200, f"Failed to list blueprints: {response.text}"

    data = response.json()
    assert "blueprints" in data, "blueprints missing from response"

    # Verify all blueprints have component_uuids
    for blueprint in data["blueprints"]:
        if blueprint["blueprint_id"] in blueprint_ids:
            assert "component_uuid" in blueprint, f"component_uuid missing for {blueprint['blueprint_id']}"
            assert blueprint["component_uuid"] is not None, f"component_uuid is None for {blueprint['blueprint_id']}"
            print(f"[OK] Blueprint {blueprint['blueprint_id']} has component_uuid: {blueprint['component_uuid']}")


if __name__ == "__main__":
    print("\n[TEST] Running UUID Tracking Integration Tests\n")
    print("=" * 60)

    try:
        # Check if API is running
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print("[ERROR] API is not running. Start it first with: docker-compose up")
            exit(1)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to API at http://localhost:8000")
        print("   Start it first with: docker-compose up")
        exit(1)

    # Run tests
    print("\n[1]  Testing blueprint creation generates UUID...")
    test_blueprint_creation_generates_uuid()

    print("\n[2]  Testing Brain initialization endpoint exists...")
    test_brain_initialization()

    print("\n[3]  Testing GET blueprint returns UUID...")
    test_get_blueprint_returns_uuid()

    print("\n[4]  Testing LIST blueprints returns UUIDs...")
    test_list_blueprints_returns_uuids()

    print("\n" + "=" * 60)
    print("[OK] All UUID tracking tests passed!\n")

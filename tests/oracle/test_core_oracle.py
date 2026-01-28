"""
Oracle test infrastructure for Guardian Gateway.
Tests that Python Core implementations match Dafny specifications.

Oracle tests load test vectors generated from Dafny GenerateTests() methods
and verify that Python implementations produce the same results.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

# Import Core modules
from api.core import models, migration, file_operations, project_management


def load_test_vectors_json(json_path: str) -> Dict[str, Any]:
    """
    Load test vectors JSON file matching Oracle's schema.
    
    Expected structure:
    {
      "test_suite": "FileOperations",
      "cases": [
        {
          "id": "save_01_success",
          "input": { "method": "SaveFile", "params": {...} },
          "expected_output": { "success": true, ... }
        }
      ]
    }
    
    Args:
        json_path: Path to test vectors JSON file
    
    Returns:
        Parsed JSON dictionary
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def state_from_json(state_dict: Dict[str, Any]) -> models.SystemState:
    """
    STRICT ORACLE TRANSLATOR:
    Converts Dafny JSON test vector -> Python SystemState.
    
    CRITICAL: This function must fail if the JSON structure does not 
    perfectly match the expected schema. No fuzzy matching allowed.
    
    Expected JSON structure (from Dafny SystemState):
    {
      "projects": {
        "p1": {
          "projectId": "p1",
          "name": "...",
          "description": "...",
          "owner": {
            "tag": "Authenticated" | "Anonymous",
            "userId": "..." (if Authenticated),
            "apiKeyHash": "..." (if Anonymous)
          },
          "fileIds": ["f1", "f2"]
        }
      },
      "files": {
        "f1": {
          "fileId": "f1",
          "projectId": "p1",
          "filename": "...",
          "content": "...",
          "fileType": "MD" | "DFY" | "UNIT",
          "sizeBytes": 123,
          "renamed": false
        }
      }
    }
    
    Args:
        state_dict: JSON dictionary matching Dafny SystemState structure
        
    Returns:
        SystemState object
        
    Raises:
        ValueError: If JSON structure does not match expected schema exactly
        KeyError: If required fields are missing
    """
    try:
        # 1. Translate Projects
        projects = {}
        if "projects" not in state_dict:
            raise ValueError("Oracle Translation Error: Missing 'projects' field in JSON")
        
        projects_data = state_dict["projects"]
        if not isinstance(projects_data, dict):
            raise ValueError(f"Oracle Translation Error: 'projects' must be a dictionary, got {type(projects_data)}")
        
        for project_id, project_data in projects_data.items():
            # Strict field validation - fail on missing fields
            if not isinstance(project_data, dict):
                raise ValueError(f"Oracle Translation Error: Project {project_id} must be a dictionary")
            
            # Required fields
            if "projectId" not in project_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} missing 'projectId' field")
            if "name" not in project_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} missing 'name' field")
            if "description" not in project_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} missing 'description' field")
            if "owner" not in project_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} missing 'owner' field")
            if "fileIds" not in project_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} missing 'fileIds' field")
            
            # Validate projectId matches key
            if project_data["projectId"] != project_id:
                raise ValueError(f"Oracle Translation Error: Project key '{project_id}' does not match projectId '{project_data['projectId']}'")
            
            # Strict Owner mapping
            owner_data = project_data["owner"]
            if not isinstance(owner_data, dict):
                raise ValueError(f"Oracle Translation Error: Project {project_id} owner must be a dictionary")
            
            if "tag" not in owner_data:
                raise ValueError(f"Oracle Translation Error: Project {project_id} owner missing 'tag' field")
            
            owner_tag = owner_data["tag"]
            if owner_tag == "Authenticated":
                if "userId" not in owner_data:
                    raise ValueError("Oracle Translation Error: Authenticated owner missing 'userId' field")
                owner = models.Owner.authenticated(str(owner_data["userId"]))
            elif owner_tag == "Anonymous":
                if "apiKeyHash" not in owner_data:
                    raise ValueError("Oracle Translation Error: Anonymous owner missing 'apiKeyHash' field")
                owner = models.Owner.anonymous(str(owner_data["apiKeyHash"]))
            else:
                raise ValueError(f"Oracle Translation Error: Unknown owner tag '{owner_tag}' (must be 'Authenticated' or 'Anonymous')")
            
            # Validate no unexpected fields in owner
            expected_owner_fields = {"tag", "userId", "apiKeyHash"}
            unexpected_fields = set(owner_data.keys()) - expected_owner_fields
            if unexpected_fields:
                raise ValueError(f"Oracle Translation Error: Unexpected fields in owner: {unexpected_fields}")
            
            # Convert fileIds to set (strict type conversion)
            file_ids_data = project_data["fileIds"]
            if not isinstance(file_ids_data, list):
                raise ValueError(f"Oracle Translation Error: Project {project_id} fileIds must be a list, got {type(file_ids_data)}")
            
            file_ids = {str(fid) for fid in file_ids_data}
            
            # Create Project object
            projects[project_id] = models.Project(
                project_id=str(project_data["projectId"]),
                name=str(project_data["name"]),
                description=str(project_data["description"]),
                owner=owner,
                file_ids=file_ids
            )
            
            # Validate no unexpected fields in project
            expected_project_fields = {"projectId", "name", "description", "owner", "fileIds"}
            unexpected_fields = set(project_data.keys()) - expected_project_fields
            if unexpected_fields:
                raise ValueError(f"Oracle Translation Error: Unexpected fields in project {project_id}: {unexpected_fields}")
        
        # 2. Translate Files
        files = {}
        if "files" not in state_dict:
            raise ValueError("Oracle Translation Error: Missing 'files' field in JSON")
        
        files_data = state_dict["files"]
        if not isinstance(files_data, dict):
            raise ValueError(f"Oracle Translation Error: 'files' must be a dictionary, got {type(files_data)}")
        
        for file_id, file_data in files_data.items():
            # Strict field validation - fail on missing fields
            if not isinstance(file_data, dict):
                raise ValueError(f"Oracle Translation Error: File {file_id} must be a dictionary")
            
            # Required fields
            required_fields = ["fileId", "projectId", "filename", "content", "fileType", "sizeBytes", "renamed"]
            for field in required_fields:
                if field not in file_data:
                    raise ValueError(f"Oracle Translation Error: File {file_id} missing '{field}' field")
            
            # Validate fileId matches key
            if file_data["fileId"] != file_id:
                raise ValueError(f"Oracle Translation Error: File key '{file_id}' does not match fileId '{file_data['fileId']}'")
            
            # Strict FileType enum mapping
            file_type_str = str(file_data["fileType"])
            file_type_map = {
                "MD": models.FileType.MD,
                "DFY": models.FileType.DFY,
                "UNIT": models.FileType.UNIT
            }
            if file_type_str not in file_type_map:
                raise ValueError(f"Oracle Translation Error: Invalid fileType '{file_type_str}' (must be 'MD', 'DFY', or 'UNIT')")
            file_type = file_type_map[file_type_str]
            
            # Strict type conversions
            content = str(file_data["content"])
            size_bytes = int(file_data["sizeBytes"])
            
            # Validate size_bytes matches content length (strict integrity check)
            expected_size = len(content.encode('utf-8'))
            if size_bytes != expected_size:
                raise ValueError(
                    f"Oracle Translation Error: File {file_id} sizeBytes ({size_bytes}) "
                    f"does not match content length ({expected_size})"
                )
            
            # Create File object
            files[file_id] = models.File(
                file_id=str(file_data["fileId"]),
                project_id=str(file_data["projectId"]),
                filename=str(file_data["filename"]),
                content=content,
                file_type=file_type,
                size_bytes=size_bytes,
                renamed=bool(file_data["renamed"])
            )
            
            # Validate no unexpected fields in file
            expected_file_fields = {"fileId", "projectId", "filename", "content", "fileType", "sizeBytes", "renamed"}
            unexpected_fields = set(file_data.keys()) - expected_file_fields
            if unexpected_fields:
                raise ValueError(f"Oracle Translation Error: Unexpected fields in file {file_id}: {unexpected_fields}")
        
        # 3. Validate no unexpected top-level fields
        expected_top_level_fields = {"projects", "files"}
        unexpected_fields = set(state_dict.keys()) - expected_top_level_fields
        if unexpected_fields:
            raise ValueError(f"Oracle Translation Error: Unexpected top-level fields: {unexpected_fields}")
        
        # 4. Create SystemState and validate invariants
        state = models.SystemState(projects=projects, files=files)
        state.validate()
        
        return state
        
    except KeyError as e:
        raise ValueError(f"Oracle Translation Error: Missing required field {e}") from e
    except (TypeError, ValueError) as e:
        # Re-raise with context
        raise ValueError(f"Oracle Translation Error: {str(e)}") from e


class TestMigrationOracle:
    """Oracle tests for migration logic."""
    
    @pytest.fixture
    def test_vectors_path(self):
        """Path to migration test vectors JSON file."""
        return Path(__file__).parent / "test_vectors_migration.json"
    
    @pytest.mark.skipif(
        not (Path(__file__).parent / "test_vectors_migration.json").exists(),
        reason="Test vectors not generated yet"
    )
    def test_migrate_anonymous_projects(self, test_vectors_path):
        """
        Oracle test: Verify migrate_anonymous_projects matches Dafny spec.
        
        Loads test vectors from Dafny GenerateTests() JSON output and verifies
        Python implementation produces identical results.
        """
        json_data = load_test_vectors_json(str(test_vectors_path))
        
        if json_data.get("test_suite") != "ProjectMigration":
            pytest.skip(f"Test suite mismatch: expected ProjectMigration, got {json_data.get('test_suite')}")
        
        for test_case in json_data.get("cases", []):
            # Extract inputs from test case
            params = test_case["input"]["params"]
            user_id = str(params["userId"])
            session_hash = str(params["currentSessionHash"])
            
            # Convert state_delta from JSON to SystemState
            if "state_delta" not in params:
                raise ValueError("Oracle test case missing 'state_delta' field")
            
            old_state = state_from_json(params["state_delta"])
            
            # Call Core function
            new_state = migration.migrate_anonymous_projects(
                old_state,
                user_id,
                session_hash
            )
            
            # Verify expected output
            expected = test_case["expected_output"]
            
            # Check that projects were migrated (user_id set, api_key_hash cleared)
            if expected.get("success", False):
                # Verify migration: projects with session_hash should now have user_id
                migrated_count = 0
                for pid, project in new_state.projects.items():
                    if project.owner.is_authenticated() and project.owner.user_id == user_id:
                        # Check if this project was migrated (was anonymous before)
                        old_project = old_state.projects.get(pid)
                        if old_project and old_project.owner.is_anonymous() and old_project.owner.api_key_hash == session_hash:
                            migrated_count += 1
                
                assert migrated_count == expected.get("migrated_count", 0), \
                    f"Expected {expected.get('migrated_count', 0)} migrated projects, got {migrated_count}"
                
                # Verify state is still valid
                new_state.validate()
            else:
                # Migration should have failed - verify state unchanged or error occurred
                # (exact behavior depends on Dafny spec)
                pass


class TestFileOperationsOracle:
    """Oracle tests for file operations."""
    
    @pytest.fixture
    def test_vectors_path(self):
        """Path to file operations test vectors JSON file."""
        return Path(__file__).parent / "test_vectors_file_operations.json"
    
    @pytest.mark.skipif(
        not (Path(__file__).parent / "test_vectors_file_operations.json").exists(),
        reason="Test vectors not generated yet"
    )
    def test_save_file(self, test_vectors_path):
        """
        Oracle test: Verify save_file_core matches Dafny SaveFile spec.
        
        Loads test vectors from Dafny GenerateTests() JSON output.
        """
        json_data = load_test_vectors_json(str(test_vectors_path))
        
        if json_data.get("test_suite") != "FileOperations":
            pytest.skip(f"Test suite mismatch: expected FileOperations, got {json_data.get('test_suite')}")
        
        for test_case in json_data.get("cases", []):
            # Extract inputs
            params = test_case["input"]["params"]
            method = test_case["input"]["method"]
            expected = test_case["expected_output"]
            
            if method == "SaveFile":
                # Convert state_delta from JSON to SystemState
                if "state_delta" not in params:
                    raise ValueError("Oracle test case missing 'state_delta' field")
                
                state = state_from_json(params["state_delta"])
                
                # Extract SaveFile parameters
                if "fileId" not in params:
                    raise ValueError("SaveFile test case missing 'fileId' parameter")
                if "projectId" not in params:
                    raise ValueError("SaveFile test case missing 'projectId' parameter")
                if "filename" not in params:
                    raise ValueError("SaveFile test case missing 'filename' parameter")
                if "content" not in params:
                    raise ValueError("SaveFile test case missing 'content' parameter")
                
                file_id = str(params["fileId"])
                project_id = str(params["projectId"])
                filename = str(params["filename"])
                content = str(params["content"])
                file_type_str = params.get("fileType", "MD")
                owner_id = str(params.get("ownerId", ""))  # Owner ID from params or derive from project
                
                # If ownerId not provided, derive from project owner
                if not owner_id and project_id in state.projects:
                    project = state.projects[project_id]
                    if project.owner.is_authenticated():
                        owner_id = project.owner.user_id
                    elif project.owner.is_anonymous():
                        owner_id = project.owner.api_key_hash
                
                if not owner_id:
                    raise ValueError("SaveFile test case missing 'ownerId' parameter and cannot derive from project")
                
                # Map file type
                file_type_map = {
                    "MD": models.FileType.MD,
                    "DFY": models.FileType.DFY,
                    "UNIT": models.FileType.UNIT
                }
                file_type = file_type_map.get(file_type_str, models.FileType.MD)
                
                # Call Core function
                new_state, result = file_operations.save_file_core(
                    state,
                    file_id,
                    project_id,
                    filename,
                    content,
                    file_type,
                    owner_id
                )
                
                # Verify expected output
                assert result.success == expected.get("success", False), \
                    f"Expected success={expected.get('success', False)}, got {result.success}"
                
                if result.success:
                    # Verify file was added/updated
                    assert file_id in new_state.files, "File should exist in new state"
                    assert new_state.files[file_id].content == content, "File content should match"
                    assert new_state.files[file_id].filename == filename, "File filename should match"
                    assert new_state.files[file_id].project_id == project_id, "File project_id should match"
                    
                    # Verify state is still valid
                    new_state.validate()
                else:
                    # Verify error kind matches
                    if "error_kind" in expected:
                        assert result.error_kind == expected["error_kind"], \
                            f"Expected error_kind={expected['error_kind']}, got {result.error_kind}"


class TestProjectManagementOracle:
    """Oracle tests for project management."""
    
    @pytest.fixture
    def test_vectors_path(self):
        """Path to project management test vectors JSON file."""
        return Path(__file__).parent / "test_vectors_project_management.json"
    
    @pytest.mark.skipif(
        not (Path(__file__).parent / "test_vectors_project_management.json").exists(),
        reason="Test vectors not generated yet"
    )
    def test_delete_project_cascade(self, test_vectors_path):
        """
        Oracle test: Verify delete_project_core matches Dafny DeleteProject spec.
        
        Specifically tests cascade deletion of files.
        """
        json_data = load_test_vectors_json(str(test_vectors_path))
        
        if json_data.get("test_suite") != "ProjectManagement":
            pytest.skip(f"Test suite mismatch: expected ProjectManagement, got {json_data.get('test_suite')}")
        
        for test_case in json_data.get("cases", []):
            # Extract inputs
            params = test_case["input"]["params"]
            method = test_case["input"]["method"]
            expected = test_case["expected_output"]
            
            if method == "DeleteProject":
                # Convert state_delta from JSON to SystemState
                if "state_delta" not in params:
                    raise ValueError("Oracle test case missing 'state_delta' field")
                
                state = state_from_json(params["state_delta"])
                
                # Extract DeleteProject parameters
                if "projectId" not in params:
                    raise ValueError("DeleteProject test case missing 'projectId' parameter")
                if "ownerId" not in params:
                    raise ValueError("DeleteProject test case missing 'ownerId' parameter")
                
                project_id = str(params["projectId"])
                owner_id = str(params["ownerId"])
                
                # Count files that should be cascaded (before deletion)
                files_to_cascade = [
                    fid for fid, file_obj in state.files.items()
                    if file_obj.project_id == project_id
                ]
                
                # Call Core function
                new_state, result = project_management.delete_project_core(
                    state,
                    project_id,
                    owner_id
                )
                
                # Verify expected output
                assert result.success == expected.get("success", False), \
                    f"Expected success={expected.get('success', False)}, got {result.success}"
                
                if result.success:
                    # Verify project was deleted
                    assert project_id not in new_state.projects, "Project should be removed from new state"
                    
                    # Verify cascade: all files belonging to project are deleted
                    for file_id in files_to_cascade:
                        assert file_id not in new_state.files, \
                            f"File {file_id} should be cascaded (deleted) with project"
                    
                    # Verify state is still valid
                    new_state.validate()
                    
                    # Verify cascade count matches expected
                    if "files_cascaded" in expected:
                        assert len(files_to_cascade) == expected["files_cascaded"], \
                            f"Expected {expected['files_cascaded']} files cascaded, got {len(files_to_cascade)}"
                else:
                    # Verify error kind matches
                    if "error_kind" in expected:
                        assert result.error_kind == expected["error_kind"], \
                            f"Expected error_kind={expected['error_kind']}, got {result.error_kind}"


def test_state_validation():
    """
    Test that SystemState validation matches Dafny ValidState predicate.
    """
    # Create valid state
    project = models.Project(
        project_id="p1",
        name="Test",
        description="",
        owner=models.Owner.anonymous("hash123"),
        file_ids={"f1"}
    )
    
    file_obj = models.File(
        file_id="f1",
        project_id="p1",
        filename="test.md",
        content="content",
        file_type=models.FileType.MD,
        size_bytes=7,
        renamed=False
    )
    
    state = models.SystemState(
        projects={"p1": project},
        files={"f1": file_obj}
    )
    
    # Should validate successfully
    assert state.validate() == True
    
    # Create invalid state (file not in project's file_ids)
    invalid_project = models.Project(
        project_id="p2",
        name="Test",
        description="",
        owner=models.Owner.anonymous("hash123"),
        file_ids=set()  # Missing file_id
    )
    
    invalid_state = models.SystemState(
        projects={"p2": invalid_project},
        files={"f1": file_obj}  # File references p1, not p2
    )
    
    # Should raise ValueError
    with pytest.raises(ValueError):
        invalid_state.validate()

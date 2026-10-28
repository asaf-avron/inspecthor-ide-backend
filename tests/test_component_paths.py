"""
Regression tests for component paths on files.

The refinement and runtime routes group files by `parent_path` (the component directory).
The column used to be missing from the File model, so those routes raised AttributeError.
"""

import uuid

from api.database import File


def _create_blueprint(client, headers) -> str:
    response = client.post(
        "/api/blueprints",
        json={"name": f"Components {uuid.uuid4()}"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["blueprint_id"]


def test_file_parent_path_defaults_to_blueprint_root(client, headers, db_session):
    blueprint_id = _create_blueprint(client, headers)

    files = db_session.query(File).filter(File.blueprint_id == uuid.UUID(blueprint_id)).all()

    assert files
    assert all(f.parent_path is None for f in files)


def test_complexity_report_reads_component_specs(client, headers, db_session):
    blueprint_id = _create_blueprint(client, headers)
    db_session.add(File(
        file_id=uuid.uuid4(),
        blueprint_id=uuid.UUID(blueprint_id),
        filename="spec.md",
        content="# Auth component\n\nUsers must log in.",
        file_type="md",
        parent_path="components/auth",
    ))
    db_session.commit()

    response = client.get(f"/api/refinement/complexity/{blueprint_id}", headers=headers)

    assert response.status_code == 200, response.text

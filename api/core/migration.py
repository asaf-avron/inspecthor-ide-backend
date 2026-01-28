"""
Migration logic: Manual synthesis from Dafny specification.
Pure function matching Dafny MigrateAnonymousProjects.

This is the "few-shot" example for the synthesis script.
Manually written to match the Dafny spec exactly.

See: api/verification/project_migration.dfy :: MigrateAnonymousProjects
"""

import icontract
from api.core.models import SystemState, Project, Owner


@icontract.require(
    lambda state, user_id, current_session_hash:
        state is not None and
        user_id is not None and
        len(user_id) > 0 and
        current_session_hash is not None and
        len(current_session_hash) > 0 and
        state.validate(),
    "Preconditions: Valid state, non-empty user_id and session_hash"
)
@icontract.ensure(
    lambda result, state, user_id, current_session_hash, OLD:
        result.validate() and
        # All projects owned by session_hash now owned by user_id
        all(
            result.projects[pid].owner == Owner.authenticated(user_id)
            for pid in result.projects
            if pid in OLD.get_value(lambda: state.projects) and
            OLD.get_value(lambda: state.projects[pid]).owner == Owner.anonymous(current_session_hash)
        ) and
        # Projects not owned by session_hash remain unchanged
        all(
            result.projects[pid] == OLD.get_value(lambda: state.projects[pid])
            for pid in result.projects
            if pid in OLD.get_value(lambda: state.projects) and
            OLD.get_value(lambda: state.projects[pid]).owner != Owner.anonymous(current_session_hash)
        ),
    "Postconditions: Valid state, migrated projects have new owner, other projects unchanged"
)
def migrate_anonymous_projects(
    state: SystemState,
    user_id: str,
    current_session_hash: str
) -> SystemState:
    """
    Migrate anonymous projects to authenticated user.
    
    Pure function matching Dafny MigrateAnonymousProjects exactly.
    Takes immutable state, returns new immutable state.
    No side effects, no database access.
    
    This function implements the logic from:
    api/verification/project_migration.dfy :: MigrateAnonymousProjects
    
    Args:
        state: Current system state snapshot
        user_id: UUID of authenticated user
        current_session_hash: API key hash of current session
    
    Returns:
        New SystemState with migrated projects
    
    Security Property (Theorem_Isolation):
        Projects NOT owned by current_session_hash are never modified.
    """
    # 1. Identify Candidate Projects (The 'Filter')
    # Logic: Projects owned by THIS session hash
    candidates = {
        pid for pid, project in state.projects.items()
        if project.owner == Owner.anonymous(current_session_hash)
    }
    
    # 2. Transform State (The 'Map')
    new_projects = {}
    for pid, project in state.projects.items():
        if pid in candidates:
            # TRANSITION: Anonymous -> Authenticated
            new_project = Project(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                owner=Owner.authenticated(user_id),
                file_ids=project.file_ids
            )
            new_projects[pid] = new_project
        else:
            # PRESERVE: Untouched
            new_projects[pid] = project
    
    # 3. Return New State
    new_state = SystemState(projects=new_projects, files=state.files)
    
    # Validate invariants
    new_state.validate()
    
    return new_state

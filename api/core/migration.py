"""
Migration logic: Manual synthesis from Dafny specification.
Pure function matching Dafny MigrateAnonymousProjects.

This is the "few-shot" example for the synthesis script.
Manually written to match the Dafny spec exactly.

See: api/verification/project_migration.dfy :: MigrateAnonymousProjects
"""

import icontract
from api.core.models import SystemState, Blueprint, Owner


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
        # All blueprints owned by session_hash now owned by user_id
        all(
            result.blueprints[pid].owner == Owner.authenticated(user_id)
            for pid in result.blueprints
            if pid in OLD.get_value(lambda: state.blueprints) and
            OLD.get_value(lambda: state.blueprints[pid]).owner == Owner.anonymous(current_session_hash)
        ) and
        # Blueprints not owned by session_hash remain unchanged
        all(
            result.blueprints[pid] == OLD.get_value(lambda: state.blueprints[pid])
            for pid in result.blueprints
            if pid in OLD.get_value(lambda: state.blueprints) and
            OLD.get_value(lambda: state.blueprints[pid]).owner != Owner.anonymous(current_session_hash)
        ),
    "Postconditions: Valid state, migrated blueprints have new owner, other blueprints unchanged"
)
def migrate_anonymous_projects(
    state: SystemState,
    user_id: str,
    current_session_hash: str
) -> SystemState:
    """
    Migrate anonymous blueprints to authenticated user.
    
    Pure function matching Dafny MigrateAnonymousBlueprints exactly.
    Takes immutable state, returns new immutable state.
    No side effects, no database access.
    
    This function implements the logic from:
    api/verification/project_migration.dfy :: MigrateAnonymousProjects
    
    Args:
        state: Current system state snapshot
        user_id: UUID of authenticated user
        current_session_hash: API key hash of current session
    
    Returns:
        New SystemState with migrated blueprints
    
    Security Property (Theorem_Isolation):
        Blueprints NOT owned by current_session_hash are never modified.
    """
    # 1. Identify Candidate Blueprints (The 'Filter')
    # Logic: Blueprints owned by THIS session hash
    candidates = {
        pid for pid, blueprint in state.blueprints.items()
        if blueprint.owner == Owner.anonymous(current_session_hash)
    }
    
    # 2. Transform State (The 'Map')
    new_blueprints = {}
    for pid, blueprint in state.blueprints.items():
        if pid in candidates:
            # TRANSITION: Anonymous -> Authenticated
            new_blueprint = Blueprint(
                blueprint_id=blueprint.blueprint_id,
                name=blueprint.name,
                description=blueprint.description,
                owner=Owner.authenticated(user_id),
                file_ids=blueprint.file_ids
            )
            new_blueprints[pid] = new_blueprint
        else:
            # PRESERVE: Untouched
            new_blueprints[pid] = blueprint
    
    # 3. Return New State
    new_state = SystemState(blueprints=new_blueprints, files=state.files)
    
    # Validate invariants
    new_state.validate()
    
    return new_state

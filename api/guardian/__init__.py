"""
Guardian module: Restricted AST gate for the Pure Functional Core.

Enforces the Architectural Directive (Provenance of Truth): only Python code
that passes the AST whitelist may be sent to the deterministic Transpiler.
"""

from .ast_whitelist import (
    ALLOWED_NODE_TYPES,
    ILLEGAL_NODE_TYPES,
    PURE_CALL_NAMES,
    PURE_CALL_ATTR,
    get_allowed_node_types,
    get_illegal_node_types,
    is_call_pure,
)
from .guard import GuardianResult, check_python_source

__all__ = [
    "ALLOWED_NODE_TYPES",
    "ILLEGAL_NODE_TYPES",
    "PURE_CALL_NAMES",
    "PURE_CALL_ATTR",
    "get_allowed_node_types",
    "get_illegal_node_types",
    "is_call_pure",
    "GuardianResult",
    "check_python_source",
]

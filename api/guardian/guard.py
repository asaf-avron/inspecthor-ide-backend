"""
Guardian AST Gate: Rejects "dirty" Python before transpilation.

Traverses Python AST and rejects code that contains:
- Any illegal node type (Import, Try, Global, etc.)
- Any Call to a non-pure function (not in PURE_CALL_NAMES / PURE_CALL_ATTR)
- Any node type not in the allowed whitelist (strict Pure Functional Core)

On rejection, the pipeline must return REJECTED_BY_ARCHITECT and must not
send code to the Transpiler or Dafny.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

from .ast_whitelist import (
    ALLOWED_NODE_TYPES,
    ILLEGAL_NODE_TYPES,
    is_call_pure,
)


@dataclass
class GuardianResult:
    """Result of the Guardian AST gate check."""

    passed: bool
    """True if code is pure and may be sent to the Transpiler."""

    reason: Optional[str] = None
    """Human-readable reason when passed=False."""

    node_type: Optional[str] = None
    """AST node type that caused rejection (e.g. 'Import', 'Call')."""

    line: Optional[int] = None
    column: Optional[int] = None
    """Source location of the violating node."""

    status: str = "OK"
    """'OK' when passed; 'REJECTED_BY_ARCHITECT' when rejected."""


def check_python_source(source: str) -> GuardianResult:
    """
    Check Python source against the restricted AST whitelist.

    Returns GuardianResult with passed=True if the code is a valid Pure
    Functional Core; otherwise passed=False and status=REJECTED_BY_ARCHITECT
    with reason and location.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return GuardianResult(
            passed=False,
            reason=f"Syntax error: {e.msg}",
            line=getattr(e, "lineno", None),
            column=getattr(e, "offset", None),
            status="REJECTED_BY_ARCHITECT",
        )

    return _check_ast(tree)


def _check_ast(node: ast.AST) -> GuardianResult:
    """Recursively check AST; return first violation or OK."""
    node_type = type(node).__name__

    # 1. Explicitly illegal node types
    if node_type in ILLEGAL_NODE_TYPES:
        return GuardianResult(
            passed=False,
            reason=f"Illegal node in Pure Functional Core: {node_type}",
            node_type=node_type,
            line=getattr(node, "lineno", None),
            column=getattr(node, "col_offset", None),
            status="REJECTED_BY_ARCHITECT",
        )

    # 2. Call only allowed if target is pure
    if isinstance(node, ast.Call):
        if not is_call_pure(node):
            return GuardianResult(
                passed=False,
                reason="Call to non-pure function (not in whitelist)",
                node_type="Call",
                line=getattr(node, "lineno", None),
                column=getattr(node, "col_offset", None),
                status="REJECTED_BY_ARCHITECT",
            )

    # 3. Strict whitelist: reject any node type not in allowed set
    if node_type not in ALLOWED_NODE_TYPES:
        return GuardianResult(
            passed=False,
            reason=f"Node type not in Pure Functional Core whitelist: {node_type}",
            node_type=node_type,
            line=getattr(node, "lineno", None),
            column=getattr(node, "col_offset", None),
            status="REJECTED_BY_ARCHITECT",
        )

    # Recurse into children
    for child in ast.iter_child_nodes(node):
        result = _check_ast(child)
        if not result.passed:
            return result

    return GuardianResult(passed=True, status="OK")

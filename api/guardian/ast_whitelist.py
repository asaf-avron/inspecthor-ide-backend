"""
Restricted AST Whitelist for the Guardian (Pure Functional Core).

Per the Architectural Directive (Provenance of Truth), the Transpiler must only
accept Python code that is a "Pure Functional Core." This module defines the
allowed and illegal AST node types for restricted AST traversal.

Verification Bridge flow:
  1. Specification (.dfy trait) is ground truth (Trust Registry).
  2. LLM/Coder produces Python implementation.
  3. Guardian checks Python against this whitelist; if dirty → REJECTED_BY_ARCHITECT.
  4. Transpiler (deterministic AST→Dafny) translates only whitelisted Python to Dafny.
  5. Dafny solver verifies transpiled output against the contract.

Allowed (Pure Functional Core):
  - BinOp: binary operations (+, -, *, /, %, etc.)
  - Compare: comparisons (==, <, >, etc.)
  - Assign: assignment to local variables
  - FunctionDef: function definitions whose body passes the guardian check
  - Plus expression/statement nodes required for the above: Constant, Name,
    Return, Expr, Load, Store, Subscript, Index, Tuple, List, UnaryOp, BoolOp,
    If, For, While (pure loops), Pass, arguments, etc.

Illegal (outside core / side effects):
  - Import, ImportFrom: no imports inside the core; dependencies are resolved externally
  - Call: to non-pure libraries (e.g. pandas, open, print); see PURE_CALL_NAMES for allowed
  - Try, TryExcept: no exception handling in the pure core
  - Global, Nonlocal: no global state
  - With, AsyncWith: no context managers (I/O)
  - AsyncFor, etc.: no async in pure core
"""

from __future__ import annotations

import ast
from typing import FrozenSet, Set, Tuple

# --- Allowed AST node types (Pure Functional Core) ---
# Nodes that may appear in code accepted by the Guardian for transpilation.

_ALLOWED_NAMES: Tuple[str, ...] = (
    # Expressions
    "BinOp",
    "UnaryOp",
    "Compare",
    "Constant",
    "Name",
    "Load",
    "Store",
    "Subscript",
    "Index",
    "Slice",
    "Tuple",
    "List",
    "Set",
    "Dict",
    "BoolOp",
    "Attribute",
    "Lambda",
    "IfExp",
    "ListComp",
    "SetComp",
    "DictComp",
    "GeneratorExp",
    "comprehension",
    "Starred",
    "FormattedValue",
    "JoinedStr",
    "NameConstant",  # Python 3.7 and earlier (True, False, None)
    # Statements
    "Assign",
    "AugAssign",
    "Return",
    "Expr",
    "Pass",
    "If",
    "For",
    "While",
    "Break",
    "Continue",
    "FunctionDef",
    "arguments",
    "arg",
    "keyword",
    # Module/function structure (minimal)
    "Module",
    "Interactive",
    "Expression",
    # Operators (BinOp, Compare, BoolOp, UnaryOp operands)
    "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow", "LShift", "RShift",
    "BitOr", "BitXor", "BitAnd", "MatMult",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
    "And", "Or",
    "UAdd", "USub", "Not", "Invert",
)

ALLOWED_NODE_TYPES: FrozenSet[str] = frozenset(_ALLOWED_NAMES)

# --- Illegal AST node types ---
# Presence of any of these in the submitted Python triggers REJECTED_BY_ARCHITECT.

_ILLEGAL_NAMES: Tuple[str, ...] = (
    "Import",
    "ImportFrom",
    "Try",
    "TryExcept",  # Python 3.7 and earlier
    "Global",
    "Nonlocal",
    "With",
    "AsyncWith",
    "AsyncFor",
    "AsyncFunctionDef",
    "ClassDef",
    "Raise",
    "Assert",  # Often used for debug; can be disallowed in strict pure core
)

ILLEGAL_NODE_TYPES: FrozenSet[str] = frozenset(_ILLEGAL_NAMES)

# --- Call: conditionally allowed ---
# Call nodes are allowed only when the call target is in PURE_CALL_NAMES
# (builtins / pure functions). Any other Call (e.g. open, print, pandas.*) is illegal.

PURE_CALL_NAMES: FrozenSet[str] = frozenset({
    "len", "range", "int", "str", "float", "bool", "abs", "min", "max", "sum",
    "list", "tuple", "dict", "set", "frozenset", "sorted", "reversed", "enumerate",
    "zip", "map", "filter", "all", "any", "round", "divmod", "pow", "ord", "chr",
    "isinstance", "hasattr", "getattr", "setattr",  # getattr/setattr can be restricted if needed
})

# Attribute calls allowed as pure (e.g. str.split, list.append in pure sense - or restrict)
# For strict pure core we only allow builtin function names above; method calls
# (e.g. x.append) can be disallowed or whitelisted per method.
PURE_CALL_ATTR: FrozenSet[str] = frozenset({
    "split", "join", "strip", "lower", "upper", "replace", "startswith", "endswith",
    "append", "extend", "insert", "pop", "copy", "index", "count", "sort", "reverse",
})

# --- Documentation for backend/docs ---
AST_WHITELIST_DOC = """
# Guardian AST Whitelist

The Guardian enforces a **Restricted AST Traversal** so that only "Pure Functional Core"
Python is sent to the deterministic Transpiler and then to the Dafny solver.

## Allowed node types

- **BinOp**, **Compare**, **Assign**, **FunctionDef** (if body is pure), plus:
- Expression nodes: Constant, Name, Load, Store, Subscript, Index, Tuple, List, Dict, Set,
  UnaryOp, BoolOp, Attribute, Lambda, IfExp, comprehensions, etc.
- Statement nodes: Return, Expr, Pass, If, For, While, Break, Continue, AugAssign,
  arguments, arg, keyword.

## Illegal node types

- **Import**, **ImportFrom**: No imports inside the core.
- **Try** / **TryExcept**: No exception handling in the pure core.
- **Global**, **Nonlocal**: No global state.
- **With**, **AsyncWith**, **AsyncFor**, **AsyncFunctionDef**, **ClassDef**, **Raise**.

## Call nodes

- **Call** is allowed only when the invoked function is in the pure whitelist:
  - Builtins: len, range, int, str, float, bool, abs, min, max, sum, list, tuple, dict, set,
    sorted, reversed, enumerate, zip, map, filter, all, any, round, divmod, pow, ord, chr,
    isinstance, hasattr, getattr.
- Any other Call (e.g. open, print, pandas.*) triggers **REJECTED_BY_ARCHITECT**.
"""


def get_allowed_node_types() -> FrozenSet[str]:
    """Return the set of allowed AST node type names."""
    return ALLOWED_NODE_TYPES


def get_illegal_node_types() -> FrozenSet[str]:
    """Return the set of illegal AST node type names."""
    return ILLEGAL_NODE_TYPES


def is_call_pure(call_node: ast.Call) -> bool:
    """
    Return True if this Call is to a whitelisted pure function.
    """
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id in PURE_CALL_NAMES
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr in PURE_CALL_ATTR
    return False

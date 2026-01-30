# Guardian AST Whitelist (Restricted AST Traversal)

The Guardian enforces a **Restricted AST Traversal** so that only "Pure Functional Core" Python is sent to the deterministic Transpiler and then to the Dafny solver. This document summarizes the whitelist; the canonical definition is in `api/guardian/ast_whitelist.py`.

## Rationale (Provenance of Truth)

Per the Architectural Directive:

- The **Transpiler** is the **Verification Bridge**: it must translate Python to Dafny in a deterministic way (no LLM as auditor).
- Only code that stays within the **Pure Functional Core** may be transpiled. Any "dirty" code (imports, I/O calls, try/except, etc.) must be rejected **before** transpilation with status **REJECTED_BY_ARCHITECT**.

## Allowed node types

- **BinOp**, **Compare**, **Assign**, **FunctionDef** (if body is pure), plus:
- Expression nodes: `Constant`, `Name`, `Load`, `Store`, `Subscript`, `Index`, `Tuple`, `List`, `Dict`, `Set`, `UnaryOp`, `BoolOp`, `Attribute`, `Lambda`, `IfExp`, comprehensions.
- Statement nodes: `Return`, `Expr`, `Pass`, `If`, `For`, `While`, `Break`, `Continue`, `AugAssign`, `arguments`, `arg`, `keyword`.

## Illegal node types

- **Import**, **ImportFrom**: No imports inside the core.
- **Try** / **TryExcept**: No exception handling in the pure core.
- **Global**, **Nonlocal**: No global state.
- **With**, **AsyncWith**, **AsyncFor**, **AsyncFunctionDef**, **ClassDef**, **Raise**.

## Call nodes

**Call** is allowed only when the invoked function is in the pure whitelist (e.g. `len`, `range`, `int`, `str`, `min`, `max`, `sum`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `all`, `any`, `isinstance`, etc.). Any other call (e.g. `open`, `print`, `pandas.*`) triggers **REJECTED_BY_ARCHITECT**.

See `api/guardian/ast_whitelist.py` for `PURE_CALL_NAMES` and `PURE_CALL_ATTR`.

## Usage

The Guardian gate is implemented in `api/guardian/guard.py`. It traverses the Python AST and rejects code that contains any illegal node or a non-pure `Call`. On rejection, the pipeline returns status **REJECTED_BY_ARCHITECT** and does not send code to the Transpiler or Dafny.

"""
Deterministic Python AST to Dafny transpiler (Verification Bridge).

Maps whitelisted Python AST nodes to Dafny method body statements.
This component is programmatic (no LLM); it is the mandatory Verification Bridge
per the Architectural Directive. Python code must pass the Guardian AST gate
before being sent here.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class TranspileResult:
    """Result of AST-to-Dafny transpilation."""
    dafny_code: str
    success: bool
    error: Optional[str] = None
    method_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Python type hint name -> Dafny type
PYTHON_TO_DAFNY_TYPE: Dict[str, str] = {
    "int": "int",
    "bool": "bool",
    "str": "string",
    "float": "real",
    "list": "seq",
    "dict": "map",
    "tuple": "seq",
    "Optional": "?",  # prefix for optional
}


def _python_type_to_dafny(annotation: Optional[ast.expr]) -> str:
    """Convert Python type annotation to Dafny type string."""
    if annotation is None:
        return "int"  # default
    try:
        s = ast.unparse(annotation)
    except Exception:
        return "int"
    # Handle simple names
    if s in PYTHON_TO_DAFNY_TYPE:
        return PYTHON_TO_DAFNY_TYPE[s]
    # Handle subscripted: list[int] -> seq<int>, dict[str,int] -> map<string,int>
    if isinstance(annotation, ast.Subscript):
        value = annotation.value
        if isinstance(value, ast.Name):
            slice_val = getattr(annotation, "slice", None)
            if value.id == "list" and slice_val is not None:
                inner = _python_type_to_dafny(slice_val)
                return f"seq<{inner}>"
            if value.id == "dict" and slice_val is not None:
                if isinstance(slice_val, (ast.Tuple, ast.List)) and len(getattr(slice_val, "elts", [])) >= 2:
                    elts = slice_val.elts
                    k = _python_type_to_dafny(elts[0])
                    v = _python_type_to_dafny(elts[1])
                    return f"map<{k},{v}>"
                return "map<int,int>"
    return "int"


class DafnyEmitter(ast.NodeVisitor):
    """
    Visits whitelisted Python AST and emits Dafny method body statements.
    Assumes the AST has already passed the Guardian gate.
    """

    def __init__(self, indent: str = "    "):
        self.indent = indent
        self.lines: List[str] = []
        self._local_vars: Dict[str, bool] = {}  # name -> declared in this block
        self._depth = 0
        self._in_method_body = False  # True when visiting statements of the top-level method

    def _emit(self, stmt: str) -> None:
        self.lines.append(self.indent * (self._depth + 1) + stmt)

    def _expr(self, node: ast.AST) -> str:
        """Emit expression and return the Dafny expression string."""
        if isinstance(node, ast.Constant):
            if node.value is True:
                return "true"
            if node.value is False:
                return "false"
            if node.value is None:
                return "null"
            if isinstance(node.value, str):
                return f'"{node.value}"'
            return str(node.value)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.BinOp):
            left = self._expr(node.left)
            right = self._expr(node.right)
            op = self._binop(node.op)
            return f"({left} {op} {right})"
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                # chained comparison: a < b < c -> (a < b) && (b < c)
                parts = []
                parts.append(self._expr(node.left))
                for i, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                    parts.append(self._compare_op(op))
                    parts.append(self._expr(comp))
                    if i < len(node.comparators) - 1:
                        parts.append("&&")
                return "(" + " ".join(parts) + ")"
            op = self._compare_op(node.ops[0])
            return f"({self._expr(node.left)} {op} {self._expr(node.comparators[0])})"
        if isinstance(node, ast.BoolOp):
            op = "&&" if isinstance(node.op, ast.And) else "||"
            parts = [self._expr(v) for v in node.values]
            return "(" + f" {op} ".join(parts) + ")"
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return f"!({self._expr(node.operand)})"
            if isinstance(node.op, ast.USub):
                return f"-({self._expr(node.operand)})"
            return f"({self._expr(node.operand)})"
        if isinstance(node, ast.Subscript):
            value = self._expr(node.value)
            if isinstance(node.slice, ast.Constant):
                idx = node.slice.value
                return f"{value}[{idx}]"
            if hasattr(node.slice, "value"):
                idx = self._expr(node.slice.value)  # type: ignore[attr-defined]
                return f"{value}[{idx}]"
            return f"{value}[0]"
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.IfExp):
            cond = self._expr(node.test)
            then_e = self._expr(node.body)
            else_e = self._expr(node.orelse)
            return f"if {cond} then {then_e} else {else_e}"
        if isinstance(node, ast.Attribute):
            base = self._expr(node.value)
            return f"{base}.{node.attr}"
        # Fallback: unparse
        try:
            return ast.unparse(node)
        except Exception:
            return "0"

    def _binop(self, op: ast.operator) -> str:
        if isinstance(op, ast.Add):
            return "+"
        if isinstance(op, ast.Sub):
            return "-"
        if isinstance(op, ast.Mult):
            return "*"
        if isinstance(op, ast.FloorDiv):
            return "/"
        if isinstance(op, ast.Mod):
            return "%"
        if isinstance(op, ast.Pow):
            return "**"
        if isinstance(op, ast.BitAnd):
            return "&&"
        if isinstance(op, ast.BitOr):
            return "||"
        return "+"

    def _compare_op(self, op: ast.cmpop) -> str:
        if isinstance(op, ast.Eq):
            return "=="
        if isinstance(op, ast.NotEq):
            return "!="
        if isinstance(op, ast.Lt):
            return "<"
        if isinstance(op, ast.LtE):
            return "<="
        if isinstance(op, ast.Gt):
            return ">"
        if isinstance(op, ast.GtE):
            return ">="
        return "=="

    def _call(self, node: ast.Call) -> str:
        """Emit Dafny for a pure call (len, range, etc.)."""
        if isinstance(node.func, ast.Name):
            name = node.func.id
            args = ", ".join(self._expr(a) for a in node.args)
            if name == "len":
                return f"|{args}|"
            return f"{name}({args})"
        if isinstance(node.func, ast.Attribute):
            base = self._expr(node.func.value)
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{base}.{node.func.attr}({args})"
        return "0"

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) != 1:
            return
        t = node.targets[0]
        value = self._expr(node.value)
        if isinstance(t, ast.Name):
            if t.id not in self._local_vars:
                self._local_vars[t.id] = True
                self._emit(f"var {t.id} := {value};")
            else:
                self._emit(f"{t.id} := {value};")
        elif isinstance(t, ast.Subscript):
            # x[i] = e -> x := x[i := e]
            try:
                target = ast.unparse(t)
                self._emit(f"{target} := {value};")
            except Exception:
                self._emit(f"// assign to subscript: {value};")
        else:
            self._emit(f"// assign: {value};")

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target = self._expr(node.target)
        value = self._expr(node.value)
        op = self._binop(node.op)
        if isinstance(node.target, ast.Name):
            self._emit(f"{node.target.id} := {target} {op} {value};")
        else:
            self._emit(f"// aug assign: {target} {op} {value};")

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            self._emit("return;")
        else:
            self._emit(f"return {self._expr(node.value)};")

    def visit_Expr(self, node: ast.Expr) -> None:
        # Standalone expression (e.g. call used as statement) - emit as assert or skip
        self._emit(f"// {self._expr(node.value)};")

    def visit_Pass(self, node: ast.Pass) -> None:
        pass

    def visit_If(self, node: ast.If) -> None:
        cond = self._expr(node.test)
        self._emit(f"if {cond} {{")
        self._depth += 1
        for s in node.body:
            self.visit(s)
        self._depth -= 1
        if node.orelse:
            self._emit("} else {")
            self._depth += 1
            for s in node.orelse:
                self.visit(s)
            self._depth -= 1
        self._emit("}")

    def visit_For(self, node: ast.For) -> None:
        # for x in range(n): body -> for i := 0 to n - 1 { body }
        target = node.target
        iter_ = node.iter
        if isinstance(target, ast.Name) and isinstance(iter_, ast.Call):
            if isinstance(iter_.func, ast.Name) and iter_.func.id == "range":
                if len(iter_.args) == 1:
                    n = self._expr(iter_.args[0])
                    self._emit(f"for i := 0 to {n} - 1")
                elif len(iter_.args) == 2:
                    start = self._expr(iter_.args[0])
                    end = self._expr(iter_.args[1])
                    self._emit(f"for i := {start} to {end} - 1")
                else:
                    self._emit("for i := 0 to 0")
                self._emit("{")
                self._depth += 1
                # Map target name to i or use i
                for s in node.body:
                    self.visit(s)
                self._depth -= 1
                self._emit("}")
                return
        # Generic for: emit as while with iterator (simplified)
        self._emit("// for loop (simplified)")
        for s in node.body:
            self.visit(s)

    def visit_While(self, node: ast.While) -> None:
        cond = self._expr(node.test)
        self._emit(f"while {cond}")
        self._emit("{")
        self._depth += 1
        for s in node.body:
            self.visit(s)
        self._depth -= 1
        self._emit("}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._in_method_body:
            # Nested function: skip (do not emit a second method)
            self._emit("// nested function skipped")
            return
        # Emit single method: signature + body
        args = node.args
        param_names = [a.arg for a in args.args]
        param_types = [_python_type_to_dafny(a.annotation) for a in args.args]
        params = ", ".join(f"{n}: {t}" for n, t in zip(param_names, param_types))
        return_ann = _python_type_to_dafny(node.returns) if node.returns else "int"
        # Single return value
        self.lines.append(f"method {node.name}({params}) returns (result: {return_ann})")
        self.lines.append("{")
        self._depth = 0
        self._local_vars = {}
        self._in_method_body = True
        for s in node.body:
            self.visit(s)
        self._in_method_body = False
        self.lines.append("}")


def transpile_python_to_dafny(
    python_source: str,
    method_name: Optional[str] = None,
    contract_signature: Optional[str] = None,
) -> TranspileResult:
    """
    Transpile Python source (single function) to a Dafny method.

    The Python code must have already passed the Guardian AST gate.
    If contract_signature is provided, it is used as the method signature;
    otherwise the signature is inferred from the Python function.
    """
    try:
        tree = ast.parse(python_source)
    except SyntaxError as e:
        return TranspileResult(
            dafny_code="",
            success=False,
            error=f"Python syntax error: {e.msg}",
        )

    # Find first top-level function
    func_node: Optional[ast.FunctionDef] = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_node = node
            break

    if func_node is None:
        return TranspileResult(
            dafny_code="",
            success=False,
            error="No function definition found in Python source",
        )

    if method_name and func_node.name != method_name:
        # Look for the requested method
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                func_node = node
                break
        else:
            return TranspileResult(
                dafny_code="",
                success=False,
                error=f"Function '{method_name}' not found",
            )

    emitter = DafnyEmitter()
    try:
        emitter.visit(func_node)
    except StopIteration:
        pass

    dafny_code = "\n".join(emitter.lines)
    return TranspileResult(
        dafny_code=dafny_code,
        success=True,
        method_name=func_node.name,
        metadata={"param_count": len(func_node.args.args)},
    )

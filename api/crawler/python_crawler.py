"""
Python AST Crawler for InSpecThor.
Extracts execution slices from Python code using static analysis.
"""

import ast
from typing import Callable, List, Dict, Set, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionSlice:
    """
    Represents an execution slice for verification.
    Contains the anchor function and all its dependencies.
    """
    anchor_code: str  # The anchored function code
    dependencies: List[str]  # Resolved dependency code
    external_stubs: List[str]  # Stubs for 3rd party imports
    imports_map: Dict[str, str]  # import name -> resolved path
    type_hints: Dict[str, str]  # variable name -> type annotation


class PythonCrawler:
    """
    Crawls Python code to extract execution slices.
    Uses AST (Abstract Syntax Tree) analysis, not RAG.
    """
    
    def __init__(self):
        self._visited_files: Set[str] = set()
        self._stdlib_modules = {
            'os', 'sys', 'math', 'datetime', 'time', 'json', 'hashlib',
            'collections', 'itertools', 'functools', 're', 'typing'
        }
    
    def extract_slice(
        self,
        anchor_path: str,
        function_name: str,
        file_fetcher: Callable[[str], str]
    ) -> ExecutionSlice:
        """
        Extract execution slice for an anchored function.
        
        Args:
            anchor_path: Path to file containing anchor (e.g., "src/auth/token.py")
            function_name: Name of anchored function
            file_fetcher: Callable that fetches file content by path
        
        Returns:
            ExecutionSlice with anchor and dependencies
        """
        self._visited_files.clear()
        
        # Fetch and parse anchor file
        source = file_fetcher(anchor_path)
        tree = ast.parse(source)
        
        # Find the anchored function
        func_node = self._find_function(tree, function_name)
        if not func_node:
            raise ValueError(f"Function '{function_name}' not found in {anchor_path}")
        
        # Extract type hints
        type_hints = self._extract_type_hints(func_node)
        
        # Find all function calls and imports
        calls = self._find_function_calls(func_node)
        imports = self._extract_imports(tree)
        
        # Resolve dependencies recursively
        dependencies = []
        imports_map = {}
        external_stubs = []
        
        for call_name in calls:
            # Check if it's a local function
            local_func = self._find_function(tree, call_name)
            if local_func:
                dependencies.append(ast.unparse(local_func))
                continue
            
            # Check if it's an imported function
            if call_name in imports:
                import_path = imports[call_name]
                
                # Skip stdlib imports
                if self._is_stdlib(import_path):
                    external_stubs.append(self._generate_stub(call_name, "stdlib"))
                    continue
                
                # Resolve relative imports
                resolved_path = self._resolve_import_path(anchor_path, import_path)
                
                # Fetch and parse dependency
                if resolved_path and resolved_path not in self._visited_files:
                    self._visited_files.add(resolved_path)
                    try:
                        dep_source = file_fetcher(resolved_path)
                        dep_tree = ast.parse(dep_source)
                        dep_func = self._find_function(dep_tree, call_name)
                        if dep_func:
                            dependencies.append(ast.unparse(dep_func))
                            imports_map[call_name] = resolved_path
                    except FileNotFoundError:
                        # External 3rd party dependency
                        external_stubs.append(self._generate_stub(call_name, "external"))
        
        # Get anchor code
        anchor_code = ast.unparse(func_node)
        
        return ExecutionSlice(
            anchor_code=anchor_code,
            dependencies=dependencies,
            external_stubs=external_stubs,
            imports_map=imports_map,
            type_hints=type_hints
        )
    
    def _find_function(self, tree: ast.AST, function_name: str) -> Optional[ast.FunctionDef]:
        """Find a function definition by name in AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return node
        return None
    
    def _find_function_calls(self, func_node: ast.FunctionDef) -> Set[str]:
        """Extract all function calls from a function."""
        calls = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    # Handle method calls like obj.method()
                    if isinstance(node.func.value, ast.Name):
                        # Could be a module method
                        calls.add(f"{node.func.value.id}.{node.func.attr}")
        return calls
    
    def _extract_imports(self, tree: ast.AST) -> Dict[str, str]:
        """
        Extract import statements from AST.
        Returns dict mapping imported name to module path.
        """
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = f"{module}.{alias.name}" if module else alias.name
        return imports
    
    def _extract_type_hints(self, func_node: ast.FunctionDef) -> Dict[str, str]:
        """Extract type annotations from function."""
        type_hints = {}
        
        # Parameter types
        for arg in func_node.args.args:
            if arg.annotation:
                type_hints[arg.arg] = ast.unparse(arg.annotation)
        
        # Return type
        if func_node.returns:
            type_hints["__return__"] = ast.unparse(func_node.returns)
        
        return type_hints
    
    def _is_stdlib(self, module_path: str) -> bool:
        """Check if module is from Python standard library."""
        root_module = module_path.split('.')[0]
        return root_module in self._stdlib_modules
    
    def _resolve_import_path(self, current_file: str, import_path: str) -> Optional[str]:
        """
        Resolve relative import to absolute file path.
        
        Args:
            current_file: Path to current file (e.g., "src/auth/token.py")
            import_path: Import path (e.g., "auth.helpers" or ".helpers")
        
        Returns:
            Resolved file path (e.g., "src/auth/helpers.py")
        """
        # Handle relative imports
        if import_path.startswith('.'):
            current_dir = str(Path(current_file).parent)
            levels = len(import_path) - len(import_path.lstrip('.'))
            path_parts = current_dir.split('/')
            
            # Go up directory levels
            for _ in range(levels - 1):
                if path_parts:
                    path_parts.pop()
            
            # Add relative path
            relative_path = import_path.lstrip('.')
            if relative_path:
                path_parts.extend(relative_path.split('.'))
            
            resolved = '/'.join(path_parts) + '.py'
            return resolved
        
        # Handle absolute imports
        # Convert "auth.helpers" to "src/auth/helpers.py"
        path_parts = import_path.split('.')
        
        # Try common src directories
        for prefix in ['src/', 'lib/', '']:
            resolved = prefix + '/'.join(path_parts) + '.py'
            # File fetcher will handle if it doesn't exist
            return resolved
        
        return None
    
    def _generate_stub(self, function_name: str, source: str) -> str:
        """
        Generate a Dafny stub for external functions.
        
        Args:
            function_name: Name of external function
            source: "stdlib" or "external"
        
        Returns:
            Dafny axiom/stub code
        """
        if source == "stdlib":
            # Common stdlib functions
            stubs = {
                "len": "axiom {:extern} function len<T>(s: seq<T>): int ensures len(s) >= 0",
                "str": "axiom {:extern} function str(x: int): string",
                "int": "axiom {:extern} function int(s: string): int",
                "hashlib.sha256": "axiom {:extern} function sha256(s: string): string"
            }
            return stubs.get(function_name, f"axiom {{:extern}} function {function_name}(...): ?")
        
        # External 3rd party
        return f"axiom {{:extern}} function {function_name}(...): ?"
    
    def detect_pure_functions(self, source: str) -> List[Dict[str, any]]:
        """
        Detect pure functions suitable for auto-anchoring (Brownfield Scanner).
        
        Criteria:
        - Type-annotated parameters and return
        - No global state access
        - No I/O operations
        - Reasonable complexity (< 50 LOC)
        
        Args:
            source: Python source code
        
        Returns:
            List of function metadata dicts
        """
        tree = ast.parse(source)
        pure_functions = []
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            
            # Check type annotations
            if not node.returns:
                continue
            
            has_annotations = all(arg.annotation for arg in node.args.args)
            if not has_annotations:
                continue
            
            # Check complexity
            lines = ast.unparse(node).count('\n')
            if lines > 50:
                continue
            
            # Check for side effects
            if self._has_side_effects(node):
                continue
            
            # This looks like a pure function!
            pure_functions.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "params": [arg.arg for arg in node.args.args],
                "return_type": ast.unparse(node.returns),
                "complexity": lines
            })
        
        return pure_functions
    
    def _has_side_effects(self, func_node: ast.FunctionDef) -> bool:
        """Check if function has side effects (I/O, global access)."""
        for node in ast.walk(func_node):
            # Check for I/O operations
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['print', 'open', 'input']:
                        return True
                elif isinstance(node.func, ast.Attribute):
                    # Check for file I/O, database, network
                    if node.func.attr in ['write', 'read', 'execute', 'commit']:
                        return True
            
            # Check for global keyword
            if isinstance(node, ast.Global):
                return True
            
            # Check for nonlocal keyword
            if isinstance(node, ast.Nonlocal):
                return True
        
        return False

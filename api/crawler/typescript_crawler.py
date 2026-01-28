"""
TypeScript/JavaScript Crawler for InSpecThor.
Uses tree-sitter for AST parsing and execution slice extraction.
"""

from typing import Callable, List, Dict, Set, Optional, Any
from dataclasses import dataclass
from pathlib import Path

# Note: tree-sitter bindings would be used here
# For now, this is a stub implementation that will be completed
# when the browser-side crawler is working

@dataclass
class TSExecutionSlice:
    """
    Represents an execution slice for TypeScript/JavaScript.
    """
    anchor_code: str
    dependencies: List[str]
    external_stubs: List[str]
    imports_map: Dict[str, str]
    type_annotations: Dict[str, str]


class TypeScriptCrawler:
    """
    Crawls TypeScript/JavaScript code using tree-sitter.
    Server-side implementation for webhook verification.
    """
    
    def __init__(self):
        self._visited_files: Set[str] = set()
        # Common Node.js stdlib modules
        self._stdlib_modules = {
            'fs', 'path', 'os', 'crypto', 'http', 'https', 'url',
            'util', 'events', 'stream', 'buffer', 'process'
        }
    
    def extract_slice(
        self,
        anchor_path: str,
        function_name: str,
        file_fetcher: Callable[[str], str]
    ) -> TSExecutionSlice:
        """
        Extract execution slice for an anchored TypeScript function.
        
        Args:
            anchor_path: Path to file containing anchor
            function_name: Name of anchored function
            file_fetcher: Callable that fetches file content by path
        
        Returns:
            TSExecutionSlice with anchor and dependencies
        """
        # TODO: Implement tree-sitter parsing
        # For now, return a basic stub
        
        source = file_fetcher(anchor_path)
        
        # Simple regex-based extraction (temporary)
        # This should be replaced with tree-sitter parsing
        anchor_code = self._extract_function_simple(source, function_name)
        
        return TSExecutionSlice(
            anchor_code=anchor_code,
            dependencies=[],
            external_stubs=[],
            imports_map={},
            type_annotations={}
        )
    
    def _extract_function_simple(self, source: str, function_name: str) -> str:
        """
        Simple function extraction (temporary until tree-sitter is integrated).
        """
        lines = source.split('\n')
        in_function = False
        function_lines = []
        brace_count = 0
        
        for i, line in enumerate(lines):
            # Look for function declaration
            if not in_function:
                if f"function {function_name}" in line or f"{function_name}(" in line:
                    in_function = True
                    function_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    continue
            
            if in_function:
                function_lines.append(line)
                brace_count += line.count('{') - line.count('}')
                
                # End of function
                if brace_count == 0 and '{' in ''.join(function_lines):
                    break
        
        return '\n'.join(function_lines) if function_lines else f"// Function {function_name} not found"
    
    def detect_pure_functions(self, source: str) -> List[Dict[str, Any]]:
        """
        Detect pure functions suitable for auto-anchoring.
        
        Args:
            source: TypeScript source code
        
        Returns:
            List of function metadata dicts
        """
        # TODO: Implement with tree-sitter
        # For now, return empty list
        return []
    
    def _is_stdlib(self, module_path: str) -> bool:
        """Check if module is from Node.js stdlib."""
        root_module = module_path.split('/')[0]
        return root_module in self._stdlib_modules
    
    def _resolve_import_path(self, current_file: str, import_path: str) -> Optional[str]:
        """
        Resolve TypeScript import to file path.
        
        Args:
            current_file: Path to current file
            import_path: Import path (e.g., "./helpers", "../utils")
        
        Returns:
            Resolved file path
        """
        # Handle relative imports
        if import_path.startswith('.'):
            current_dir = str(Path(current_file).parent)
            resolved = str(Path(current_dir) / import_path)
            
            # Try common extensions
            for ext in ['.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.js']:
                if Path(resolved + ext).exists():
                    return resolved + ext
            
            return resolved + '.ts'
        
        # Handle absolute imports from node_modules (external)
        return None

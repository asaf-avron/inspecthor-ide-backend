"""
Dafny Contract + Implementation Merger for InSpecThor.
Combines Dafny contracts (from specs) with implementations (from transpiler).
"""

import re
from typing import Optional, Dict, Any
from pydantic import BaseModel


class MergeResult(BaseModel):
    """Result of merging contract and implementation."""
    merged_code: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class DafnyMerger:
    """
    Merges Dafny contracts with implementations.
    
    Contract contains:
    - Method signature
    - requires clauses (preconditions)
    - ensures clauses (postconditions)
    - decreases clauses (termination)
    
    Implementation contains:
    - Method body with logic
    - Loop invariants
    - assert statements
    """
    
    def merge_contract_and_impl(
        self,
        contract: str,
        implementation: str
    ) -> MergeResult:
        """
        Merge Dafny contract with implementation.
        
        Args:
            contract: Dafny contract (signature + requires/ensures)
            implementation: Dafny implementation from transpiler
        
        Returns:
            MergeResult with merged code
        
        Example:
            Contract:
                method ValidateToken(token: string, secret: string) returns (valid: bool)
                    requires |token| > 0
                    ensures valid ==> TokenFormat(token)
            
            Implementation:
                method ValidateToken(token: string, secret: string) returns (valid: bool)
                {
                    valid := |token| > 0 && CheckSecret(token, secret);
                }
            
            Merged:
                method ValidateToken(token: string, secret: string) returns (valid: bool)
                    requires |token| > 0
                    ensures valid ==> TokenFormat(token)
                {
                    valid := |token| > 0 && CheckSecret(token, secret);
                }
        """
        try:
            # Parse contract
            contract_parts = self._parse_contract(contract)
            
            # Parse implementation
            impl_body = self._extract_method_body(implementation)
            
            if not impl_body:
                return MergeResult(
                    merged_code="",
                    success=False,
                    error="Could not extract method body from implementation"
                )
            
            # Build merged code
            merged = self._build_merged_method(contract_parts, impl_body)
            
            return MergeResult(
                merged_code=merged,
                success=True,
                metadata={
                    "has_requires": bool(contract_parts.get("requires")),
                    "has_ensures": bool(contract_parts.get("ensures")),
                    "has_decreases": bool(contract_parts.get("decreases"))
                }
            )
            
        except Exception as e:
            return MergeResult(
                merged_code="",
                success=False,
                error=f"Merge error: {str(e)}"
            )
    
    def _parse_contract(self, contract: str) -> Dict[str, Any]:
        """
        Parse contract into components.
        
        Returns:
            Dict with signature, requires, ensures, decreases clauses
        """
        lines = contract.strip().split('\n')
        
        parts = {
            "signature": "",
            "requires": [],
            "ensures": [],
            "decreases": []
        }
        
        current_clause = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//'):
                continue
            
            # Method signature
            if line.startswith('method '):
                parts["signature"] = line
                continue
            
            # Requires clause
            if line.startswith('requires '):
                current_clause = "requires"
                parts["requires"].append(line)
                continue
            
            # Ensures clause
            if line.startswith('ensures '):
                current_clause = "ensures"
                parts["ensures"].append(line)
                continue
            
            # Decreases clause
            if line.startswith('decreases '):
                current_clause = "decreases"
                parts["decreases"].append(line)
                continue
            
            # Continuation of current clause
            if current_clause and line:
                parts[current_clause][-1] += " " + line
        
        return parts
    
    def _extract_method_body(self, implementation: str) -> Optional[str]:
        """
        Extract method body from implementation.
        
        Args:
            implementation: Full Dafny method with body
        
        Returns:
            Just the body content (between { and })
        """
        # Find the opening brace
        brace_start = implementation.find('{')
        if brace_start == -1:
            return None
        
        # Find the matching closing brace
        brace_count = 0
        body_start = brace_start
        
        for i in range(brace_start, len(implementation)):
            if implementation[i] == '{':
                brace_count += 1
            elif implementation[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Extract body including braces
                    return implementation[body_start:i+1]
        
        return None
    
    def _build_merged_method(
        self,
        contract_parts: Dict[str, Any],
        impl_body: str
    ) -> str:
        """
        Build merged method from contract parts and implementation body.
        
        Args:
            contract_parts: Parsed contract components
            impl_body: Method body from implementation
        
        Returns:
            Complete merged Dafny method
        """
        lines = []
        
        # Add signature
        lines.append(contract_parts["signature"])
        
        # Add requires clauses (indented)
        for req in contract_parts["requires"]:
            lines.append("    " + req)
        
        # Add ensures clauses (indented)
        for ens in contract_parts["ensures"]:
            lines.append("    " + ens)
        
        # Add decreases clauses (indented)
        for dec in contract_parts["decreases"]:
            lines.append("    " + dec)
        
        # Add method body
        lines.append(impl_body)
        
        return '\n'.join(lines)
    
    def validate_merge(self, merged_code: str) -> Dict[str, Any]:
        """
        Basic validation of merged code.
        
        Args:
            merged_code: Merged Dafny code
        
        Returns:
            Dict with validation results
        """
        issues = []
        
        # Check for balanced braces
        if merged_code.count('{') != merged_code.count('}'):
            issues.append("Unbalanced braces in merged code")
        
        # Check for method signature
        if not merged_code.strip().startswith('method '):
            issues.append("Missing method signature")
        
        # Check for method body
        if '{' not in merged_code or '}' not in merged_code:
            issues.append("Missing method body")
        
        # Check for at least one requires or ensures
        has_contract = 'requires ' in merged_code or 'ensures ' in merged_code
        if not has_contract:
            issues.append("Warning: No requires/ensures clauses found")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "has_contract": has_contract,
            "line_count": merged_code.count('\n') + 1
        }
    
    def add_helper_functions(
        self,
        merged_code: str,
        helpers: list[str]
    ) -> str:
        """
        Add helper functions/predicates to merged code.
        
        Args:
            merged_code: Main method code
            helpers: List of helper function definitions
        
        Returns:
            Code with helpers prepended
        """
        if not helpers:
            return merged_code
        
        helper_code = '\n\n'.join(helpers)
        return f"{helper_code}\n\n{merged_code}"

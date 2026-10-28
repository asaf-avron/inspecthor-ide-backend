# Inspecthor - Core Parser
# Pure Python logic for parsing Dafny contracts
# Functional Core: No UI framework imports in core

"""
The Dafny Parser: Extracts method contracts from Dafny source code.
This module contains pure Python logic for parsing Dafny specifications
into structured data that can be rendered by the UI.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Method:
    """Represents a Dafny method with its contract clauses."""
    name: str
    signature: str
    preconditions: list[str] = field(default_factory=list)   # requires clauses
    postconditions: list[str] = field(default_factory=list)  # ensures clauses


@dataclass
class DafnyContract:
    """Represents a parsed Dafny contract with all its methods."""
    source: str
    methods: list[Method] = field(default_factory=list)


class DafnyParser:
    """
    Pure function parser that scans raw Dafny text and extracts structure.
    
    Preconditions: Input string must not be empty.
    Postconditions: Returns a structured DafnyContract containing all 
                    requires and ensures lines found in the source.
    """
    
    # Regex patterns for Dafny constructs
    METHOD_PATTERN = re.compile(
        r'method\s+(\w+)\s*\(([^)]*)\)\s*(?:returns\s*\(([^)]*)\))?',
        re.MULTILINE
    )
    REQUIRES_PATTERN = re.compile(r'requires\s+(.+?)(?://.*)?$', re.MULTILINE)
    ENSURES_PATTERN = re.compile(r'ensures\s+(.+?)(?://.*)?$', re.MULTILINE)
    
    def parse(self, source: str) -> DafnyContract:
        """
        Parse a Dafny source file and extract all method contracts.
        
        Args:
            source: The Dafny source code as a string
            
        Returns:
            A DafnyContract object containing all parsed methods
        """
        if not source or not source.strip():
            return DafnyContract(source=source, methods=[])
        
        contract = DafnyContract(source=source)
        
        # Find all method declarations
        method_matches = list(self.METHOD_PATTERN.finditer(source))
        
        for i, match in enumerate(method_matches):
            method_name = match.group(1)
            params = match.group(2).strip() if match.group(2) else ""
            returns = match.group(3).strip() if match.group(3) else ""
            
            # Build full signature
            signature = f"method {method_name}({params})"
            if returns:
                signature += f" returns ({returns})"
            
            # Determine the block for this method (from this match to the next method or end)
            start_pos = match.end()
            if i + 1 < len(method_matches):
                end_pos = method_matches[i + 1].start()
            else:
                end_pos = len(source)
            
            method_block = source[start_pos:end_pos]
            
            # Extract requires and ensures from this method's block
            preconditions = self._extract_clauses(method_block, self.REQUIRES_PATTERN)
            postconditions = self._extract_clauses(method_block, self.ENSURES_PATTERN)
            
            method = Method(
                name=method_name,
                signature=signature,
                preconditions=preconditions,
                postconditions=postconditions
            )
            contract.methods.append(method)
        
        return contract
    
    def _extract_clauses(self, block: str, pattern: re.Pattern) -> list[str]:
        """Extract all matching clauses from a code block."""
        matches = pattern.findall(block)
        # Clean up whitespace and trailing comments
        return [m.strip().rstrip('//').strip() for m in matches]


def parse_dafny_source(source: str) -> DafnyContract:
    """
    Convenience function to parse Dafny source code.
    
    Args:
        source: The Dafny source code as a string
        
    Returns:
        A DafnyContract object containing all parsed methods
    """
    parser = DafnyParser()
    return parser.parse(source)


# Humanization patterns: (regex pattern, human-readable template)
HUMANIZE_PATTERNS = [
    # Comparison operators
    (r'(\w+)\s*>\s*0', r'\1 must be positive'),
    (r'(\w+)\s*>=\s*0', r'\1 must be non-negative'),
    (r'(\w+)\s*<\s*0', r'\1 must be negative'),
    (r'(\w+)\s*==\s*0', r'\1 must be zero'),
    (r'(\w+)\s*!=\s*(\w+)', r'\1 must not equal \2'),
    
    # Collection membership
    (r'(\w+)\s+in\s+(\w+)\s*&&\s*(\w+)\s+in\s+(\w+)', r'\1 and \3 must exist in \2'),
    (r'(\w+)\s+in\s+(\w+)', r'\1 must exist in \2'),
    
    # Validity predicates
    (r'Valid\((\w+)\)', r'\1 must be in valid state'),
    
    # Balance/amount operations  
    (r'(\w+)\[(\w+)\]\s*>=\s*(\w+)', r'\2 must have sufficient \3 in \1'),
    (r'(\w+)\[(\w+)\]\s*==\s*(\w+)\[(\w+)\]\s*-\s*(\w+)', r'\2 balance decreases by \5'),
    (r'(\w+)\[(\w+)\]\s*==\s*(\w+)\[(\w+)\]\s*\+\s*(\w+)', r'\2 balance increases by \5'),
    
    # Old value comparisons
    (r'old\((\w+)\)', r'original \1'),
    
    # Implication
    (r'(\w+)\s*==>\s*(.+)', r'if \1 then \2'),
    
    # Forall quantifier
    (r'forall\s+(\w+)\s*::', r'for all \1:'),
]


def humanize_clause(clause: str, clause_type: str = "requires") -> str:
    """
    Translate a technical Dafny clause into human-readable text.
    
    Args:
        clause: The raw Dafny clause (e.g., "amount > 0")
        clause_type: Either "requires" (precondition) or "ensures" (postcondition)
        
    Returns:
        Human-readable description of the clause
    """
    result = clause.strip()
    
    # Try each humanization pattern
    for pattern, replacement in HUMANIZE_PATTERNS:
        new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new_result != result:
            result = new_result
            break  # Use first matching pattern
    
    # Capitalize first letter
    if result:
        result = result[0].upper() + result[1:]
    
    # Add prefix based on clause type
    if clause_type == "requires":
        prefix = "Guardrail"
    else:
        prefix = "Promise"
    
    return f"{prefix}: {result}"


def get_clause_icon(clause_type: str) -> str:
    """
    Get the appropriate icon for a clause type.
    
    Args:
        clause_type: Either "requires" or "ensures"
        
    Returns:
        Emoji icon for the clause type
    """
    if clause_type == "requires":
        return "🟢"  # Green for guardrails/preconditions
    else:
        return "🔵"  # Blue for promises/postconditions

if __name__ == "__main__":
    import os
    
    # Simple Test Harness to verify the logic on the command line
    fixture_path = "tests/fixtures/interface.dfy"
    
    if os.path.exists(fixture_path):
        with open(fixture_path, "r") as f:
            source_code = f.read()
        
        print(f"🔍 Scanning: {fixture_path}...")
        
        # Initialize and Parse
        # Note: Ensure these class names match what Cursor generated
        parser = DafnyParser() 
        contract = parser.parse(source_code)
        
        # Visual Report
        print("✅ Found Contract!")
        for method in contract.methods:
            print(f"\n🔹 Method: {method.name}")
            print(f"   🛡️ Guardrails ({len(method.preconditions)}):")
            for pre in method.preconditions:
                print(f"      - {pre}")
            print(f"   ✨ Promises ({len(method.postconditions)}):")
            for post in method.postconditions:
                print(f"      - {post}")
    else:
        print(f"❌ Error: Test fixture not found at {fixture_path}")
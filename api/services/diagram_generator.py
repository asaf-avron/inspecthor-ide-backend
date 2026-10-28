"""
Mermaid Diagram Generator Service

Generates Mermaid diagrams for Intent Verification (Horizon A).
Supports:
- Generating expected diagrams from spec.md (requirements)
- Generating actual diagrams from Python code (implementation)
- Computing diffs between expected and actual
"""

import logging
import os
from typing import Any, Optional, Dict, Tuple
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class DiagramGenerator:
    """Service for generating Mermaid diagrams"""

    def __init__(self):
        """Initialize the diagram generator"""
        self.model_name = "gemini-1.5-flash"

    def generate_from_spec(self, spec_md: str, component_name: str = "Component") -> str:
        """
        Generate Mermaid diagram from specification (expected behavior)

        Args:
            spec_md: Markdown specification content
            component_name: Name of the component

        Returns:
            Mermaid diagram as string
        """
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set, returning placeholder diagram")
            return self._placeholder_diagram(component_name)

        try:
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""Given this software specification, generate a Mermaid flowchart that visualizes the logic flow.

Specification:
---
{spec_md}
---

Generate a Mermaid diagram (flowchart syntax) that shows:
1. Main user interactions and entry points
2. Key decision points (if/else logic)
3. State transitions or workflow steps
4. Component interactions
5. Data flow between components

Requirements:
- Use 'graph TD' (top-down) or 'graph LR' (left-right) as appropriate
- Use clear, concise node labels
- Show decision diamonds with conditional paths
- Include subgraphs for logical groupings
- Use meaningful connection labels
- Keep it focused on high-level logic, not implementation details

IMPORTANT:
- Return ONLY the Mermaid code, no explanations or markdown code fences
- Start directly with 'graph TD' or 'graph LR'
- Do not include ```mermaid``` or ``` markers
- Use valid Mermaid syntax

Example output format:
graph TD
    A[User Request] --> B{{Validate Input}}
    B -->|Valid| C[Process Request]
    B -->|Invalid| D[Return Error]
    C --> E[Save to Database]
    E --> F[Return Success]
"""

            response = model.generate_content(prompt)
            diagram = response.text.strip()

            # Clean up any markdown code fences that might have been added
            diagram = self._clean_diagram(diagram)

            logger.info(f"Generated Mermaid diagram from spec ({len(diagram)} chars)")
            return diagram

        except Exception as e:
            logger.error(f"Failed to generate diagram from spec: {e}")
            return self._placeholder_diagram(component_name, error=str(e))

    def generate_from_code(self, python_code: str, component_name: str = "Component") -> str:
        """
        Generate Mermaid diagram from Python implementation (actual behavior)

        Args:
            python_code: Python source code
            component_name: Name of the component

        Returns:
            Mermaid diagram as string
        """
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set, returning placeholder diagram")
            return self._placeholder_diagram(component_name, is_actual=True)

        try:
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""Given this Python code, generate a Mermaid flowchart that visualizes the actual execution flow.

Python Code:
---
{python_code}
---

Generate a Mermaid diagram (flowchart syntax) that shows:
1. Function/method entry points
2. Conditional branches (if/elif/else)
3. Loops and iterations
4. Function calls and dependencies
5. Return paths and error handling
6. Exception handling flows

Requirements:
- Use 'graph TD' (top-down) or 'graph LR' (left-right) as appropriate
- Use clear, concise node labels matching the code structure
- Show all conditional branches
- Include error/exception paths
- Use subgraphs for classes or logical groups
- Keep it focused on the actual control flow

IMPORTANT:
- Return ONLY the Mermaid code, no explanations or markdown code fences
- Start directly with 'graph TD' or 'graph LR'
- Do not include ```mermaid``` or ``` markers
- Use valid Mermaid syntax

Example output format:
graph TD
    A[function start] --> B{{check condition}}
    B -->|true| C[do action]
    B -->|false| D[skip]
    C --> E{{error?}}
    E -->|yes| F[handle error]
    E -->|no| G[return success]
"""

            response = model.generate_content(prompt)
            diagram = response.text.strip()

            # Clean up any markdown code fences
            diagram = self._clean_diagram(diagram)

            logger.info(f"Generated Mermaid diagram from code ({len(diagram)} chars)")
            return diagram

        except Exception as e:
            logger.error(f"Failed to generate diagram from code: {e}")
            return self._placeholder_diagram(component_name, is_actual=True, error=str(e))

    def compute_diff(
        self,
        expected_diagram: str,
        actual_diagram: str
    ) -> Dict[str, Any]:
        """
        Compare expected vs actual diagrams and identify differences

        Args:
            expected_diagram: Mermaid diagram from spec
            actual_diagram: Mermaid diagram from code

        Returns:
            Dictionary with diff information
        """
        # Extract nodes and edges from diagrams
        expected_nodes, expected_edges = self._parse_diagram(expected_diagram)
        actual_nodes, actual_edges = self._parse_diagram(actual_diagram)

        # Find missing and extra nodes
        missing_nodes = expected_nodes - actual_nodes
        extra_nodes = actual_nodes - expected_nodes
        common_nodes = expected_nodes & actual_nodes

        # Find missing and extra edges
        missing_edges = expected_edges - actual_edges
        extra_edges = actual_edges - expected_edges
        common_edges = expected_edges & actual_edges

        # Calculate similarity percentage
        total_nodes = len(expected_nodes | actual_nodes)
        total_edges = len(expected_edges | actual_edges)
        matching_nodes = len(common_nodes)
        matching_edges = len(common_edges)

        similarity: float = 0
        if total_nodes + total_edges > 0:
            similarity = ((matching_nodes + matching_edges) / (total_nodes + total_edges)) * 100

        return {
            "similarity_percent": round(similarity, 2),
            "missing_nodes": list(missing_nodes),
            "extra_nodes": list(extra_nodes),
            "common_nodes": list(common_nodes),
            "missing_edges": list(missing_edges),
            "extra_edges": list(extra_edges),
            "common_edges": list(common_edges),
            "summary": self._generate_diff_summary(
                missing_nodes, extra_nodes, missing_edges, extra_edges, similarity
            )
        }

    def _clean_diagram(self, diagram: str) -> str:
        """
        Clean up diagram by removing markdown code fences and extra whitespace

        Args:
            diagram: Raw diagram string

        Returns:
            Cleaned diagram
        """
        # Remove markdown code fences
        diagram = diagram.replace("```mermaid", "").replace("```", "")

        # Remove leading/trailing whitespace
        diagram = diagram.strip()

        # Ensure it starts with graph declaration
        if not diagram.startswith("graph ") and not diagram.startswith("flowchart "):
            # Try to find the graph declaration
            lines = diagram.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("graph ") or line.strip().startswith("flowchart "):
                    diagram = "\n".join(lines[i:])
                    break

        return diagram

    def _parse_diagram(self, diagram: str) -> Tuple[set, set]:
        """
        Parse Mermaid diagram to extract nodes and edges

        Args:
            diagram: Mermaid diagram string

        Returns:
            Tuple of (nodes set, edges set)
        """
        nodes = set()
        edges = set()

        lines = diagram.split("\n")
        for line in lines:
            line = line.strip()

            # Skip empty lines and graph declaration
            if not line or line.startswith("graph ") or line.startswith("flowchart ") or line.startswith("subgraph"):
                continue

            # Simple parsing: look for node definitions and connections
            # Format: A[Label] --> B[Label]
            # Format: A --> B
            # Format: A[Label]

            # Extract node IDs (letters before brackets or arrows)
            parts = line.replace("-->", " ").replace("---", " ").replace("->", " ").replace("--", " ")

            # Split on spaces and extract node identifiers
            tokens = parts.split()
            for token in tokens:
                # Remove brackets and content
                node_id = token.split("[")[0].split("{")[0].split("(")[0]
                if node_id and node_id.isalnum():
                    nodes.add(node_id)

            # Extract edges (connections)
            if "-->" in line or "---" in line or "->" in line or "--" in line:
                edges.add(line)

        return nodes, edges

    def _generate_diff_summary(
        self,
        missing_nodes: set,
        extra_nodes: set,
        missing_edges: set,
        extra_edges: set,
        similarity: float
    ) -> str:
        """
        Generate human-readable diff summary

        Args:
            missing_nodes: Nodes in expected but not actual
            extra_nodes: Nodes in actual but not expected
            missing_edges: Edges in expected but not actual
            extra_edges: Edges in actual but not expected
            similarity: Similarity percentage

        Returns:
            Summary string
        """
        if similarity >= 95:
            return "Implementation closely matches specification."
        elif similarity >= 80:
            return "Implementation mostly matches specification with minor differences."
        elif similarity >= 60:
            return "Implementation has notable differences from specification."
        else:
            return "Implementation significantly differs from specification."

    def _placeholder_diagram(
        self,
        component_name: str,
        is_actual: bool = False,
        error: Optional[str] = None
    ) -> str:
        """
        Generate a placeholder diagram when generation fails or API key missing

        Args:
            component_name: Name of component
            is_actual: Whether this is an actual (code-based) diagram
            error: Optional error message

        Returns:
            Placeholder Mermaid diagram
        """
        diagram_type = "Actual Implementation" if is_actual else "Expected Behavior"

        if error:
            return f"""graph TD
    A[{component_name}]
    A --> B[Error: Could not generate diagram]
    B --> C[{error[:50]}...]
    style B fill:#ffcccc
"""
        else:
            return f"""graph TD
    A[{component_name}]
    A --> B[{diagram_type}]
    B --> C[Diagram generation requires GEMINI_API_KEY]
    style C fill:#ffffcc
"""


# Singleton instance
_generator_instance = None


def get_diagram_generator() -> DiagramGenerator:
    """Get or create diagram generator singleton"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = DiagramGenerator()
    return _generator_instance

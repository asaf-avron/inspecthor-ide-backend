"""
Call Graph Analyzer Service

Extracts and compares call graphs from Python code and Mermaid diagrams.
Part of Runtime Verification Pipeline (Horizon C).

This analyzer:
1. Parses Python code to extract actual function call graphs
2. Parses Mermaid diagrams to extract expected call graphs
3. Compares expected vs actual graphs
4. Computes similarity scores and identifies discrepancies
"""

import ast
import re
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GraphDiscrepancyType(str, Enum):
    """Types of discrepancies between expected and actual call graphs"""
    MISSING_CALL = "missing_call"  # Expected call not found in implementation
    EXTRA_CALL = "extra_call"  # Unexpected call found in implementation
    MISSING_FUNCTION = "missing_function"  # Expected function not implemented
    EXTRA_FUNCTION = "extra_function"  # Function implemented but not in spec


@dataclass
class CallGraphNode:
    """Represents a function/method in the call graph"""
    name: str
    calls: Set[str]  # Functions this node calls
    called_by: Set[str]  # Functions that call this node


@dataclass
class CallGraph:
    """Complete call graph representation"""
    nodes: Dict[str, CallGraphNode]

    def get_all_calls(self) -> Set[Tuple[str, str]]:
        """Get all call edges as (caller, callee) tuples"""
        edges = set()
        for caller, node in self.nodes.items():
            for callee in node.calls:
                edges.add((caller, callee))
        return edges

    def get_functions(self) -> Set[str]:
        """Get all function names in the graph"""
        return set(self.nodes.keys())


@dataclass
class GraphDiscrepancy:
    """A discrepancy between expected and actual graphs"""
    discrepancy_type: GraphDiscrepancyType
    source: Optional[str]  # Caller function (for call discrepancies)
    target: Optional[str]  # Callee function (for call discrepancies)
    function_name: Optional[str]  # Function name (for function discrepancies)
    description: str
    severity: str  # 'low', 'medium', 'high'


@dataclass
class GraphComparisonReport:
    """Report comparing expected vs actual call graphs"""
    similarity_score: float  # 0-100, higher is better
    total_expected_calls: int
    total_actual_calls: int
    matching_calls: int
    discrepancies: List[GraphDiscrepancy]
    expected_graph: CallGraph
    actual_graph: CallGraph


class CallGraphAnalyzer:
    """Service for analyzing and comparing call graphs"""

    def __init__(self):
        """Initialize analyzer"""
        pass

    def extract_from_python(self, python_code: str) -> CallGraph:
        """
        Extract call graph from Python source code

        Args:
            python_code: Python source code

        Returns:
            CallGraph representing the code structure
        """
        try:
            tree = ast.parse(python_code)
            visitor = CallGraphVisitor()
            visitor.visit(tree)
            return visitor.get_call_graph()
        except Exception as e:
            logger.error(f"Failed to parse Python code: {e}")
            return CallGraph(nodes={})

    def extract_from_mermaid(self, mermaid_diagram: str) -> CallGraph:
        """
        Extract call graph from Mermaid diagram

        Supports Mermaid flowchart and sequence diagram syntax.

        Args:
            mermaid_diagram: Mermaid diagram text

        Returns:
            CallGraph representing the diagram structure
        """
        nodes = {}

        # Parse flowchart syntax: A --> B, A -> B
        arrow_pattern = r'(\w+)\s*(?:-->|->)\s*(\w+)'
        for match in re.finditer(arrow_pattern, mermaid_diagram):
            caller = match.group(1)
            callee = match.group(2)

            if caller not in nodes:
                nodes[caller] = CallGraphNode(name=caller, calls=set(), called_by=set())
            if callee not in nodes:
                nodes[callee] = CallGraphNode(name=callee, calls=set(), called_by=set())

            nodes[caller].calls.add(callee)
            nodes[callee].called_by.add(caller)

        # Parse sequence diagram syntax: participant A, A->>B
        sequence_pattern = r'(\w+)\s*->>[\+\-]?\s*(\w+)'
        for match in re.finditer(sequence_pattern, mermaid_diagram):
            caller = match.group(1)
            callee = match.group(2)

            if caller not in nodes:
                nodes[caller] = CallGraphNode(name=caller, calls=set(), called_by=set())
            if callee not in nodes:
                nodes[callee] = CallGraphNode(name=callee, calls=set(), called_by=set())

            nodes[caller].calls.add(callee)
            nodes[callee].called_by.add(caller)

        # Extract participant names
        participant_pattern = r'participant\s+(\w+)'
        for match in re.finditer(participant_pattern, mermaid_diagram):
            participant = match.group(1)
            if participant not in nodes:
                nodes[participant] = CallGraphNode(
                    name=participant,
                    calls=set(),
                    called_by=set()
                )

        return CallGraph(nodes=nodes)

    def compare_graphs(
        self,
        expected_graph: CallGraph,
        actual_graph: CallGraph
    ) -> GraphComparisonReport:
        """
        Compare expected (from Mermaid) vs actual (from Python) graphs

        Args:
            expected_graph: Call graph from specification
            actual_graph: Call graph from implementation

        Returns:
            GraphComparisonReport with similarity score and discrepancies
        """
        expected_calls = expected_graph.get_all_calls()
        actual_calls = actual_graph.get_all_calls()
        expected_functions = expected_graph.get_functions()
        actual_functions = actual_graph.get_functions()

        # Find matching calls
        matching_calls = expected_calls & actual_calls

        # Identify discrepancies
        discrepancies = []

        # Missing calls (in expected but not actual)
        missing_calls = expected_calls - actual_calls
        for caller, callee in missing_calls:
            discrepancies.append(GraphDiscrepancy(
                discrepancy_type=GraphDiscrepancyType.MISSING_CALL,
                source=caller,
                target=callee,
                function_name=None,
                description=f"Expected call from '{caller}' to '{callee}' not found in implementation",
                severity='high'
            ))

        # Extra calls (in actual but not expected)
        extra_calls = actual_calls - expected_calls
        for caller, callee in extra_calls:
            discrepancies.append(GraphDiscrepancy(
                discrepancy_type=GraphDiscrepancyType.EXTRA_CALL,
                source=caller,
                target=callee,
                function_name=None,
                description=f"Unexpected call from '{caller}' to '{callee}' found in implementation",
                severity='medium'
            ))

        # Missing functions (in expected but not actual)
        missing_functions = expected_functions - actual_functions
        for func in missing_functions:
            discrepancies.append(GraphDiscrepancy(
                discrepancy_type=GraphDiscrepancyType.MISSING_FUNCTION,
                source=None,
                target=None,
                function_name=func,
                description=f"Expected function '{func}' not found in implementation",
                severity='high'
            ))

        # Extra functions (in actual but not expected)
        extra_functions = actual_functions - expected_functions
        for func in extra_functions:
            discrepancies.append(GraphDiscrepancy(
                discrepancy_type=GraphDiscrepancyType.EXTRA_FUNCTION,
                source=None,
                target=None,
                function_name=func,
                description=f"Function '{func}' implemented but not in specification",
                severity='low'
            ))

        # Calculate similarity score
        similarity = self._calculate_similarity(
            expected_calls,
            actual_calls,
            expected_functions,
            actual_functions,
            matching_calls
        )

        return GraphComparisonReport(
            similarity_score=similarity,
            total_expected_calls=len(expected_calls),
            total_actual_calls=len(actual_calls),
            matching_calls=len(matching_calls),
            discrepancies=discrepancies,
            expected_graph=expected_graph,
            actual_graph=actual_graph
        )

    def _calculate_similarity(
        self,
        expected_calls: Set[Tuple[str, str]],
        actual_calls: Set[Tuple[str, str]],
        expected_functions: Set[str],
        actual_functions: Set[str],
        matching_calls: Set[Tuple[str, str]]
    ) -> float:
        """
        Calculate similarity score between graphs

        Uses weighted average of:
        - Call similarity (80% weight)
        - Function similarity (20% weight)
        """
        # Call similarity
        if len(expected_calls) == 0 and len(actual_calls) == 0:
            call_similarity = 100.0
        elif len(expected_calls) == 0:
            call_similarity = 0.0
        else:
            call_similarity = (len(matching_calls) / len(expected_calls)) * 100

        # Function similarity
        if len(expected_functions) == 0 and len(actual_functions) == 0:
            function_similarity = 100.0
        elif len(expected_functions) == 0:
            function_similarity = 0.0
        else:
            matching_functions = expected_functions & actual_functions
            function_similarity = (len(matching_functions) / len(expected_functions)) * 100

        # Weighted average (calls are more important)
        similarity = (call_similarity * 0.8) + (function_similarity * 0.2)

        return round(similarity, 2)


class CallGraphVisitor(ast.NodeVisitor):
    """AST visitor to extract call graph from Python code"""

    def __init__(self):
        self.current_function = None
        self.nodes = {}

    def visit_FunctionDef(self, node):
        """Visit function definition"""
        func_name = node.name

        if func_name not in self.nodes:
            self.nodes[func_name] = CallGraphNode(
                name=func_name,
                calls=set(),
                called_by=set()
            )

        # Set current context
        prev_function = self.current_function
        self.current_function = func_name

        # Visit function body
        self.generic_visit(node)

        # Restore context
        self.current_function = prev_function

    def visit_AsyncFunctionDef(self, node):
        """Visit async function definition"""
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        """Visit function call"""
        if self.current_function:
            # Extract called function name
            callee = None

            if isinstance(node.func, ast.Name):
                callee = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # For method calls like obj.method(), use just the method name
                callee = node.func.attr

            if callee:
                # Add callee node if not exists
                if callee not in self.nodes:
                    self.nodes[callee] = CallGraphNode(
                        name=callee,
                        calls=set(),
                        called_by=set()
                    )

                # Record the call
                self.nodes[self.current_function].calls.add(callee)
                self.nodes[callee].called_by.add(self.current_function)

        self.generic_visit(node)

    def get_call_graph(self) -> CallGraph:
        """Get the extracted call graph"""
        return CallGraph(nodes=self.nodes)

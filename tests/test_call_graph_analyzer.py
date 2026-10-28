"""
Tests for Call Graph Analyzer (Task #8 - Runtime Verification)
"""

import pytest
from api.services.call_graph_analyzer import (
    CallGraphAnalyzer,
    CallGraph,
    CallGraphNode,
    GraphDiscrepancyType
)


class TestCallGraphAnalyzer:
    """Test call graph extraction and comparison"""

    def setup_method(self):
        """Create analyzer for tests"""
        self.analyzer = CallGraphAnalyzer()

    def test_extract_from_simple_python(self):
        """Test extracting call graph from simple Python code"""
        python_code = """
def foo():
    bar()

def bar():
    baz()

def baz():
    pass
"""
        graph = self.analyzer.extract_from_python(python_code)

        assert "foo" in graph.nodes
        assert "bar" in graph.nodes
        assert "baz" in graph.nodes

        assert "bar" in graph.nodes["foo"].calls
        assert "baz" in graph.nodes["bar"].calls
        assert len(graph.nodes["baz"].calls) == 0

    def test_extract_from_python_with_methods(self):
        """Test extracting call graph with method calls"""
        python_code = """
class MyClass:
    def method_a(self):
        self.method_b()

    def method_b(self):
        helper_function()

def helper_function():
    pass
"""
        graph = self.analyzer.extract_from_python(python_code)

        assert "method_a" in graph.nodes
        assert "method_b" in graph.nodes
        assert "helper_function" in graph.nodes

        assert "method_b" in graph.nodes["method_a"].calls
        assert "helper_function" in graph.nodes["method_b"].calls

    def test_extract_from_mermaid_flowchart(self):
        """Test extracting call graph from Mermaid flowchart"""
        mermaid = """
flowchart TD
    A --> B
    B --> C
    C --> D
"""
        graph = self.analyzer.extract_from_mermaid(mermaid)

        assert "A" in graph.nodes
        assert "B" in graph.nodes
        assert "C" in graph.nodes
        assert "D" in graph.nodes

        assert "B" in graph.nodes["A"].calls
        assert "C" in graph.nodes["B"].calls
        assert "D" in graph.nodes["C"].calls

    def test_extract_from_mermaid_sequence(self):
        """Test extracting call graph from Mermaid sequence diagram"""
        mermaid = """
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>Bob: Hello
    Bob->>Charlie: Forward
"""
        graph = self.analyzer.extract_from_mermaid(mermaid)

        assert "Alice" in graph.nodes
        assert "Bob" in graph.nodes
        assert "Charlie" in graph.nodes

        assert "Bob" in graph.nodes["Alice"].calls
        assert "Charlie" in graph.nodes["Bob"].calls

    def test_compare_identical_graphs(self):
        """Test comparing identical graphs"""
        python_code = """
def foo():
    bar()

def bar():
    pass
"""
        mermaid = """
flowchart TD
    foo --> bar
"""

        actual = self.analyzer.extract_from_python(python_code)
        expected = self.analyzer.extract_from_mermaid(mermaid)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert comparison.similarity_score == 100.0
        assert comparison.matching_calls == 1
        assert len(comparison.discrepancies) == 0

    def test_compare_missing_call(self):
        """Test comparison with missing call"""
        # Expected: foo -> bar
        mermaid = """
flowchart TD
    foo --> bar
"""

        # Actual: foo exists but doesn't call bar
        python_code = """
def foo():
    pass

def bar():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert comparison.similarity_score < 100.0
        assert any(
            d.discrepancy_type == GraphDiscrepancyType.MISSING_CALL
            for d in comparison.discrepancies
        )

    def test_compare_extra_call(self):
        """Test comparison with extra call"""
        # Expected: just foo
        mermaid = """
flowchart TD
    foo
"""

        # Actual: foo calls bar (unexpected)
        python_code = """
def foo():
    bar()

def bar():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert comparison.similarity_score < 100.0
        assert any(
            d.discrepancy_type == GraphDiscrepancyType.EXTRA_CALL
            for d in comparison.discrepancies
        )

    def test_compare_missing_function(self):
        """Test comparison with missing function"""
        # Expected: foo, bar, baz
        mermaid = """
flowchart TD
    foo --> bar
    bar --> baz
"""

        # Actual: only foo and bar
        python_code = """
def foo():
    bar()

def bar():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert comparison.similarity_score < 100.0
        assert any(
            d.discrepancy_type == GraphDiscrepancyType.MISSING_FUNCTION
            and d.function_name == "baz"
            for d in comparison.discrepancies
        )

    def test_compare_extra_function(self):
        """Test comparison with extra function"""
        # Expected: just foo
        mermaid = """
flowchart TD
    foo
"""

        # Actual: foo and bar
        python_code = """
def foo():
    pass

def bar():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert any(
            d.discrepancy_type == GraphDiscrepancyType.EXTRA_FUNCTION
            and d.function_name == "bar"
            for d in comparison.discrepancies
        )

    def test_similarity_calculation(self):
        """Test similarity score calculation"""
        # Expected: A -> B -> C
        mermaid = """
flowchart TD
    A --> B
    B --> C
"""

        # Actual: A -> B (missing B -> C)
        python_code = """
def A():
    B()

def B():
    pass

def C():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        # Should be 50% call similarity (1 of 2 calls match)
        # Plus function similarity (all 3 functions present)
        # Weighted: 50% * 0.8 + 100% * 0.2 = 40% + 20% = 60%
        assert 55.0 <= comparison.similarity_score <= 65.0

    def test_empty_graphs(self):
        """Test comparing empty graphs"""
        empty_python = ""
        empty_mermaid = "flowchart TD"

        expected = self.analyzer.extract_from_mermaid(empty_mermaid)
        actual = self.analyzer.extract_from_python(empty_python)

        comparison = self.analyzer.compare_graphs(expected, actual)

        assert comparison.similarity_score == 100.0
        assert len(comparison.discrepancies) == 0

    def test_get_all_calls(self):
        """Test getting all call edges"""
        python_code = """
def foo():
    bar()
    baz()

def bar():
    baz()
"""
        graph = self.analyzer.extract_from_python(python_code)
        calls = graph.get_all_calls()

        assert ("foo", "bar") in calls
        assert ("foo", "baz") in calls
        assert ("bar", "baz") in calls
        assert len(calls) == 3

    def test_get_functions(self):
        """Test getting all function names"""
        python_code = """
def foo():
    pass

def bar():
    pass
"""
        graph = self.analyzer.extract_from_python(python_code)
        functions = graph.get_functions()

        assert "foo" in functions
        assert "bar" in functions
        assert len(functions) == 2

    def test_complex_python_code(self):
        """Test parsing complex Python with nested calls"""
        python_code = """
def process_data(data):
    validated = validate(data)
    transformed = transform(validated)
    return save(transformed)

def validate(data):
    check_format(data)
    return data

def transform(data):
    return data.upper()

def save(data):
    write_to_db(data)

def check_format(data):
    pass

def write_to_db(data):
    pass
"""
        graph = self.analyzer.extract_from_python(python_code)

        assert "process_data" in graph.nodes
        assert "validate" in graph.nodes["process_data"].calls
        assert "transform" in graph.nodes["process_data"].calls
        assert "save" in graph.nodes["process_data"].calls

        assert "check_format" in graph.nodes["validate"].calls
        assert "write_to_db" in graph.nodes["save"].calls

    def test_async_functions(self):
        """Test extracting async functions"""
        python_code = """
async def async_foo():
    await async_bar()

async def async_bar():
    pass
"""
        graph = self.analyzer.extract_from_python(python_code)

        assert "async_foo" in graph.nodes
        assert "async_bar" in graph.nodes
        assert "async_bar" in graph.nodes["async_foo"].calls

    def test_invalid_python(self):
        """Test handling invalid Python code"""
        invalid_code = "def foo(:"

        graph = self.analyzer.extract_from_python(invalid_code)

        # Should return empty graph on parse error
        assert len(graph.nodes) == 0

    def test_discrepancy_severity(self):
        """Test that discrepancies have appropriate severity"""
        mermaid = """
flowchart TD
    foo --> bar
"""
        python_code = """
def foo():
    pass
"""

        expected = self.analyzer.extract_from_mermaid(mermaid)
        actual = self.analyzer.extract_from_python(python_code)

        comparison = self.analyzer.compare_graphs(expected, actual)

        # Missing call should be high severity
        missing_call = next(
            d for d in comparison.discrepancies
            if d.discrepancy_type == GraphDiscrepancyType.MISSING_CALL
        )
        assert missing_call.severity == 'high'

        # Missing function should be high severity
        missing_func = next(
            d for d in comparison.discrepancies
            if d.discrepancy_type == GraphDiscrepancyType.MISSING_FUNCTION
        )
        assert missing_func.severity == 'high'


if __name__ == "__main__":
    print("\n[TEST] Running Call Graph Analyzer Tests\n")
    print("=" * 60)

    analyzer = CallGraphAnalyzer()

    print("\n[1] Testing Python call graph extraction...")
    test = TestCallGraphAnalyzer()
    test.setup_method()
    test.test_extract_from_simple_python()
    print("[OK] Python extraction works")

    print("\n[2] Testing Mermaid call graph extraction...")
    test.test_extract_from_mermaid_flowchart()
    test.test_extract_from_mermaid_sequence()
    print("[OK] Mermaid extraction works")

    print("\n[3] Testing graph comparison...")
    test.test_compare_identical_graphs()
    test.test_compare_missing_call()
    print("[OK] Graph comparison works")

    print("\n[4] Testing similarity calculation...")
    test.test_similarity_calculation()
    print("[OK] Similarity calculation works")

    print("\n" + "=" * 60)
    print("[OK] All call graph analyzer tests completed!\n")

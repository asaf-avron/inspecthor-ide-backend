"""
Tests for Mermaid Diagram Generator (Task #3)
"""

import pytest
from api.services.diagram_generator import DiagramGenerator


class TestDiagramGenerator:
    """Test diagram generation service"""

    def setup_method(self):
        """Create diagram generator for tests"""
        self.generator = DiagramGenerator()

    def test_generate_from_spec_basic(self):
        """Test generating diagram from a simple spec"""
        spec = """
# User Authentication

## Requirements
- Users can log in with email and password
- System validates credentials
- Failed attempts are logged
- Successful login creates a session
"""

        diagram = self.generator.generate_from_spec(spec, "Authentication")

        # Verify diagram starts with graph declaration
        assert diagram.startswith("graph ") or diagram.startswith("flowchart "), \
            f"Diagram should start with 'graph' or 'flowchart', got: {diagram[:50]}"

        # Verify it's not a placeholder (unless GEMINI_API_KEY is missing)
        if "GEMINI_API_KEY" not in diagram:
            assert len(diagram) > 100, "Diagram seems too short"

        print(f"Generated diagram ({len(diagram)} chars):")
        print(diagram)

    def test_generate_from_code_basic(self):
        """Test generating diagram from Python code"""
        code = """
def authenticate_user(email, password):
    if not email or not password:
        return {"error": "Missing credentials"}

    user = database.get_user(email)
    if not user:
        log_failure(email)
        return {"error": "Invalid credentials"}

    if not verify_password(password, user.password_hash):
        log_failure(email)
        return {"error": "Invalid credentials"}

    session = create_session(user.id)
    return {"success": True, "session_id": session.id}
"""

        diagram = self.generator.generate_from_code(code, "Authentication")

        # Verify diagram starts with graph declaration
        assert diagram.startswith("graph ") or diagram.startswith("flowchart "), \
            f"Diagram should start with 'graph' or 'flowchart', got: {diagram[:50]}"

        print(f"Generated diagram ({len(diagram)} chars):")
        print(diagram)

    def test_compute_diff_identical(self):
        """Test diff computation for identical diagrams"""
        diagram = """graph TD
    A[Start] --> B[Process]
    B --> C[End]
"""

        diff = self.generator.compute_diff(diagram, diagram)

        assert diff["similarity_percent"] == 100.0
        assert len(diff["missing_nodes"]) == 0
        assert len(diff["extra_nodes"]) == 0
        assert "closely matches" in diff["summary"].lower()

    def test_compute_diff_different(self):
        """Test diff computation for different diagrams"""
        expected = """graph TD
    A[Start] --> B[Validate]
    B --> C[Process]
    C --> D[End]
"""

        actual = """graph TD
    A[Start] --> B[Process]
    B --> D[End]
"""

        diff = self.generator.compute_diff(expected, actual)

        # Should detect missing Validate node
        assert diff["similarity_percent"] < 100.0
        assert "C" in diff["missing_nodes"] or len(diff["missing_edges"]) > 0

        print(f"Similarity: {diff['similarity_percent']}%")
        print(f"Summary: {diff['summary']}")

    def test_compute_diff_extra_nodes(self):
        """Test diff with extra nodes in actual"""
        expected = """graph TD
    A[Start] --> B[End]
"""

        actual = """graph TD
    A[Start] --> B[Validate]
    B --> C[Process]
    C --> D[End]
"""

        diff = self.generator.compute_diff(expected, actual)

        # Should detect extra nodes
        assert diff["similarity_percent"] < 100.0
        assert len(diff["extra_nodes"]) > 0 or len(diff["extra_edges"]) > 0

        print(f"Extra nodes: {diff['extra_nodes']}")
        print(f"Summary: {diff['summary']}")

    def test_clean_diagram_removes_code_fences(self):
        """Test that clean_diagram removes markdown code fences"""
        dirty = """```mermaid
graph TD
    A[Start] --> B[End]
```"""

        cleaned = self.generator._clean_diagram(dirty)

        assert "```" not in cleaned
        assert cleaned.strip().startswith("graph TD")

    def test_parse_diagram_extracts_nodes(self):
        """Test that parse_diagram extracts nodes correctly"""
        diagram = """graph TD
    A[Start] --> B[Process]
    B --> C[End]
"""

        nodes, edges = self.generator._parse_diagram(diagram)

        assert "A" in nodes
        assert "B" in nodes
        assert "C" in nodes
        assert len(edges) > 0

    def test_placeholder_diagram_on_error(self):
        """Test that placeholder is generated on error"""
        diagram = self.generator._placeholder_diagram(
            "TestComponent",
            error="Test error message"
        )

        assert "TestComponent" in diagram
        assert "Error" in diagram
        assert diagram.startswith("graph TD")

    def test_placeholder_diagram_no_api_key(self):
        """Test placeholder when API key is missing"""
        diagram = self.generator._placeholder_diagram("TestComponent")

        assert "TestComponent" in diagram
        assert "GEMINI_API_KEY" in diagram
        assert diagram.startswith("graph TD")


class TestDiagramDiff:
    """Test diagram diff functionality"""

    def setup_method(self):
        """Create diagram generator for tests"""
        self.generator = DiagramGenerator()

    def test_similarity_perfect_match(self):
        """Test similarity calculation for perfect match"""
        diagram = """graph TD
    A[Start] --> B[Process]
    B --> C{Decision}
    C -->|Yes| D[Action1]
    C -->|No| E[Action2]
    D --> F[End]
    E --> F
"""

        diff = self.generator.compute_diff(diagram, diagram)

        assert diff["similarity_percent"] == 100.0
        assert diff["summary"].lower().find("closely") >= 0

    def test_similarity_partial_match(self):
        """Test similarity for partial match"""
        expected = """graph TD
    A[Start] --> B[Process]
    B --> C[End]
"""

        actual = """graph TD
    A[Start] --> B[Process]
    B --> D[Validate]
    D --> C[End]
"""

        diff = self.generator.compute_diff(expected, actual)

        # Should be less than 100% but at least 40% (allowing for edge cases)
        assert 40 <= diff["similarity_percent"] < 100

    def test_similarity_no_match(self):
        """Test similarity for completely different diagrams"""
        expected = """graph TD
    A[Start] --> B[End]
"""

        actual = """graph TD
    X[Begin] --> Y[Process]
    Y --> Z[Finish]
"""

        diff = self.generator.compute_diff(expected, actual)

        # Should detect low similarity
        assert diff["similarity_percent"] < 60


if __name__ == "__main__":
    print("\n[TEST] Running Mermaid Diagram Generator Tests\n")
    print("=" * 60)

    # Run tests
    generator = DiagramGenerator()

    print("\n[1] Testing spec-to-diagram generation...")
    test = TestDiagramGenerator()
    test.setup_method()
    test.test_generate_from_spec_basic()

    print("\n[2] Testing code-to-diagram generation...")
    test.test_generate_from_code_basic()

    print("\n[3] Testing diagram diff (identical)...")
    test.test_compute_diff_identical()

    print("\n[4] Testing diagram diff (different)...")
    test.test_compute_diff_different()

    print("\n[5] Testing diagram parsing...")
    test.test_parse_diagram_extracts_nodes()

    print("\n" + "=" * 60)
    print("[OK] All diagram generator tests completed!\n")

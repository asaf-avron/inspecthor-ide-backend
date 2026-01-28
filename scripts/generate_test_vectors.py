"""
Test vector generation: Extract concrete test cases from Dafny GenerateTests() methods.
Uses Dafny /mv flag to generate model values from concrete instances.
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_dafny_model_values(
    dafny_file: str,
    method_name: str = "GenerateTests",
    docker_service: str = "api"
) -> Optional[str]:
    """
    Run Dafny with /mv flag to generate model values from GenerateTests() method.
    
    Args:
        dafny_file: Path to Dafny file
        method_name: Name of test generation method
        docker_service: Docker Compose service name
    
    Returns:
        Model values output as string, or None if error
    """
    cmd = [
        "docker-compose",
        "exec",
        "-T",
        docker_service,
        "dafny",
        "verify",
        "/mv",
        dafny_file
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            logger.error(f"Dafny model values generation failed: {result.stderr}")
            return None
        
        return result.stdout
    
    except subprocess.TimeoutExpired:
        logger.error("Dafny model values generation timed out")
        return None
    except Exception as e:
        logger.error(f"Error running Dafny model values: {e}")
        return None


def parse_model_values(output: str) -> List[Dict[str, Any]]:
    """
    Parse Dafny model values output to extract test vectors.
    
    Args:
        output: Dafny /mv output
    
    Returns:
        List of test vector dictionaries
    """
    # TODO: Implement proper parsing of Dafny model values format
    # This is a placeholder - actual format depends on Dafny version
    
    test_vectors = []
    
    # Simple extraction: look for test case patterns
    # Actual implementation needs to parse Dafny's model value format
    
    lines = output.split('\n')
    current_vector = {}
    
    for line in lines:
        if "TestCase" in line or "testCases" in line:
            # Extract test case data
            # This is a simplified parser - needs refinement
            pass
    
    return test_vectors


def export_test_vectors_json(
    test_vectors: List[Dict[str, Any]],
    output_path: str
) -> None:
    """
    Export test vectors to JSON file.
    
    Args:
        test_vectors: List of test vector dictionaries
        output_path: Path to output JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(test_vectors, f, indent=2, default=str)
    
    logger.info(f"Exported {len(test_vectors)} test vectors to {output_path}")


def generate_pytest_file(
    test_vectors: List[Dict[str, Any]],
    output_path: str,
    module_name: str
) -> None:
    """
    Generate pytest-compatible test file from test vectors.
    
    Args:
        test_vectors: List of test vector dictionaries
        output_path: Path to output Python test file
        module_name: Name of module being tested
    """
    test_code = f'''"""
Oracle tests for {module_name}.
Generated from Dafny GenerateTests() method.
"""

import pytest
from api.core import {module_name}


@pytest.mark.parametrize("test_vector", [
'''
    
    for i, vector in enumerate(test_vectors):
        test_code += f"    {json.dumps(vector, default=str)},\n"
    
    test_code += '''])
def test_oracle(test_vector):
    """
    Oracle test: Verify Python implementation matches Dafny specification.
    """
    # TODO: Implement test logic
    # Extract inputs from test_vector
    # Call Python function
    # Compare output with expected result from Dafny
    pass
'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    logger.info(f"Generated pytest file: {output_path}")


def main():
    """Main entry point for test vector generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test vectors from Dafny specs")
    parser.add_argument("dafny_file", help="Path to Dafny specification file")
    parser.add_argument("--method", default="GenerateTests", help="Test generation method name")
    parser.add_argument("--output-json", help="Output JSON file path", default=None)
    parser.add_argument("--output-pytest", help="Output pytest file path", default=None)
    parser.add_argument("--module", help="Python module name for pytest generation", default=None)
    parser.add_argument("--docker-service", default="api", help="Docker Compose service name")
    
    args = parser.parse_args()
    
    # Run Dafny model values generation
    logger.info(f"Generating model values from {args.dafny_file}")
    output = run_dafny_model_values(args.dafny_file, args.method, args.docker_service)
    
    if not output:
        logger.error("Failed to generate model values")
        return 1
    
    # Parse test vectors
    test_vectors = parse_model_values(output)
    
    if not test_vectors:
        logger.warning("No test vectors extracted")
        return 1
    
    # Export JSON
    if args.output_json:
        export_test_vectors_json(test_vectors, args.output_json)
    
    # Generate pytest file
    if args.output_pytest and args.module:
        generate_pytest_file(test_vectors, args.output_pytest, args.module)
    
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exit(main())

"""
LLM-based Python code generation from Dafny specs.
Synthesis script for generating Python Core functions from Dafny specifications.

This script uses the manual migration.py as a "few-shot" example to guide synthesis.
"""

import sys
from pathlib import Path
from typing import Optional
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def load_dafny_spec(spec_path: str) -> str:
    """
    Load Dafny specification file.
    
    Args:
        spec_path: Path to .dfy file
    
    Returns:
        File contents as string
    """
    with open(spec_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_few_shot_example() -> str:
    """
    Load manual synthesis example (migration.py) as few-shot template.
    
    Returns:
        Example Python code matching Dafny spec
    """
    example_path = Path(__file__).parent.parent / "api" / "core" / "migration.py"
    with open(example_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_function_signature(dafny_code: str, function_name: str) -> Optional[str]:
    """
    Extract function signature from Dafny code.
    
    Args:
        dafny_code: Dafny source code
        function_name: Name of function to extract
    
    Returns:
        Function signature string or None if not found
    """
    # Simple extraction: look for function declaration
    lines = dafny_code.split('\n')
    in_function = False
    signature_lines = []
    
    for line in lines:
        if f"function {function_name}" in line:
            in_function = True
            signature_lines.append(line.strip())
        elif in_function:
            if '{' in line:
                break
            signature_lines.append(line.strip())
    
    return '\n'.join(signature_lines) if signature_lines else None


def generate_llm_prompt(
    dafny_spec: str,
    function_name: str,
    target_module: str,
    few_shot_example: str
) -> str:
    """
    Generate LLM prompt for Python synthesis.
    
    Args:
        dafny_spec: Complete Dafny specification
        function_name: Name of function to synthesize
        target_module: Target Python module name (e.g., "file_operations")
        few_shot_example: Manual synthesis example code
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are a code synthesis tool that translates Dafny specifications to Python.

Your task is to generate a Python function matching the Dafny specification exactly.

## Dafny Specification:
```dafny
{dafny_spec}
```

## Target Function:
{function_name}

## Few-Shot Example (Manual Synthesis):
```python
{few_shot_example}
```

## Requirements:
1. Match the Dafny function signature exactly
2. Use icontract decorators matching Dafny pre/postconditions
3. Pure function: no side effects, no database access
4. Use immutable SystemState models from api.core.models
5. Return new SystemState (immutable update pattern)
6. Include docstring referencing Dafny spec location

## Output Format:
Generate only the Python function code, including:
- Import statements needed
- @icontract decorators
- Function implementation
- Docstring

Do not include any explanation or markdown formatting.
"""
    return prompt


def synthesize_python_code(
    dafny_spec_path: str,
    function_name: str,
    target_module: str,
    llm_api_key: Optional[str] = None,
    llm_provider: str = "openai"
) -> str:
    """
    Synthesize Python code from Dafny spec using LLM.
    
    Args:
        dafny_spec_path: Path to Dafny .dfy file
        function_name: Name of function to synthesize
        target_module: Target Python module name
        llm_api_key: API key for LLM provider
        llm_provider: LLM provider ("openai", "gemini", "anthropic")
    
    Returns:
        Generated Python code
    
    Note:
        This is a skeleton - actual LLM integration needs to be implemented.
    """
    # Load inputs
    dafny_spec = load_dafny_spec(dafny_spec_path)
    few_shot_example = load_few_shot_example()
    
    # Generate prompt
    prompt = generate_llm_prompt(dafny_spec, function_name, target_module, few_shot_example)
    
    # TODO: Call LLM API
    # For now, return placeholder
    logger.warning("LLM synthesis not yet implemented - returning placeholder")
    
    return f"""# Generated from {dafny_spec_path} :: {function_name}
# TODO: Implement LLM synthesis
# Prompt generated: {len(prompt)} characters
"""


def main():
    """Main entry point for synthesis script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Synthesize Python code from Dafny specs")
    parser.add_argument("dafny_spec", help="Path to Dafny specification file")
    parser.add_argument("function_name", help="Name of function to synthesize")
    parser.add_argument("target_module", help="Target Python module name")
    parser.add_argument("--output", help="Output file path", default=None)
    parser.add_argument("--llm-provider", choices=["openai", "gemini", "anthropic"], default="openai")
    parser.add_argument("--llm-api-key", help="LLM API key", default=None)
    
    args = parser.parse_args()
    
    # Synthesize code
    python_code = synthesize_python_code(
        args.dafny_spec,
        args.function_name,
        args.target_module,
        llm_api_key=args.llm_api_key,
        llm_provider=args.llm_provider
    )
    
    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(python_code)
        print(f"Generated code written to {args.output}")
    else:
        print(python_code)


if __name__ == "__main__":
    main()

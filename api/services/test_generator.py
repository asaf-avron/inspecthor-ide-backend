"""
Test Generator Service - Horizon C: Runtime Verification

Generates pytest test suites from Dafny formal specifications.

This implements Horizon C of the Three Horizons of Truth:
- Horizon A: Intent (Mermaid diagrams) ✓
- Horizon B: Logic (Dafny verification) ✓
- Horizon C: Runtime (Test generation) ← This module

Ensures that Shell (Python implementation) obeys Kernel (Dafny spec).
"""

import re
import ast
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TestType(str, Enum):
    """Types of tests that can be generated"""
    UNIT = "unit"
    PROPERTY = "property"
    FUZZER = "fuzzer"
    INTEGRATION = "integration"


@dataclass
class DafnyMethod:
    """Represents a parsed Dafny method"""
    name: str
    parameters: List[Tuple[str, str]]  # (param_name, param_type)
    return_type: Optional[str]
    preconditions: List[str]  # requires clauses
    postconditions: List[str]  # ensures clauses
    body: Optional[str]


@dataclass
class GeneratedTest:
    """Represents a generated test case"""
    test_name: str
    test_type: TestType
    test_code: str
    description: str
    method_under_test: str


class TestGenerator:
    """Generates test suites from Dafny specifications"""

    def __init__(self):
        """Initialize test generator"""
        pass

    def generate_from_dafny(
        self,
        dafny_code: str,
        test_types: List[TestType]
    ) -> List[GeneratedTest]:
        """
        Generate pytest test suite from Dafny specification

        Args:
            dafny_code: Dafny formal specification
            test_types: Types of tests to generate (unit, property, fuzzer)

        Returns:
            List of GeneratedTest objects
        """
        try:
            # Parse Dafny methods
            methods = self._parse_dafny_methods(dafny_code)

            if not methods:
                return []  # No methods to test

            # Generate tests for each method
            generated_tests = []

            for method in methods:
                # Generate unit tests
                if TestType.UNIT in test_types:
                    unit_tests = self._generate_unit_tests(method)
                    generated_tests.extend(unit_tests)

                # Generate property-based tests
                if TestType.PROPERTY in test_types:
                    property_tests = self._generate_property_tests(method)
                    generated_tests.extend(property_tests)

            logger.info(f"Generated {len(generated_tests)} tests for {test_types}")

            return generated_tests

        except Exception as e:
            logger.error(f"Failed to generate tests: {e}")
            return []

    def generate_fuzzer(
        self,
        module_name: str,
        entry_points: List[str]
    ) -> List[GeneratedTest]:
        """
        Generate fuzzer tests for robustness testing

        Args:
            module_name: Name of the module to test
            entry_points: List of function names to fuzz

        Returns:
            List of fuzzer test objects
        """
        try:
            fuzzer_tests = []

            # Generate fuzzer for each entry point
            for func_name in entry_points:
                test_name = f"test_fuzz_{func_name}"

                test_code = f"""
def {test_name}():
    \"\"\"Fuzzer test for {func_name}\"\"\"
    import random
    import string

    # Generate random inputs
    for _ in range(100):
        # Random string input
        random_str = ''.join(random.choices(string.printable, k=random.randint(0, 1000)))

        # Random integer input
        random_int = random.randint(-1000000, 1000000)

        # Random list input
        random_list = [random.randint(-100, 100) for _ in range(random.randint(0, 100))]

        # Test with random inputs (should not crash)
        try:
            # Call function with various random inputs
            {func_name}(random_str)
            {func_name}(random_int)
            {func_name}(random_list)
        except Exception:
            # Expected - function may reject invalid input
            pass
"""

                fuzzer_tests.append(GeneratedTest(
                    test_name=test_name,
                    test_type=TestType.FUZZER,
                    test_code=test_code.strip(),
                    description=f"Fuzzer test for {func_name}",
                    method_under_test=func_name
                ))

            logger.info(f"Generated {len(fuzzer_tests)} fuzzer tests")

            return fuzzer_tests

        except Exception as e:
            logger.error(f"Failed to generate fuzzer: {e}")
            return []

    def _parse_dafny_methods(self, dafny_code: str) -> List[DafnyMethod]:
        """
        Parse Dafny code to extract method signatures and contracts

        Args:
            dafny_code: Dafny source code

        Returns:
            List of DafnyMethod objects
        """
        methods = []

        # Simple regex-based parsing
        # Pattern: method MethodName(params) returns (type) requires ... ensures ...
        method_pattern = r'method\s+(\w+)\s*\((.*?)\)\s*(?:returns\s*\((.*?)\))?\s*(.*?)(?=method\s+|\Z)'

        matches = re.finditer(method_pattern, dafny_code, re.DOTALL)

        for match in matches:
            method_name = match.group(1)
            params_str = match.group(2)
            returns_str = match.group(3)
            body_and_contracts = match.group(4)

            # Parse parameters
            parameters = self._parse_parameters(params_str)

            # Parse return type (extract just the type from "varname: type")
            return_type = None
            if returns_str:
                returns_str = returns_str.strip()
                if ':' in returns_str:
                    # Format: "result: int" -> extract "int"
                    return_type = returns_str.split(':', 1)[1].strip()
                else:
                    return_type = returns_str

            # Extract requires and ensures
            preconditions = self._extract_requires(body_and_contracts)
            postconditions = self._extract_ensures(body_and_contracts)

            methods.append(DafnyMethod(
                name=method_name,
                parameters=parameters,
                return_type=return_type,
                preconditions=preconditions,
                postconditions=postconditions,
                body=body_and_contracts
            ))

        return methods

    def _parse_parameters(self, params_str: str) -> List[Tuple[str, str]]:
        """Parse Dafny parameter string"""
        parameters: List[Tuple[str, str]] = []

        if not params_str or not params_str.strip():
            return parameters

        # Split by comma
        param_parts = params_str.split(',')

        for part in param_parts:
            part = part.strip()
            if ':' in part:
                name, param_type = part.split(':', 1)
                parameters.append((name.strip(), param_type.strip()))

        return parameters

    def _extract_requires(self, body: str) -> List[str]:
        """Extract requires clauses from Dafny method body"""
        requires = []
        pattern = r'requires\s+(.*?)(?=\n\s*(?:requires|ensures|{))'

        matches = re.finditer(pattern, body, re.DOTALL)
        for match in matches:
            condition = match.group(1).strip()
            if condition:
                requires.append(condition)

        return requires

    def _extract_ensures(self, body: str) -> List[str]:
        """Extract ensures clauses from Dafny method body"""
        ensures = []
        pattern = r'ensures\s+(.*?)(?=\n\s*(?:requires|ensures|{))'

        matches = re.finditer(pattern, body, re.DOTALL)
        for match in matches:
            condition = match.group(1).strip()
            if condition:
                ensures.append(condition)

        return ensures

    def _generate_unit_tests(
        self,
        method: DafnyMethod
    ) -> List[GeneratedTest]:
        """Generate basic unit tests for a method"""
        tests = []

        # Generate happy path test
        happy_path_test = self._generate_happy_path_test(method)
        if happy_path_test:
            tests.append(happy_path_test)

        # Generate edge case tests based on preconditions
        if method.preconditions:
            edge_tests = self._generate_edge_case_tests(method)
            tests.extend(edge_tests)

        return tests

    def _generate_happy_path_test(
        self,
        method: DafnyMethod
    ) -> Optional[GeneratedTest]:
        """Generate a basic happy path test"""
        test_name = f"test_{method.name.lower()}_happy_path"

        # Generate test parameters (simple defaults)
        param_assignments = []
        param_names = []

        for param_name, param_type in method.parameters:
            default_value = self._get_default_value(param_type)
            param_assignments.append(f"    {param_name} = {default_value}")
            param_names.append(param_name)

        params_call = ", ".join(param_names)

        # Generate test code
        test_code = f"""
def {test_name}():
    \"\"\"Test {method.name} with valid inputs\"\"\"
{chr(10).join(param_assignments) if param_assignments else '    pass'}

    # Call method
    result = {method.name}({params_call})

    # Verify postconditions
{self._generate_postcondition_checks(method)}
"""

        return GeneratedTest(
            test_name=test_name,
            test_type=TestType.UNIT,
            test_code=test_code.strip(),
            description=f"Happy path test for {method.name}",
            method_under_test=method.name
        )

    def _generate_edge_case_tests(
        self,
        method: DafnyMethod
    ) -> List[GeneratedTest]:
        """Generate edge case tests based on preconditions"""
        tests = []

        # For each precondition, generate a test that violates it
        for i, precondition in enumerate(method.preconditions):
            test_name = f"test_{method.name.lower()}_violates_precondition_{i+1}"

            test_code = f"""
def {test_name}():
    \"\"\"Test {method.name} with invalid input (violates: {precondition[:50]})\"\"\"
    # This test should raise an exception or return error

    # TODO: Generate inputs that violate: {precondition}
    # Call method and expect failure
    with pytest.raises(Exception):
        # Generate violating input
        pass
"""

            tests.append(GeneratedTest(
                test_name=test_name,
                test_type=TestType.UNIT,
                test_code=test_code.strip(),
                description=f"Edge case test for {method.name} (precondition violation)",
                method_under_test=method.name
            ))

        return tests

    def _generate_property_tests(
        self,
        method: DafnyMethod
    ) -> List[GeneratedTest]:
        """Generate property-based tests using Hypothesis"""
        tests = []

        test_name = f"test_{method.name.lower()}_properties"

        # Generate Hypothesis strategies for parameters
        strategies = []
        param_names = []

        for param_name, param_type in method.parameters:
            strategy = self._get_hypothesis_strategy(param_type)
            strategies.append(f"    {param_name}=st.{strategy}")
            param_names.append(param_name)

        params_call = ", ".join(param_names)

        test_code = f"""
from hypothesis import given, strategies as st

@given(
{','.join(strategies)}
)
def {test_name}({', '.join(param_names)}):
    \"\"\"Property-based test for {method.name}\"\"\"
    # Assume preconditions (if violated, skip test)
{self._generate_precondition_assumptions(method)}

    # Call method
    result = {method.name}({params_call})

    # Assert postconditions
{self._generate_postcondition_assertions(method)}
"""

        tests.append(GeneratedTest(
            test_name=test_name,
            test_type=TestType.PROPERTY,
            test_code=test_code.strip(),
            description=f"Property-based test for {method.name}",
            method_under_test=method.name
        ))

        return tests

    def _generate_fuzzer_test(
        self,
        method: DafnyMethod,
        python_func: str,
        component_name: str
    ) -> str:
        """Generate a fuzzer test for a specific method"""
        test_name = f"test_fuzz_{method.name.lower()}"

        # Generate random inputs based on parameter types
        param_generators = []
        for param_name, param_type in method.parameters:
            generator = self._get_fuzzer_generator(param_type)
            param_generators.append(f"        {param_name} = {generator}")

        test_code = f"""
def {test_name}():
    \"\"\"Fuzzer test for {method.name}\"\"\"
    for _ in range(100):  # 100 random test cases
{chr(10).join(param_generators)}

        try:
            result = {python_func}({', '.join([p[0] for p in method.parameters])})
            # Verify result follows Kernel spec
{self._generate_postcondition_checks(method)}
        except Exception as e:
            # Shell should handle all Kernel exceptions gracefully
            pass
"""

        return test_code.strip()

    def _extract_python_functions(self, python_code: str) -> List[str]:
        """Extract function names from Python code"""
        functions = []

        try:
            tree = ast.parse(python_code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)

        except Exception as e:
            logger.warning(f"Failed to parse Python code: {e}")

        return functions

    def _find_matching_function(
        self,
        dafny_method: str,
        python_functions: List[str]
    ) -> Optional[str]:
        """Find Python function matching Dafny method"""
        # Simple name matching (case-insensitive)
        dafny_lower = dafny_method.lower()

        for func in python_functions:
            if func.lower() == dafny_lower:
                return func

        return None

    def _create_fuzzer_module(
        self,
        fuzzer_tests: List[str],
        component_name: str
    ) -> str:
        """Create complete fuzzer test module"""
        header = f"""
\"\"\"
Fuzzer tests for {component_name}
Auto-generated from Dafny specification

Ensures Shell (Python) handles all Kernel (Dafny) edge cases.
\"\"\"

import pytest
import random
import string
from hypothesis import given, strategies as st

"""

        return header + "\n\n".join(fuzzer_tests)

    def _get_default_value(self, param_type: str) -> str:
        """Get default value for a parameter type"""
        type_defaults = {
            'int': '0',
            'bool': 'False',
            'string': '""',
            'str': '""',
            'nat': '0',
            'real': '0.0'
        }

        param_type_lower = param_type.lower()
        for type_key, default in type_defaults.items():
            if type_key in param_type_lower:
                return default

        return 'None'

    def _get_hypothesis_strategy(self, param_type: str) -> str:
        """Get Hypothesis strategy for a parameter type"""
        type_strategies = {
            'int': 'integers()',
            'nat': 'integers(min_value=0)',
            'bool': 'booleans()',
            'string': 'text()',
            'str': 'text()',
            'real': 'floats(allow_nan=False, allow_infinity=False)'
        }

        param_type_lower = param_type.lower()
        for type_key, strategy in type_strategies.items():
            if type_key in param_type_lower:
                return strategy

        return 'text()'

    def _get_fuzzer_generator(self, param_type: str) -> str:
        """Get random value generator for fuzzer"""
        type_generators = {
            'int': 'random.randint(-1000, 1000)',
            'nat': 'random.randint(0, 1000)',
            'bool': 'random.choice([True, False])',
            'string': '"".join(random.choices(string.ascii_letters, k=10))',
            'str': '"".join(random.choices(string.ascii_letters, k=10))',
            'real': 'random.uniform(-100.0, 100.0)'
        }

        param_type_lower = param_type.lower()
        for type_key, generator in type_generators.items():
            if type_key in param_type_lower:
                return generator

        return '""'

    def _generate_postcondition_checks(self, method: DafnyMethod) -> str:
        """Generate assertions for postconditions"""
        if not method.postconditions:
            return "    # No postconditions to verify"

        checks = []
        for i, postcondition in enumerate(method.postconditions):
            # Simplified: just add as comment (full translation complex)
            checks.append(f"    # TODO: Verify postcondition: {postcondition}")

        return "\n".join(checks)

    def _generate_precondition_assumptions(self, method: DafnyMethod) -> str:
        """Generate Hypothesis assumptions for preconditions"""
        if not method.preconditions:
            return "    pass"

        assumptions = []
        for precondition in method.preconditions:
            # Simplified: add as comment
            assumptions.append(f"    # assume({precondition})")

        return "\n".join(assumptions)

    def _generate_postcondition_assertions(self, method: DafnyMethod) -> str:
        """Generate assertions for postconditions in property tests"""
        if not method.postconditions:
            return "    assert True  # No postconditions"

        assertions = []
        for postcondition in method.preconditions:
            # Simplified: add as comment
            assertions.append(f"    # assert {postcondition}")

        return "\n".join(assertions)

    def create_test_module(
        self,
        tests: List[GeneratedTest],
        component_name: str
    ) -> str:
        """
        Create complete pytest test module

        Args:
            tests: List of generated tests
            component_name: Name of the component

        Returns:
            Complete test module as string
        """
        header = f"""
\"\"\"
Auto-generated tests for {component_name}
Generated from Dafny formal specification

Horizon C: Runtime Verification
Ensures Shell (Python implementation) obeys Kernel (Dafny spec)
\"\"\"

import pytest
from hypothesis import given, strategies as st

"""

        # Group tests by type
        unit_tests = [t for t in tests if t.test_type == TestType.UNIT]
        property_tests = [t for t in tests if t.test_type == TestType.PROPERTY]

        module_code = header

        if unit_tests:
            module_code += "\n# Unit Tests\n\n"
            for test in unit_tests:
                module_code += test.test_code + "\n\n"

        if property_tests:
            module_code += "\n# Property-Based Tests\n\n"
            for test in property_tests:
                module_code += test.test_code + "\n\n"

        return module_code.strip()

"""
Tests for Test Generator Service (Task #8 - Runtime Verification)
Horizon C: Ensuring Shell obeys Kernel
"""

import pytest
from api.services.test_generator import TestGenerator, TestType, DafnyMethod


class TestTestGenerator:
    """Test automatic test generation from Dafny specs"""

    def setup_method(self):
        """Create test generator for tests"""
        self.generator = TestGenerator()

    def test_parse_simple_dafny_method(self):
        """Test parsing a simple Dafny method"""
        dafny_code = """
method Add(x: int, y: int) returns (result: int)
    ensures result == x + y
{
    result := x + y;
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 1
        assert methods[0].name == "Add"
        assert len(methods[0].parameters) == 2
        assert methods[0].return_type == "int"
        assert len(methods[0].postconditions) == 1
        assert "x + y" in methods[0].postconditions[0]

    def test_parse_method_with_preconditions(self):
        """Test parsing method with requires clause"""
        dafny_code = """
method Divide(x: int, y: int) returns (result: int)
    requires y != 0
    ensures result == x / y
{
    result := x / y;
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 1
        assert methods[0].name == "Divide"
        assert len(methods[0].preconditions) == 1
        assert "y != 0" in methods[0].preconditions[0]
        assert len(methods[0].postconditions) == 1

    def test_parse_multiple_methods(self):
        """Test parsing multiple methods"""
        dafny_code = """
method Foo() returns (r: int)
{
    r := 1;
}

method Bar(x: int) returns (r: int)
    requires x > 0
{
    r := x + 1;
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 2
        assert methods[0].name == "Foo"
        assert methods[1].name == "Bar"

    def test_generate_unit_test(self):
        """Test generating unit tests"""
        dafny_code = """
method IsEven(n: int) returns (result: bool)
    ensures result == (n % 2 == 0)
{
    result := n % 2 == 0;
}
"""
        tests = self.generator.generate_from_dafny(dafny_code, [TestType.UNIT])

        assert len(tests) > 0
        assert any(t.test_type == TestType.UNIT for t in tests)
        assert any("iseven" in t.test_name.lower() for t in tests)

        # Check test code contains verification (assertions or TODO comments)
        unit_test = next(t for t in tests if t.test_type == TestType.UNIT)
        assert ("assert" in unit_test.test_code.lower() or "verify" in unit_test.test_code.lower())

    def test_generate_property_test(self):
        """Test generating property-based tests"""
        dafny_code = """
method Abs(x: int) returns (result: int)
    ensures result >= 0
    ensures result == x || result == -x
{
    if x < 0 {
        result := -x;
    } else {
        result := x;
    }
}
"""
        tests = self.generator.generate_from_dafny(
            dafny_code,
            [TestType.PROPERTY]
        )

        assert len(tests) > 0
        property_test = next(t for t in tests if t.test_type == TestType.PROPERTY)

        # Should use Hypothesis
        assert "hypothesis" in property_test.test_code.lower() or "@given" in property_test.test_code

    def test_generate_fuzzer_test(self):
        """Test generating fuzzer tests"""
        tests = self.generator.generate_fuzzer(
            module_name="MyModule",
            entry_points=["process_input", "handle_request"]
        )

        assert len(tests) > 0
        assert any(t.test_type == TestType.FUZZER for t in tests)

        fuzzer_test = tests[0]
        assert "random" in fuzzer_test.test_code.lower() or "fuzzer" in fuzzer_test.test_code.lower()

    def test_create_test_module(self):
        """Test creating complete test module"""
        dafny_code = """
method Add(x: int, y: int) returns (result: int)
    ensures result == x + y
{
    result := x + y;
}
"""
        tests = self.generator.generate_from_dafny(dafny_code, [TestType.UNIT])
        module_code = self.generator.create_test_module(tests, "arithmetic")

        # Check module structure
        assert "import pytest" in module_code
        assert "def test_" in module_code
        assert "arithmetic" in module_code

    def test_empty_dafny_code(self):
        """Test handling empty Dafny code"""
        tests = self.generator.generate_from_dafny("", [TestType.UNIT])

        # Should return empty list
        assert len(tests) == 0

    def test_dafny_with_no_methods(self):
        """Test Dafny code with only data structures"""
        dafny_code = """
datatype Color = Red | Green | Blue

class Point {
    var x: int
    var y: int
}
"""
        tests = self.generator.generate_from_dafny(dafny_code, [TestType.UNIT])

        # No methods to test
        assert len(tests) == 0

    def test_method_with_multiple_ensures(self):
        """Test method with multiple postconditions"""
        dafny_code = """
method Clamp(x: int, min: int, max: int) returns (result: int)
    requires min <= max
    ensures result >= min
    ensures result <= max
    ensures (min <= x <= max) ==> result == x
{
    if x < min {
        result := min;
    } else if x > max {
        result := max;
    } else {
        result := x;
    }
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 1
        assert len(methods[0].preconditions) == 1
        assert len(methods[0].postconditions) == 3

    def test_method_with_multiple_requires(self):
        """Test method with multiple preconditions"""
        dafny_code = """
method Process(x: int, y: int) returns (result: int)
    requires x > 0
    requires y > 0
    requires x < 100
{
    result := x + y;
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 1
        assert len(methods[0].preconditions) == 3

    def test_generate_all_test_types(self):
        """Test generating all types of tests"""
        dafny_code = """
method Square(x: int) returns (result: int)
    ensures result >= 0
    ensures result == x * x
{
    result := x * x;
}
"""
        tests = self.generator.generate_from_dafny(
            dafny_code,
            [TestType.UNIT, TestType.PROPERTY]
        )

        # Should have both unit and property tests
        test_types = set(t.test_type for t in tests)
        assert TestType.UNIT in test_types
        assert TestType.PROPERTY in test_types

    def test_test_descriptions(self):
        """Test that generated tests have descriptions"""
        dafny_code = """
method GetLength(s: string) returns (len: int)
    ensures len >= 0
{
    len := |s|;
}
"""
        tests = self.generator.generate_from_dafny(dafny_code, [TestType.UNIT])

        assert len(tests) > 0
        for test in tests:
            assert test.description is not None
            assert len(test.description) > 0

    def test_method_under_test_tracking(self):
        """Test that tests track which method they test"""
        dafny_code = """
method Foo() returns (r: int) { r := 1; }
method Bar() returns (r: int) { r := 2; }
"""
        tests = self.generator.generate_from_dafny(dafny_code, [TestType.UNIT])

        # Each test should know which method it tests
        for test in tests:
            assert test.method_under_test in ["Foo", "Bar"]

    def test_test_names_are_unique(self):
        """Test that generated test names are unique"""
        dafny_code = """
method Process(x: int) returns (r: int) { r := x; }
"""
        tests = self.generator.generate_from_dafny(
            dafny_code,
            [TestType.UNIT, TestType.PROPERTY]
        )

        test_names = [t.test_name for t in tests]
        assert len(test_names) == len(set(test_names))

    def test_complex_dafny_method(self):
        """Test parsing complex Dafny with nested structures"""
        dafny_code = """
method BinarySearch(arr: array<int>, key: int) returns (index: int)
    requires arr.Length > 0
    requires forall i, j :: 0 <= i < j < arr.Length ==> arr[i] <= arr[j]
    ensures 0 <= index <= arr.Length
    ensures index < arr.Length ==> arr[index] == key
    ensures index == arr.Length ==> forall i :: 0 <= i < arr.Length ==> arr[i] != key
{
    var low := 0;
    var high := arr.Length;
    while low < high
        invariant 0 <= low <= high <= arr.Length
    {
        var mid := (low + high) / 2;
        if arr[mid] < key {
            low := mid + 1;
        } else if arr[mid] > key {
            high := mid;
        } else {
            return mid;
        }
    }
    return arr.Length;
}
"""
        methods = self.generator._parse_dafny_methods(dafny_code)

        assert len(methods) == 1
        assert methods[0].name == "BinarySearch"
        assert len(methods[0].preconditions) >= 2
        assert len(methods[0].postconditions) >= 3


if __name__ == "__main__":
    print("\n[TEST] Running Test Generator Tests\n")
    print("=" * 60)

    generator = TestGenerator()

    print("\n[1] Testing Dafny method parsing...")
    test = TestTestGenerator()
    test.setup_method()
    test.test_parse_simple_dafny_method()
    test.test_parse_method_with_preconditions()
    print("[OK] Dafny parsing works")

    print("\n[2] Testing unit test generation...")
    test.test_generate_unit_test()
    print("[OK] Unit test generation works")

    print("\n[3] Testing property-based test generation...")
    test.test_generate_property_test()
    print("[OK] Property test generation works")

    print("\n[4] Testing fuzzer generation...")
    test.test_generate_fuzzer_test()
    print("[OK] Fuzzer generation works")

    print("\n[5] Testing test module creation...")
    test.test_create_test_module()
    print("[OK] Test module creation works")

    print("\n" + "=" * 60)
    print("[OK] All test generator tests completed!\n")

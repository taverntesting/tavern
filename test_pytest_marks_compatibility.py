#!/usr/bin/env python3
"""
Test script to verify Pytest mark compatibility fixes
"""

import pytest
import sys
import os

# Add the tavern directory to the path so we can import tavern modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tavern'))

def test_mark_imports():
    """Test that the new mark imports work correctly"""
    try:
        from _pytest.mark.structures import Mark
        print("✓ Successfully imported Mark from _pytest.mark.structures")
    except ImportError as e:
        print(f"✗ Failed to import Mark: {e}")
        return False

    try:
        from tavern._core.pytest.file import _format_test_marks
        print("✓ Successfully imported _format_test_marks")
    except ImportError as e:
        print(f"✗ Failed to import _format_test_marks: {e}")
        return False

    try:
        from tavern._core.pytest.item import YamlItem
        print("✓ Successfully imported YamlItem")
    except ImportError as e:
        print(f"✗ Failed to import YamlItem: {e}")
        return False

    return True

def test_mark_creation():
    """Test that mark creation works with the new API"""
    from _pytest.mark.structures import Mark

    # Test simple mark creation
    simple_mark = Mark("slow", (), {})
    assert simple_mark.name == "slow"
    assert simple_mark.args == ()
    assert simple_mark.kwargs == {}

    # Test mark with arguments
    arg_mark = Mark("skipif", ("condition",), {})
    assert arg_mark.name == "skipif"
    assert arg_mark.args == ("condition",)

    print("✓ Mark creation tests passed")

def test_format_test_marks():
    """Test the refactored _format_test_marks function"""
    from tavern._core.pytest.file import _format_test_marks

    # Test with empty marks
    marks, formatted = _format_test_marks([], {}, "test_name")
    assert marks == []
    assert formatted == []

    # Test with simple string mark
    marks, formatted = _format_test_marks(["slow"], {}, "test_name")
    assert len(marks) == 1
    assert marks[0].name == "slow"
    assert marks[0].args == ()

    # Test with dict mark
    marks, formatted = _format_test_marks([{"skipif": "condition"}], {}, "test_name")
    assert len(marks) == 1
    assert marks[0].name == "skipif"
    assert marks[0].args == ("condition",)

    print("✓ _format_test_marks tests passed")

def test_pytest_version():
    """Test that we're using a compatible Pytest version"""
    import pytest
    version = pytest.__version__
    print(f"Pytest version: {version}")

    # Parse version to check if it's >= 7.3.0
    major, minor, patch = map(int, version.split('.')[:3])
    if major > 7 or (major == 7 and minor >= 3):
        print("✓ Using Pytest 7.3.0+ (compatible)")
        return True
    else:
        print("✗ Using Pytest < 7.3.0 (may have compatibility issues)")
        return False

def main():
    """Run all compatibility tests"""
    print("Testing Pytest Mark Compatibility Fixes")
    print("=" * 40)

    tests = [
        test_mark_imports,
        test_mark_creation,
        test_format_test_marks,
        test_pytest_version,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed: {e}")

    print("\n" + "=" * 40)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All compatibility tests passed!")
        return 0
    else:
        print("✗ Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

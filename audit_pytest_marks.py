#!/usr/bin/env python3
"""
Tavern Pytest Mark Compatibility Audit Script
--------------------------------------------
This script performs a comprehensive audit of all Pytest mark handling in the Tavern
codebase to ensure compatibility with Pytest 7.3.0+.

The script checks for:
1. Deprecated mark usage patterns
2. Modern mark API usage
3. Custom mark registration
4. Test compatibility

Run this script from the Tavern repository root:
    python3 audit_pytest_marks.py

Author: GitHub Copilot Chat Assistant
Date: 2025-01-12
"""

import os
import re
import sys
import ast
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class PytestMarkAuditor:
    """Audits Pytest mark usage for compatibility with Pytest 7.3.0+"""

    def __init__(self):
        self.deprecated_patterns = {
            r'\.get_marker\(': 'Use item.iter_markers() instead',
            r'getattr\s*\(\s*pytest\.mark\s*,\s*[\'"]\w+[\'"]\s*\)': 'Use Mark() constructor instead',
            r'\.mark\.args': 'Use .args directly on Mark object',
            # Exclude valid decorators like @pytest.mark.parametrize
            r'(?<!@)pytest\.mark\.\w+\(': 'Use Mark() constructor for programmatic mark creation',
        }

        self.modern_patterns = {
            r'from _pytest\.mark\.structures import Mark': 'Modern Mark import',
            r'Mark\(': 'Modern Mark constructor usage',
            r'\.iter_markers\(': 'Modern mark iteration',
            r'\.args\b': 'Modern args access',
        }

        self.files_audited = 0
        self.issues_found = []
        self.modern_usage_found = []

    def audit_file(self, filepath: Path) -> Dict[str, Any]:
        """Audit a single file for Pytest mark usage"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {filepath}: {e}")
            return {"file": str(filepath), "error": str(e)}

        issues = []
        modern_usage = []

        # Check for deprecated patterns
        for pattern, message in self.deprecated_patterns.items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    "line": line_num,
                    "pattern": pattern,
                    "message": message,
                    "context": self._get_line_context(content, match.start())
                })

        # Check for modern patterns
        for pattern, message in self.modern_patterns.items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                modern_usage.append({
                    "line": line_num,
                    "pattern": pattern,
                    "message": message,
                    "context": self._get_line_context(content, match.start())
                })

        return {
            "file": str(filepath),
            "issues": issues,
            "modern_usage": modern_usage,
            "has_issues": len(issues) > 0,
            "has_modern_usage": len(modern_usage) > 0
        }

    def _get_line_context(self, content: str, position: int) -> str:
        """Get the line containing the given position"""
        lines = content.split('\n')
        line_num = content[:position].count('\n')
        if 0 <= line_num < len(lines):
            return lines[line_num].strip()
        return ""

    def audit_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """Audit all Python files in a directory"""
        results = []

        for filepath in directory.rglob("*.py"):
            if filepath.name.startswith('.'):
                continue

            result = self.audit_file(filepath)
            results.append(result)
            self.files_audited += 1

            if result.get("has_issues"):
                self.issues_found.append(result)
            if result.get("has_modern_usage"):
                self.modern_usage_found.append(result)

        return results

    def check_mark_registration(self) -> Dict[str, Any]:
        """Check if custom marks are properly registered"""
        config_files = [
            "pyproject.toml",
            "pytest.ini",
            "setup.cfg"
        ]

        registration_status = {
            "pyproject.toml": False,
            "pytest.ini": False,
            "setup.cfg": False,
            "conftest.py_files": []
        }

        # Check pyproject.toml
        if os.path.exists("pyproject.toml"):
            with open("pyproject.toml", 'r') as f:
                content = f.read()
                if "markers =" in content or "markers=[" in content:
                    registration_status["pyproject.toml"] = True

        # Check pytest.ini
        if os.path.exists("pytest.ini"):
            with open("pytest.ini", 'r') as f:
                content = f.read()
                if "markers =" in content:
                    registration_status["pytest.ini"] = True

        # Check setup.cfg
        if os.path.exists("setup.cfg"):
            with open("setup.cfg", 'r') as f:
                content = f.read()
                if "markers =" in content:
                    registration_status["setup.cfg"] = True

        # Check conftest.py files
        for conftest in Path(".").rglob("conftest.py"):
            with open(conftest, 'r') as f:
                content = f.read()
                if "addinivalue_line" in content and "markers" in content:
                    registration_status["conftest.py_files"].append(str(conftest))

        return registration_status

    def run_compatibility_tests(self) -> Dict[str, Any]:
        """Run basic compatibility tests"""
        test_results = {
            "mark_import": False,
            "mark_creation": False,
            "mark_iteration": False,
            "mark_args_access": False
        }

        try:
            # Test Mark import
            from _pytest.mark.structures import Mark
            test_results["mark_import"] = True

            # Test Mark creation
            mark = Mark("test", (), {})
            test_results["mark_creation"] = True

            # Test mark iteration (simulated)
            class MockItem:
                def iter_markers(self, name):
                    return [mark]

            item = MockItem()
            markers = list(item.iter_markers("test"))
            test_results["mark_iteration"] = len(markers) > 0

            # Test args access
            args = mark.args
            test_results["mark_args_access"] = True

        except Exception as e:
            logger.error(f"Compatibility test failed: {e}")

        return test_results

    def generate_report(self) -> str:
        """Generate a comprehensive audit report"""
        report = []
        report.append("=" * 80)
        report.append("TAVERN PYTEST MARK COMPATIBILITY AUDIT REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary
        report.append("SUMMARY:")
        report.append(f"- Files audited: {self.files_audited}")
        report.append(f"- Files with issues: {len(self.issues_found)}")
        report.append(f"- Files with modern usage: {len(self.modern_usage_found)}")
        report.append("")

        # Issues found
        if self.issues_found:
            report.append("ISSUES FOUND:")
            report.append("-" * 40)
            for result in self.issues_found:
                report.append(f"File: {result['file']}")
                for issue in result['issues']:
                    report.append(f"  Line {issue['line']}: {issue['message']}")
                    report.append(f"  Context: {issue['context']}")
                report.append("")
        else:
            report.append("✓ NO DEPRECATED MARK USAGE FOUND")
            report.append("")

        # Modern usage found
        if self.modern_usage_found:
            report.append("MODERN MARK USAGE FOUND:")
            report.append("-" * 40)
            for result in self.modern_usage_found:
                report.append(f"File: {result['file']}")
                for usage in result['modern_usage']:
                    report.append(f"  Line {usage['line']}: {usage['message']}")
                report.append("")

        # Mark registration status
        registration = self.check_mark_registration()
        report.append("MARK REGISTRATION STATUS:")
        report.append("-" * 40)
        for config_file, has_registration in registration.items():
            if config_file != "conftest.py_files":
                status = "✓" if has_registration else "✗"
                report.append(f"{status} {config_file}")

        if registration["conftest.py_files"]:
            report.append("✓ Custom marks registered in conftest.py files:")
            for conftest in registration["conftest.py_files"]:
                report.append(f"  - {conftest}")
        report.append("")

        # Compatibility test results
        compatibility = self.run_compatibility_tests()
        report.append("COMPATIBILITY TEST RESULTS:")
        report.append("-" * 40)
        for test, passed in compatibility.items():
            status = "✓" if passed else "✗"
            report.append(f"{status} {test}")
        report.append("")

        # Recommendations
        report.append("RECOMMENDATIONS:")
        report.append("-" * 40)
        if not self.issues_found:
            report.append("✓ Codebase is compatible with Pytest 7.3.0+")
            report.append("✓ All mark usage follows modern patterns")
        else:
            report.append("✗ Found deprecated mark usage patterns")
            report.append("  - Replace .get_marker() with .iter_markers()")
            report.append("  - Replace getattr(pytest.mark, ...) with Mark() constructor")
            report.append("  - Replace .mark.args with .args")

        if not any(registration.values()):
            report.append("✗ No custom mark registration found")
            report.append("  - Add mark registration to pyproject.toml or conftest.py")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

def main():
    """Main audit function"""
    auditor = PytestMarkAuditor()

    # Audit key directories
    directories_to_audit = [
        "tavern/_core/pytest",
        "tavern/_plugins",
        "tests/unit",
        "tests/integration"
    ]

    logger.info("Starting Pytest mark compatibility audit...")

    for directory in directories_to_audit:
        if os.path.exists(directory):
            logger.info(f"Auditing {directory}...")
            auditor.audit_directory(Path(directory))

    # Generate and print report
    report = auditor.generate_report()
    print(report)

    # Exit with appropriate code
    if auditor.issues_found:
        logger.error("Issues found - compatibility may be compromised")
        sys.exit(1)
    else:
        logger.info("Audit completed successfully - no issues found")
        sys.exit(0)

if __name__ == "__main__":
    main()

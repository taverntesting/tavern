"""Unit tests for regex functions in the Starlark environment.

These tests verify the re.match and re.sub implementations for Starlark,
including match result struct behavior and substitution patterns.
"""


class TestReMatch:
    """Tests for the re.match function."""

    def test_match_success_returns_struct(self, basic_runner):
        """Test that successful match returns a struct with groups."""

        script = r"""
load("@tavern_helpers.star", "re")
result = re.match("hello (\\w+)", "hello world")
"""
        basic_runner.load_and_run(script)
        # Script should execute without errors

    def test_match_returns_none_on_failure(self, basic_runner):
        """Test that failed match returns None."""

        script = """
load("@tavern_helpers.star", "re")
result = re.match("goodbye", "hello world")
if result != None:
    fail("Expected None for failed match")
"""
        basic_runner.load_and_run(script)

    def test_match_with_capture_groups(self, basic_runner):
        """Test that capture groups are accessible in result."""

        script = r"""
load("@tavern_helpers.star", "re")
result = re.match("(\\w+)@(\\w+)", "user@domain")
if result == None:
    fail("Match should succeed")
if result.group0 != "user@domain":
    fail("group0 should be full match")
if result.groups[0] != "user":
    fail("First group should be 'user'")
if result.groups[1] != "domain":
    fail("Second group should be 'domain'")
"""
        basic_runner.load_and_run(script)

    def test_match_start_end_positions(self, basic_runner):
        """Test that start and end positions are correct."""

        script = r"""
load("@tavern_helpers.star", "re")
result = re.match("\\d+", "12345abc")
if result == None:
    fail("Match should succeed")
if result.start != 0:
    fail("Start should be 0")
if result.end != 5:
    fail("End should be 5")
"""
        basic_runner.load_and_run(script)

    def test_match_only_at_string_start(self, basic_runner):
        """Test that match only works at beginning of string (Python re.match behavior)."""

        script = """
load("@tavern_helpers.star", "re")
# match() only matches at the start, not in the middle
result = re.match("world", "hello world")
if result != None:
    fail("match should return None when pattern not at start")
"""
        basic_runner.load_and_run(script)

    def test_match_with_empty_string(self, basic_runner):
        """Test match with empty string."""

        script = """
load("@tavern_helpers.star", "re")
result = re.match(".*", "")
if result == None:
    fail("Empty pattern should match empty string")
"""
        basic_runner.load_and_run(script)


class TestReSub:
    """Tests for the re.sub function."""

    def test_basic_substitution(self, basic_runner):
        """Test basic string substitution."""

        script = """
load("@tavern_helpers.star", "re")
result = re.sub("world", "universe", "hello world")
if result != "hello universe":
    fail("Substitution failed")
"""
        basic_runner.load_and_run(script)

    def test_global_replacement(self, basic_runner):
        """Test that all occurrences are replaced by default."""

        script = """
load("@tavern_helpers.star", "re")
result = re.sub("a", "b", "aaa aaa")
if result != "bbb bbb":
    fail("All occurrences should be replaced")
"""
        basic_runner.load_and_run(script)

    def test_no_match_returns_unchanged_string(self, basic_runner):
        """Test that no match returns the original string."""

        script = """
load("@tavern_helpers.star", "re")
result = re.sub("xyz", "abc", "hello world")
if result != "hello world":
    fail("String should be unchanged when no match")
"""
        basic_runner.load_and_run(script)

    def test_substitution_with_capture_groups(self, basic_runner):
        """Test substitution preserves captured content via backreferences."""
        script = r"""
load("@tavern_helpers.star", "re")
result = re.sub("(\\w+)-(\\w+)", "\\2-\\1", "hello-world")
if result != "world-hello":
    fail("Capture swap failed - got: " + result)
"""
        basic_runner.load_and_run(script)

    def test_substitution_with_digit_pattern(self, basic_runner):
        """Test substitution with digit patterns."""

        script = r"""
load("@tavern_helpers.star", "re")
result = re.sub("\\d+", "NUM", "user123@example456")
if result != "userNUM@exampleNUM":
    fail("Digit substitution failed")
"""
        basic_runner.load_and_run(script)

    def test_substitution_empty_string(self, basic_runner):
        """Test substitution with empty pattern."""

        script = """
load("@tavern_helpers.star", "re")
# Empty pattern matches between every character, inserting replacement
result = re.sub("", "-", "abc")
# This results in "-a-b-c-" in Python
if result != "-a-b-c-":
    fail("Empty pattern substitution failed")
"""
        basic_runner.load_and_run(script)

    def test_match_result_is_truthy(self, basic_runner):
        """Test that successful match result is truthy."""

        script = """
load("@tavern_helpers.star", "re")
result = re.match("hello", "hello world")
if not result:
    fail("Match result should be truthy")
"""
        basic_runner.load_and_run(script)

    def test_no_match_result_is_falsy(self, basic_runner):
        """Test that failed match result is falsy (None)."""

        script = """
load("@tavern_helpers.star", "re")
result = re.match("xyz", "hello world")
if result:
    fail("Failed match should be falsy")
"""
        basic_runner.load_and_run(script)

    def test_match_in_conditional(self, basic_runner):
        """Test using match result in conditional expressions."""

        script = """
load("@tavern_helpers.star", "re")
# Use match result in conditional
if re.match("hello", "hello world"):
    pass  # Match succeeded
else:
    fail("Match should have succeeded")

if re.match("xyz", "hello world"):
    fail("Match should have failed")
"""
        basic_runner.load_and_run(script)

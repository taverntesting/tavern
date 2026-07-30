import pytest

from tavern._core.starlark.diagram import build_mermaid, escape_label, stage_summary


@pytest.fixture
def stages():
    return {
        "get_cookie": {
            "id": "get_cookie",
            "name": "Get cookie",
            "request": {"url": "{global_host}/get_cookie", "method": "POST"},
        },
        "echo_value": {
            "id": "echo_value",
            "name": "Echo a value",
            "request": {"url": "{global_host}/echo", "method": "POST"},
        },
        "polling": {
            "id": "polling",
            "name": "polling",
            "request": {"url": "{global_host}/poll", "method": "GET"},
        },
        "publish": {
            "id": "publish",
            "name": "Publish something",
            "mqtt_publish": {"topic": "/a/topic"},
        },
        "no_request": {"id": "no_request", "name": "Just a name"},
    }


class TestStageSummary:
    def test_http_stage_shows_method_and_url(self, stages):
        assert (
            stage_summary(stages["get_cookie"])
            == "Get cookie\nPOST {global_host}/get_cookie"
        )

    def test_non_http_stage_shows_request_type(self, stages):
        assert stage_summary(stages["publish"]) == "Publish something\nmqtt publish"

    def test_stage_with_no_request_is_just_the_name(self, stages):
        assert stage_summary(stages["no_request"]) == "Just a name"

    def test_falls_back_to_id(self):
        assert stage_summary({"id": "an_id"}) == "an_id"


class TestEscaping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ('say "hi"', "say #quot;hi#quot;"),
            ("a < b > c", "a #lt; b #gt; c"),
            ("issue #1", "issue #35;1"),
            ("one\ntwo", "one<br/>two"),
        ],
    )
    def test_escapes(self, raw, expected):
        assert escape_label(raw) == expected

    def test_long_lines_are_truncated(self):
        escaped = escape_label("x" * 200)
        assert len(escaped) < 200
        assert escaped.endswith("…")


class TestBuildMermaid:
    def test_starts_with_flowchart_header(self, stages):
        diagram = build_mermaid('run_stage("get_cookie")', stages)
        assert diagram.splitlines()[0] == "flowchart TD"

    def test_sequential_stages(self, stages):
        script = """
load("@tavern_helpers.star", "run_stage")

resp = run_stage("get_cookie")
resp = run_stage("echo_value")
"""
        diagram = build_mermaid(script, stages)

        assert "Get cookie<br/>POST {global_host}/get_cookie" in diagram
        assert "Echo a value<br/>POST {global_host}/echo" in diagram
        assert "start --> s1" in diagram
        assert "s1 --> s2" in diagram
        assert "s2 --> finish" in diagram

    def test_load_and_log_are_not_rendered(self, stages):
        script = """
load("@tavern_helpers.star", "run_stage")
log("hello")
run_stage("get_cookie")
"""
        diagram = build_mermaid(script, stages)

        assert "hello" not in diagram
        assert "tavern_helpers" not in diagram

    def test_if_else_branches(self, stages):
        script = """
resp = run_stage("get_cookie")
if resp.failed:
    run_stage("echo_value")
else:
    run_stage("polling")
"""
        diagram = build_mermaid(script, stages)

        assert 'c2{"resp.failed"}' in diagram
        assert "c2 -->|yes| s3" in diagram
        assert "c2 -->|no| s4" in diagram

    def test_if_with_no_else_still_has_a_no_branch(self, stages):
        script = """
if run_stage("get_cookie").failed:
    run_stage("echo_value")
run_stage("polling")
"""
        diagram = build_mermaid(script, stages)

        assert "c2 -->|yes| s3" in diagram
        assert "c2 -->|no| s4" in diagram

    def test_run_stage_in_condition_is_rendered_before_the_decision(self, stages):
        diagram = build_mermaid(
            'if run_stage("get_cookie").failed:\n    fail("no")', stages
        )

        assert "start --> s1" in diagram
        assert "s1 --> c2" in diagram

    def test_continue_on_fail_is_annotated(self, stages):
        diagram = build_mermaid('run_stage("polling", continue_on_fail=True)', stages)

        assert "(continue_on_fail)" in diagram

    def test_continue_on_fail_false_is_not_annotated(self, stages):
        diagram = build_mermaid('run_stage("polling", continue_on_fail=False)', stages)

        assert "(continue_on_fail)" not in diagram

    def test_fail_is_terminal(self, stages):
        script = """
resp = run_stage("get_cookie")
if resp.failed:
    fail("it broke")
run_stage("echo_value")
"""
        diagram = build_mermaid(script, stages)

        assert 'f3[["fail: it broke"]]' in diagram
        # The fail node has no outgoing edge
        assert "f3 -->" not in diagram

    def test_retry_loop_with_break(self, stages):
        script = """
succeeded = False
for i in range(0, 3):
    resp = run_stage("polling", continue_on_fail=True)
    if not resp.failed:
        succeeded = True
        break
    time.sleep(1)

if not succeeded:
    fail("polling did not succeed")
"""
        diagram = build_mermaid(script, stages)

        assert 'l1{"for i in range(0, 3)"}' in diagram
        assert "l1 -->|each| s2" in diagram
        # sleep is part of the flow
        assert 't4("sleep 1")' in diagram
        # back edge to the top of the loop
        assert "t4 -->|loop| l1" in diagram
        # break jumps past the loop, as does falling off the end of it
        assert "l1 -->|done| c5" in diagram
        assert "c3 -->|yes| c5" in diagram

    def test_continue_goes_back_to_the_loop_head(self, stages):
        script = """
for i in range(0, 3):
    if i == 1:
        continue
    run_stage("polling")
"""
        diagram = build_mermaid(script, stages)

        assert "c2 -->|yes| l1" in diagram

    def test_while_loop(self, stages):
        diagram = build_mermaid('while True:\n    run_stage("polling")', stages)

        assert 'l1{"while True"}' in diagram

    def test_unknown_stage_id_is_flagged(self, stages):
        diagram = build_mermaid('run_stage("not_a_real_stage")', stages)

        assert "unknown stage 'not_a_real_stage'" in diagram
        assert ":::unknownStage" in diagram
        assert "classDef unknownStage" in diagram

    def test_known_stages_have_no_classdefs(self, stages):
        diagram = build_mermaid('run_stage("get_cookie")', stages)

        assert "classDef" not in diagram

    def test_dynamically_named_stage_is_flagged(self, stages):
        diagram = build_mermaid("run_stage(stage_name)", stages)

        assert "run_stage(stage_name)" in diagram
        assert ":::dynamicStage" in diagram

    def test_local_function_is_rendered_as_a_subgraph(self, stages):
        script = """
def check():
    run_stage("echo_value")

run_stage("get_cookie")
check()
"""
        diagram = build_mermaid(script, stages)

        assert 'subgraph sg_check["def check()"]' in diagram
        assert "end" in diagram.splitlines()[-1] or "end" in diagram
        # dashed edge from the call node into the function
        assert "-.->" in diagram
        assert "Echo a value" in diagram

    def test_recursive_function_does_not_hang(self, stages):
        script = """
def loop_forever():
    run_stage("polling")
    loop_forever()

loop_forever()
"""
        diagram = build_mermaid(script, stages)

        assert 'subgraph sg_loop_forever["def loop_forever()"]' in diagram

    def test_syntax_error_returns_an_error_node(self, stages):
        diagram = build_mermaid("this is not valid at all !!", stages)

        assert diagram.startswith("flowchart TD")
        assert "could not parse script" in diagram
        assert ":::scriptError" in diagram

    def test_labels_with_quotes_are_escaped(self, stages):
        diagram = build_mermaid(
            're.search("v(\\\\d+)\\\\.", body)\nfail("bad \\"thing\\"")', stages
        )

        assert "#quot;" in diagram
        # no unescaped quotes inside a label
        for line in diagram.splitlines():
            stripped = line.strip()
            if stripped.startswith("f") and '"' in stripped:
                assert stripped.count('"') == 2

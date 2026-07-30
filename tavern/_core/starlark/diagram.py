"""Render a mermaid flowchart from a 'control_flow' Starlark script.

This is a purely static analysis of the script - nothing is executed and no
requests are made. It exists so that users can see the shape of a
``control_flow`` script (which branches exist, which stages each one runs,
where the loops are) without having to mentally simulate it.

Starlark is a syntactic subset of Python, so the script is parsed with the
stdlib :mod:`ast` module. ``starlark-pyo3`` returns an opaque AST object which
cannot be walked from Python, and this also means this module works fine
without the optional ``scriptable`` extra installed.

Because this is static, every branch is rendered - unlike a traced run, which
would only ever show one path through the script.
"""

import ast
import logging
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# Anything longer than this in a node label gets truncated
_MAX_LABEL_LEN = 80

_UNKNOWN_CLASS = "unknownStage"
_DYNAMIC_CLASS = "dynamicStage"
_ERROR_CLASS = "scriptError"

_CLASS_DEFS = {
    _UNKNOWN_CLASS: "classDef unknownStage fill:#ffd9d9,stroke:#cc3333,stroke-width:2px;",
    _DYNAMIC_CLASS: "classDef dynamicStage fill:#fff4d6,stroke:#cc9933,stroke-width:2px;",
    _ERROR_CLASS: "classDef scriptError fill:#ffd9d9,stroke:#cc3333,stroke-width:2px;",
}

# Keys a stage can use to describe its request. Only 'request' (http) has a
# useful one line summary, the rest are just used to say what kind of stage it
# is.
_REQUEST_KEYS = {
    "request": None,
    "mqtt_publish": "mqtt publish",
    "grpc_request": "grpc request",
    "graphql_request": "graphql request",
}


def escape_label(text: str) -> str:
    """Escape a string so it can be used inside a quoted mermaid node label.

    Mermaid renders label contents as HTML, so angle brackets and quotes have
    to be replaced with entities. '#' is escaped first because it is the entity
    escape character itself.

    Args:
        text: raw text, possibly containing newlines

    Returns:
        the escaped text, with newlines turned into '<br/>'
    """
    lines = []
    for line in text.splitlines() or [""]:
        if len(line) > _MAX_LABEL_LEN:
            line = line[: _MAX_LABEL_LEN - 1] + "…"
        line = (
            line.replace("#", "#35;")
            .replace('"', "#quot;")
            .replace("<", "#lt;")
            .replace(">", "#gt;")
        )
        lines.append(line)

    return "<br/>".join(lines)


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - ast.unparse is very forgiving
        return "<expression>"


def stage_summary(stage: dict[str, Any]) -> str:
    """One or two line human readable summary of a stage, for use as a node label

    Args:
        stage: the stage dict from the test spec

    Returns:
        the stage name, followed by the request method and url if it is a HTTP
        stage. Note that the url is _not_ formatted, as variables are not
        resolved when this runs.
    """
    name = stage.get("name") or stage.get("id") or "unnamed stage"

    for key, description in _REQUEST_KEYS.items():
        block = stage.get(key)
        if not isinstance(block, dict):
            continue

        if key == "request":
            method = block.get("method", "GET")
            url = block.get("url", "")
            return f"{name}\n{method} {url}".strip()

        return f"{name}\n{description}"

    return name


class _LoopContext:
    """Tracks where 'break' and 'continue' should jump to"""

    def __init__(self, head: str) -> None:
        self.head = head
        self.breaks: list[tuple[str, str | None]] = []


class _MermaidBuilder:
    """Walks a parsed script and accumulates mermaid nodes/edges

    'Pending' edges are the dangling ends of the flow so far - a list of
    (node id, edge label) which the next node should be connected to. A branch
    doubles the number of pending edges, a 'fail()' removes them.
    """

    def __init__(self, stages_by_id: dict[str, dict]) -> None:
        self._stages_by_id = stages_by_id
        self._counter = 0
        self._lines: list[str] = []
        self._subgraph_lines: list[str] = []
        self._used_classes: set[str] = set()
        self._loops: list[_LoopContext] = []
        self._functions: dict[str, ast.FunctionDef] = {}
        # name -> entry node id of an already rendered function subgraph
        self._rendered_functions: dict[str, str] = {}
        self._rendering: set[str] = set()
        # Return statements encountered while rendering a function body
        self._returns: list[tuple[str, str | None]] | None = None

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _node(
        self,
        node_id: str,
        shape: tuple[str, str],
        label: str,
        cls: str | None = None,
    ) -> None:
        """Add a node, where 'shape' is the mermaid brackets to wrap the label in"""
        opening, closing = shape
        line = f'{node_id}{opening}"{escape_label(label)}"{closing}'
        if cls:
            line += f":::{cls}"
            self._used_classes.add(cls)
        self._lines.append(line)

    def _edge(
        self,
        pending: list[tuple[str, str | None]],
        dest: str,
        *,
        dashed: bool = False,
    ) -> None:
        arrow = "-.->" if dashed else "-->"
        for src, label in pending:
            if label:
                self._lines.append(f"{src} {arrow}|{escape_label(label)}| {dest}")
            else:
                self._lines.append(f"{src} {arrow} {dest}")

    # Statement handling

    def visit_body(
        self, stmts: list[ast.stmt], pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        for stmt in stmts:
            pending = self.visit_stmt(stmt, pending)
            if not pending:
                # Flow stopped (fail/break/continue/return) - anything after
                # this in the same block is unreachable
                break

        return pending

    def visit_stmt(
        self, stmt: ast.stmt, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        if isinstance(stmt, ast.FunctionDef):
            self._functions[stmt.name] = stmt
            return pending

        if isinstance(stmt, ast.If):
            return self._visit_if(stmt, pending)

        if isinstance(stmt, ast.For):
            return self._visit_loop(
                stmt,
                f"for {_unparse(stmt.target)} in {_unparse(stmt.iter)}",
                stmt.iter,
                pending,
            )

        if isinstance(stmt, ast.While):
            return self._visit_loop(
                stmt, f"while {_unparse(stmt.test)}", stmt.test, pending
            )

        if isinstance(stmt, ast.Break):
            if self._loops:
                self._loops[-1].breaks.extend(pending)
            return []

        if isinstance(stmt, ast.Continue):
            if self._loops:
                self._edge(pending, self._loops[-1].head)
            return []

        if isinstance(stmt, ast.Return):
            if stmt.value is not None:
                pending = self._visit_expr(stmt.value, pending)
            if self._returns is not None:
                self._returns.extend(pending)
            return []

        # Everything else (assignments, bare calls, load(), pass) is only
        # interesting for the calls it contains
        for expr in _expressions_in(stmt):
            pending = self._visit_expr(expr, pending)

        return pending

    def _visit_if(
        self, stmt: ast.If, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        pending = self._visit_expr(stmt.test, pending)

        decision = self._next_id("c")
        self._node(decision, ("{", "}"), _unparse(stmt.test))
        self._edge(pending, decision)

        after = self.visit_body(stmt.body, [(decision, "yes")])

        if stmt.orelse:
            after += self.visit_body(stmt.orelse, [(decision, "no")])
        else:
            after += [(decision, "no")]

        return after

    def _visit_loop(
        self,
        stmt: ast.For | ast.While,
        label: str,
        header_expr: ast.expr,
        pending: list[tuple[str, str | None]],
    ) -> list[tuple[str, str | None]]:
        pending = self._visit_expr(header_expr, pending)

        head = self._next_id("l")
        self._node(head, ("{", "}"), label)
        self._edge(pending, head)

        context = _LoopContext(head)
        self._loops.append(context)
        try:
            body_end = self.visit_body(stmt.body, [(head, "each")])
        finally:
            self._loops.pop()

        # Back edge to the top of the loop, keeping any branch label so it's
        # clear which way round a decision loops
        self._edge([(node_id, label or "loop") for node_id, label in body_end], head)

        return [(head, "done")] + context.breaks

    # Expression handling

    def _visit_expr(
        self, expr: ast.expr, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        """Emit nodes for any 'interesting' calls in an expression

        This means a call in an 'if' condition or on the right hand side of an
        assignment gets a node in the right place in the flow.
        """
        calls = [n for n in ast.walk(expr) if isinstance(n, ast.Call)]
        calls.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))

        for call in calls:
            name = _called_name(call)

            if name == "run_stage":
                pending = self._run_stage_node(call, pending)
            elif name == "fail":
                pending = self._fail_node(call, pending)
            elif name in ("time.sleep", "sleep"):
                pending = self._sleep_node(call, pending)
            elif name in self._functions:
                pending = self._function_call_node(name, pending)

        return pending

    def _run_stage_node(
        self, call: ast.Call, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        node_id = self._next_id("s")
        cls = None

        if call.args and isinstance(call.args[0], ast.Constant):
            stage_id = str(call.args[0].value)
            stage = self._stages_by_id.get(stage_id)
            if stage is None:
                label = f"unknown stage '{stage_id}'"
                cls = _UNKNOWN_CLASS
            else:
                label = stage_summary(stage)
        elif call.args:
            label = f"run_stage({_unparse(call.args[0])})"
            cls = _DYNAMIC_CLASS
        else:
            label = "run_stage()"
            cls = _DYNAMIC_CLASS

        if _keyword_is_true(call, "continue_on_fail"):
            label += "\n(continue_on_fail)"

        self._node(node_id, ("[", "]"), label, cls)
        self._edge(pending, node_id)

        return [(node_id, None)]

    def _fail_node(
        self, call: ast.Call, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        node_id = self._next_id("f")

        if call.args:
            if isinstance(call.args[0], ast.Constant):
                message = str(call.args[0].value)
            else:
                message = _unparse(call.args[0])
            label = f"fail: {message}"
        else:
            label = "fail"

        self._node(node_id, ("[[", "]]"), label)
        self._edge(pending, node_id)

        # fail() ends the test
        return []

    def _sleep_node(
        self, call: ast.Call, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        node_id = self._next_id("t")
        args = ", ".join(_unparse(a) for a in call.args)
        self._node(node_id, ("(", ")"), f"sleep {args}")
        self._edge(pending, node_id)

        return [(node_id, None)]

    def _function_call_node(
        self, name: str, pending: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        node_id = self._next_id("n")
        self._node(node_id, ("[/", "/]"), f"{name}()")
        self._edge(pending, node_id)

        entry = self._render_function(name)
        if entry:
            self._edge([(node_id, None)], entry, dashed=True)

        return [(node_id, None)]

    def _render_function(self, name: str) -> str | None:
        """Render a locally defined function as its own subgraph, once

        Returns:
            the id of the function's entry node, or None if it is being
            rendered already (i.e. it is recursive)
        """
        if name in self._rendered_functions:
            return self._rendered_functions[name]
        if name in self._rendering:
            return None

        definition = self._functions[name]

        self._rendering.add(name)
        outer_lines, outer_returns, outer_loops = (
            self._lines,
            self._returns,
            self._loops,
        )
        self._lines, self._returns, self._loops = [], [], []

        try:
            entry = self._next_id("e")
            self._node(entry, ("([", "])"), f"def {name}()")
            self._rendered_functions[name] = entry

            self.visit_body(definition.body, [(entry, None)])

            body_lines = self._lines
        finally:
            self._lines, self._returns, self._loops = (
                outer_lines,
                outer_returns,
                outer_loops,
            )
            self._rendering.discard(name)

        subgraph_id = f"sg_{name}"
        self._subgraph_lines.append(f'subgraph {subgraph_id}["def {name}()"]')
        self._subgraph_lines.extend(f"  {line}" for line in body_lines)
        self._subgraph_lines.append("end")

        return entry

    # Output

    def render(self, tree: ast.Module) -> str:
        start = "start"
        self._node(start, ("([", "])"), "start")

        # Register functions up front so they can be called before they are
        # defined in the script
        for stmt in tree.body:
            if isinstance(stmt, ast.FunctionDef):
                self._functions[stmt.name] = stmt

        pending = self.visit_body(tree.body, [(start, None)])

        if pending:
            end = "finish"
            self._node(end, ("([", "])"), "end")
            self._edge(pending, end)

        lines = ["flowchart TD"]
        lines += [f"  {line}" for line in self._lines]
        lines += [f"  {line}" for line in self._subgraph_lines]
        lines += [f"  {_CLASS_DEFS[c]}" for c in sorted(self._used_classes)]

        return "\n".join(lines)


def _expressions_in(stmt: ast.stmt) -> list[ast.expr]:
    """Top level expressions of a statement which might contain calls"""
    if isinstance(stmt, ast.Expr):
        return [stmt.value]
    if isinstance(stmt, ast.Assign):
        return [stmt.value]
    if isinstance(stmt, ast.AugAssign):
        return [stmt.value]
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return [stmt.value]
    return []


def _called_name(call: ast.Call) -> str | None:
    """Dotted name of the thing being called, if it is a plain name/attribute"""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def _keyword_is_true(call: ast.Call, name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return bool(keyword.value.value)
    return False


def build_mermaid(script: str, stages_by_id: dict[str, dict]) -> str:
    """Build a mermaid flowchart for a control_flow script

    Args:
        script: the contents of the 'control_flow' key
        stages_by_id: mapping of stage id to stage, used to label the nodes and
            to flag stage ids which do not exist

    Returns:
        a mermaid 'flowchart TD' definition. If the script cannot be parsed a
        single error node is returned rather than raising - this is a
        diagnostic tool and should never break a test run.
    """
    try:
        tree = ast.parse(script)
    except SyntaxError as e:
        logger.warning("Could not parse control_flow script: %s", e)
        message = f"could not parse script: {e.msg} (line {e.lineno})"
        return "\n".join(
            [
                "flowchart TD",
                f'  err["{escape_label(message)}"]:::{_ERROR_CLASS}',
                f"  {_CLASS_DEFS[_ERROR_CLASS]}",
            ]
        )

    return _MermaidBuilder(stages_by_id).render(tree)

"""Implementation of the --tavern-what-would-happen flag

Rather than running a test with a 'control_flow' script, build a mermaid
flowchart of what the script _would_ do and print it at the end of the run.
Nothing is executed and no sessions are opened.
"""

import logging
import pathlib
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import pytest

from tavern._core.dict_util import get_tavern_box

from .config import TestConfig
from .util import get_option_generic

if TYPE_CHECKING:
    from .item import YamlItem

logger: logging.Logger = logging.getLogger(__name__)

# nodeid -> mermaid flowchart
diagrams_key = pytest.StashKey[dict[str, str]]()


def enabled(config: pytest.Config) -> bool:
    """Whether --tavern-what-would-happen (or the equivalent ini option) was passed"""
    try:
        return bool(get_option_generic(config, "tavern-what-would-happen", False))
    except ValueError:
        # Option not registered, eg when tavern is used as a library
        return False


def _output_dir(config: pytest.Config) -> pathlib.Path | None:
    directory = get_option_generic(config, "tavern-what-would-happen-dir", None)
    if not directory:
        return None
    return pathlib.Path(directory)


def _slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "test"


def stages_by_id(test_spec: Mapping, global_cfg: TestConfig) -> dict[str, dict]:
    """All stages a control_flow script could refer to, keyed by id

    This mirrors what run_test passes to the StarlarkPipelineRunner - stages
    defined in the test itself, stages from global config, and stages from
    any '!include'd files.

    Args:
        test_spec: the test being described
        global_cfg: global config, which holds any globally defined stages

    Returns:
        mapping of stage id to stage
    """
    # Local import to avoid a circular dependency at import time
    from tavern._core.run import _get_included_stages

    available_stages: list[dict] = list(global_cfg.stages)

    try:
        included_stages = _get_included_stages(
            get_tavern_box(),
            global_cfg.with_new_variables(),
            test_spec,
            available_stages,
        )
    except Exception as e:
        logger.warning("Could not resolve included stages: %s", e)
        included_stages = []

    all_stages: list[dict[str, Any]] = (
        available_stages + included_stages + list(test_spec.get("stages", []))
    )

    return {s["id"]: s for s in all_stages if isinstance(s, dict) and s.get("id")}


def record(item: "YamlItem") -> None:
    """Build the diagram for a test and stash it for the terminal summary

    Args:
        item: the test item, which is not going to be run
    """
    # Local import to avoid a circular dependency at import time
    from tavern._core.starlark.diagram import build_mermaid

    diagram = build_mermaid(
        item.spec["control_flow"], stages_by_id(item.spec, item.global_cfg)
    )

    stash = item.config.stash.setdefault(diagrams_key, {})
    stash[item.nodeid] = diagram

    directory = _output_dir(item.config)
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{item.path.name.split('.')[0]}.{_slugify(item.name)}.mmd"
        (directory / filename).write_text(diagram + "\n")
        logger.debug("Wrote diagram to %s", directory / filename)


def print_summary(config: pytest.Config, terminalreporter) -> None:
    """Print all the diagrams collected during the run"""
    diagrams = config.stash.get(diagrams_key, None)
    if not diagrams:
        return

    terminalreporter.write_sep("=", "what would happen")

    for nodeid, diagram in diagrams.items():
        terminalreporter.write_line("")
        terminalreporter.write_line(f"### {nodeid}")
        terminalreporter.write_line("")
        terminalreporter.write_line("```mermaid")
        for line in diagram.splitlines():
            terminalreporter.write_line(line)
        terminalreporter.write_line("```")

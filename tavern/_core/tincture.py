import collections.abc
import dataclasses
import inspect
import logging
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from tavern._core import exceptions
from tavern._core.extfunctions import get_wrapped_response_function

if TYPE_CHECKING:
    from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Tinctures:
    tinctures: list[Any]
    needs_response: list[Generator[None, tuple[Any, Any], None]] = dataclasses.field(
        default_factory=list
    )
    # Global tinctures that persist across stages (initialized once per test)
    global_tinctures: list[Any] = dataclasses.field(default_factory=list)
    global_needs_response: list[Generator[None, tuple[Any, Any], None]] = (
        dataclasses.field(default_factory=list)
    )

    def start_tinctures(self, stage: collections.abc.Mapping) -> None:
        results = [t(stage) for t in self.tinctures]

        for r in results:
            if inspect.isgenerator(r):
                # Store generator and start it
                self.needs_response.append(r)
                next(r)

    def end_tinctures(self, expected: collections.abc.Mapping, response) -> None:
        """
        Send the response object to any tinctures that want it

        Args:
            expected: 'expected' from initial test - type varies depending on backend
            response: The response from 'run' for the stage - type varies depending on backend

        Raises:
            exceptions.TinctureError: If a tincture yields more than once
        """
        if self.needs_response is None:
            raise RuntimeError(
                "should not be called before accumulating tinctures which need a response"
            )

        for n in self.needs_response:
            try:
                n.send((expected, response))
            except StopIteration:
                pass
            else:
                raise exceptions.TinctureError("Tincture had more than one yield")

    def start_global_tinctures(self, stage: collections.abc.Mapping) -> None:
        """Start global tinctures that persist across stages.

        This is called once at the start of the test to initialize global tinctures.
        For generator-based global tinctures, they are started and stored for later use.

        Args:
            stage: Stage dictionary (passed to each global tincture)
        """
        results = [t(stage) for t in self.global_tinctures]

        for r in results:
            if inspect.isgenerator(r):
                # Store generator and start it
                self.global_needs_response.append(r)
                next(r)

    def call_global_tinctures(self, stage: collections.abc.Mapping) -> None:
        """Call global tinctures before each stage.

        This is called at the start of each stage to run global tinctures.
        For non-generator global tinctures, they are called directly.
        For generator-based global tinctures that were started in start_global_tinctures,
        they receive the stage via send().

        Args:
            stage: Stage dictionary (passed to each global tincture)
        """
        # Call non-generator global tinctures directly
        for t in self.global_tinctures:
            if not inspect.isgenerator(t):
                # Regular function - call it with stage
                t(stage)

        # Send stage to generator-based global tinctures that were already started
        for g in self.global_needs_response:
            try:
                g.send(stage)
            except StopIteration:
                pass

    def end_global_tinctures(self, expected: collections.abc.Mapping, response) -> None:
        """Send response to global tinctures that need it.

        This is called at the end of each stage to send the response to
        generator-based global tinctures.

        Args:
            expected: 'expected' from initial test - type varies depending on backend
            response: The response from 'run' for the stage - type varies depending on backend

        Raises:
            exceptions.TinctureError: If a tincture yields more than once
        """
        for n in self.global_needs_response:
            try:
                n.send((expected, response))
            except StopIteration:
                pass
            else:
                raise exceptions.TinctureError(
                    "Global tincture had more than one yield"
                )


def get_stage_tinctures(
    stage: collections.abc.Mapping,
    test_spec: collections.abc.Mapping,
    global_cfg: "TestConfig | None" = None,
) -> Tinctures:
    """Get tinctures for stage

    Note: Global tinctures are now handled separately via get_global_tinctures().
    This function only returns test-level and stage-level tinctures.

    Args:
        stage: Stage
        test_spec: Whole test spec
        global_cfg: Global configuration (optional, deprecated - use get_global_tinctures)

    Returns:
        Tinctures: List of tinctures for the stage
    """
    stage_tinctures = []

    def add_tinctures_from_block(maybe_tinctures, blockname: str):
        logger.debug("Trying to add tinctures from %s", blockname)

        def inner_yield():
            if maybe_tinctures is not None:
                if isinstance(maybe_tinctures, list):
                    for vf in maybe_tinctures:
                        yield get_wrapped_response_function(vf)
                elif isinstance(maybe_tinctures, dict):
                    yield get_wrapped_response_function(maybe_tinctures)
                elif maybe_tinctures is not None:
                    raise exceptions.BadSchemaError(
                        f"Badly formatted 'tinctures' block in {blockname}"
                    )

        stage_tinctures.extend(inner_yield())

    add_tinctures_from_block(test_spec.get("tinctures"), "test")
    add_tinctures_from_block(stage.get("tinctures"), "stage")

    # Note: Global tinctures are now handled separately via get_global_tinctures()
    # to allow them to persist across stages

    logger.debug("%d tinctures for stage %s", len(stage_tinctures), stage["name"])

    return Tinctures(stage_tinctures)


def get_global_tinctures(global_cfg: "TestConfig | None") -> Tinctures:
    """Get global tinctures that persist across stages.

    Global tinctures are initialized once at the start of a test and are
    called before/after each stage. This allows them to track state across
    the entire test execution.

    Args:
        global_cfg: Global configuration containing global tinctures

    Returns:
        Tinctures: Tinctures object with only global tinctures initialized
    """
    global_tinctures_list = []

    if global_cfg is not None and global_cfg.tinctures is not None:
        maybe_tinctures = global_cfg.tinctures
        logger.debug("Loading global tinctures from global config")

        def inner_yield():
            if maybe_tinctures is not None:
                if isinstance(maybe_tinctures, list):
                    for vf in maybe_tinctures:
                        yield get_wrapped_response_function(vf)
                elif isinstance(maybe_tinctures, dict):
                    yield get_wrapped_response_function(maybe_tinctures)
                elif maybe_tinctures is not None:
                    raise exceptions.BadSchemaError(
                        "Badly formatted 'tinctures' block in global config"
                    )

        global_tinctures_list.extend(inner_yield())

    logger.debug(
        "%d global tinctures loaded",
        len(global_tinctures_list),
    )

    return Tinctures(tinctures=[], global_tinctures=global_tinctures_list)

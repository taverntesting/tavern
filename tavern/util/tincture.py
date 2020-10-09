import inspect
import logging

from tavern.util import exceptions
from tavern.util.extfunctions import get_wrapped_response_function

logger = logging.getLogger(__name__)


class TinctureProvider:
    def __init__(self, stage):
        self._tinctures = TinctureProvider._accumulate_tincture_funcs(stage)
        self._needs_response = []

    @staticmethod
    def _accumulate_tincture_funcs(stage):
        """
        Get tinctures from stage

        Args:
            stage (dict): Test stage
        """
        tinctures = stage.get("tinctures", None)

        if isinstance(tinctures, list):
            for vf in tinctures:
                yield get_wrapped_response_function(vf)
        elif isinstance(tinctures, dict):
            yield get_wrapped_response_function(tinctures)
        elif tinctures is not None:
            raise exceptions.BadSchemaError("Badly formatted 'tinctures' block")

    def start_tinctures(self, stage):
        results = [t(stage) for t in self._tinctures]

        for r in results:
            if inspect.isgenerator(r):
                # Store generator and start it
                self._needs_response.append(r)
                next(r)

    def end_tinctures(self, response):
        """
        Send the response object to any tinctures that want it

        Args:
            response (object): The response from 'run' for the stage
        """
        if self._needs_response is None:
            raise RuntimeError(
                "should not be called before accumulating tinctures which need a response"
            )

        for n in self._needs_response:
            try:
                n.send(response)
            except StopIteration:
                pass
            else:
                raise RuntimeError("Tincture had more than one yield")

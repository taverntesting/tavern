import inspect

from tavern.schemas.extensions import get_wrapped_response_function
from tavern.util import exceptions


class TinctureProvider:
    def __init__(self, stage):
        self._tinctures = TinctureProvider._accumulate_tincture_funcs(stage)
        self._needs_response = None

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

        self._needs_response = [r for r in results if inspect.isgenerator(r)]

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
            n.send(None)
            try:
                n.send(response)
            except StopIteration:
                pass
            else:
                raise RuntimeError("Tincture had more than one yield")

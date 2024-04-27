import contextlib
import copy
import logging
import os
import tempfile
from collections.abc import Mapping

import pykwalify
import yaml
from pykwalify import core

from tavern._core.exceptions import BadSchemaError
from tavern._core.loader import load_single_document_yaml
from tavern._core.plugins import load_plugins
from tavern._core.schema.jsonschema import verify_jsonschema

logger: logging.Logger = logging.getLogger(__name__)


class SchemaCache:
    """Caches loaded schemas"""

    def __init__(self) -> None:
        self._loaded: dict[str, dict] = {}

    def _load_base_schema(self, schema_filename):
        try:
            return self._loaded[schema_filename]
        except KeyError:
            self._loaded[schema_filename] = load_single_document_yaml(schema_filename)

            logger.debug("Loaded schema from %s", schema_filename)

            return self._loaded[schema_filename]

    def _load_schema_with_plugins(self, schema_filename: str) -> dict:
        mangled = f"{schema_filename}-plugins"

        try:
            return self._loaded[mangled]
        except KeyError:
            pass

        plugins = load_plugins()
        base_schema = copy.deepcopy(self._load_base_schema(schema_filename))

        logger.debug("Adding plugins to schema: %s", [p.name for p in plugins])

        for p in plugins:
            try:
                plugin_schema = p.plugin.schema
            except AttributeError:
                # Don't require a schema
                logger.debug("No schema defined for %s", p.name)
            else:
                base_schema["properties"].update(plugin_schema.get("properties", {}))

        self._loaded[mangled] = base_schema
        return self._loaded[mangled]

    def __call__(self, schema_filename: str, with_plugins: bool):
        """Load the schema file and cache it for future use

        Args:
            schema_filename: filename of schema
            with_plugins: Whether to load plugin schema into this schema as well

        Returns:
            loaded schema
        """

        if with_plugins:
            schema = self._load_schema_with_plugins(schema_filename)
        else:
            schema = self._load_base_schema(schema_filename)

        return schema


load_schema_file = SchemaCache()


def verify_pykwalify(to_verify, schema) -> None:
    """Verify a generic file against a given pykwalify schema
    Args:
        to_verify: Filename of source tests to check
        schema: Schema to verify against
    Raises:
        BadSchemaError: Schema did not match
    """
    logger.debug("Verifying %s against %s", to_verify, schema)

    here = os.path.dirname(os.path.abspath(__file__))
    extension_module_filename = os.path.join(here, "extensions.py")

    verifier = core.Core(
        source_data=to_verify,
        schema_data=schema,
        extensions=[extension_module_filename],
    )

    try:
        verifier.validate()
    except pykwalify.errors.PyKwalifyException as e:
        logger.exception("Error validating %s", to_verify)
        raise BadSchemaError() from e


@contextlib.contextmanager
def wrapfile(to_wrap):
    """Wrap a dictionary into a temporary yaml file

    Args:
        to_wrap: Dictionary to write to temporary file

    Yields:
        filename: name of temporary file object that will be destroyed at the end of the
            context manager
    """
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as wrapped_tmp:
        # put into a file
        dumped = yaml.dump(to_wrap, default_flow_style=False)
        wrapped_tmp.write(dumped.encode("utf8"))
        wrapped_tmp.close()

        try:
            yield wrapped_tmp.name
        finally:
            os.remove(wrapped_tmp.name)


def verify_tests(test_spec: Mapping, with_plugins: bool = True) -> None:
    """Verify that a specific test block is correct

    Todo:
        Load schema file once. Requires some caching of the file

    Args:
        test_spec: Test in dictionary form
        with_plugins: Whether to load plugin schema into this schema as well

    Raises:
        BadSchemaError: Schema did not match
    """
    here = os.path.dirname(os.path.abspath(__file__))

    schema_filename = os.path.join(here, "tests.jsonschema.yaml")
    schema = load_schema_file(schema_filename, with_plugins)

    verify_jsonschema(test_spec, schema)

import os
import copy
import tempfile
import functools
import logging
import contextlib

from future.utils import raise_from

import yaml
from pykwalify import core
import pykwalify
from tavern.util.exceptions import BadSchemaError
from tavern.plugins import load_plugins

from tavern.util.loader import IncludeLoader
core.yaml.safe_load = functools.partial(yaml.load, Loader=IncludeLoader)

logger = logging.getLogger(__name__)


class SchemaCache(object):
    """Caches loaded schemas"""

    def __init__(self):
        self._loaded = {}

    def _load_base_schema(self, schema_filename):
        try:
            return self._loaded[schema_filename]
        except KeyError:
            with open(schema_filename, "r") as sfile:
                self._loaded[schema_filename] = yaml.load(sfile.read())

            logger.debug("Loaded schema from %s", schema_filename)

            return self._loaded[schema_filename]

    def _load_schema_with_plugins(self, schema_filename):
        mangled = "{}-plugins".format(schema_filename)

        try:
            return self._loaded[mangled]
        except KeyError:
            plugins = load_plugins()
            base_schema = copy.deepcopy(self._load_base_schema(schema_filename))

            logger.debug("Adding plugins to schema: %s", plugins)

            for p in plugins:
                try:
                    plugin_schema = p.plugin.schema
                except AttributeError:
                    # Don't require a schema
                    logger.debug("No schema defined for %s", p.name)
                else:
                    base_schema["mapping"].update(plugin_schema.get("initialisation", {}))

            self._loaded[mangled] = base_schema
            return self._loaded[mangled]

    def __call__(self, schema_filename, with_plugins):
        """Load the schema file and cache it for future use

        Args:
            schema_filename (str): filename of schema
            with_plugins (bool): Whether to load plugin schema into this schema as well

        Returns:
            dict: loaded schema
        """

        if with_plugins:
            schema = self._load_schema_with_plugins(schema_filename)
        else:
            schema = self._load_base_schema(schema_filename)

        return schema


load_schema_file = SchemaCache()


def verify_generic(to_verify, schema):
    """Verify a generic file against a given schema file

    Args:
        to_verify (str): Filename of source tests to check
        schema (dict): Schema to verify against

    Raises:
        BadSchemaError: Schema did not match
    """
    logger.debug("Verifying %s against %s", to_verify, schema)

    here = os.path.dirname(os.path.abspath(__file__))
    extension_module_filename = os.path.join(here, "extensions.py")

    verifier = core.Core(
        source_file=to_verify,
        schema_data=schema,
        extensions=[extension_module_filename],
    )

    try:
        verifier.validate()
    except pykwalify.errors.PyKwalifyException as e:
        logger.exception("Error validating %s", to_verify)
        raise_from(BadSchemaError(), e)


@contextlib.contextmanager
def wrapfile(to_wrap):
    """Wrap a dictionary into a temporary yaml file

    Args:
        to_wrap (dict): Dictionary to write to temporary file

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


def verify_tests(test_spec, with_plugins=True):
    """Verify that a specific test block is correct

    Todo:
        Load schema file once. Requires some caching of the file

    Args:
        test_spec (dict): Test in dictionary form

    Raises:
        BadSchemaError: Schema did not match
    """
    here = os.path.dirname(os.path.abspath(__file__))

    schema_filename = os.path.join(here, "tests.schema.yaml")
    schema = load_schema_file(schema_filename, with_plugins)

    with wrapfile(test_spec) as test_tmp:
        verify_generic(test_tmp, schema)

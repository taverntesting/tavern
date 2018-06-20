import os
import tempfile
import functools
import logging
import contextlib

from future.utils import raise_from

import yaml
from pykwalify import core
import pykwalify
from tavern.util.exceptions import BadSchemaError
from tavern.plugins import load_schema_plugins

from tavern.util.loader import IncludeLoader
core.yaml.safe_load = functools.partial(yaml.load, Loader=IncludeLoader)

logger = logging.getLogger(__name__)


def verify_generic(to_verify, schema_filename):
    """Verify a generic file against a given schema file

    Args:
        to_verify (str): filename of file to check
        schema_filename (str): filename of schema

    Raises:
        BadSchemaError: Schema did not match
    """
    logger.debug("Verifying %s against %s", to_verify, schema_filename)

    here = os.path.dirname(os.path.abspath(__file__))
    extension_module_filename = os.path.join(here, "extensions.py")

    verifier = core.Core(
        to_verify,
        [schema_filename],
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

        yield wrapped_tmp.name

        os.remove(wrapped_tmp.name)


def verify_tests(test_spec, load_plugins=True):
    """Verify that a specific test block is correct

    Todo:
        Load schema file once. Requires some caching of the file

    Args:
        test_spec (dict): Test in dictionary form

    Raises:
        BadSchemaError: Schema did not match
    """
    with wrapfile(test_spec) as test_tmp:
        here = os.path.dirname(os.path.abspath(__file__))
        schema_filename = os.path.join(here, "tests.schema.yaml")

        if load_plugins:
            # TODO
            # cache this
            schema_with_plugins = load_schema_plugins(schema_filename)

            with wrapfile(schema_with_plugins) as schema_tmp:
                verify_generic(test_tmp, schema_tmp)
        else:
            verify_generic(test_tmp, schema_filename)

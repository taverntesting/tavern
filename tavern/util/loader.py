# https://gist.github.com/joshbode/569627ced3076931b02f

import logging
import uuid
import os.path
import pytest
from future.utils import raise_from

import yaml
from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.resolver import Resolver

from tavern.util.exceptions import BadSchemaError


logger = logging.getLogger(__name__)


def makeuuid(loader, node):
    # pylint: disable=unused-argument
    return str(uuid.uuid4())


class RememberComposer(Composer):

    """A composer that doesn't forget anchors across documents
    """

    def compose_document(self):
        # Drop the DOCUMENT-START event.
        self.get_event()

        # Compose the root node.
        node = self.compose_node(None, None)

        # Drop the DOCUMENT-END event.
        self.get_event()

        # If we don't drop the anchors here, then we can keep anchors across
        # documents.
        # self.anchors = {}

        return node


# pylint: disable=too-many-ancestors
class IncludeLoader(Reader, Scanner, Parser, RememberComposer, SafeConstructor, Resolver):
    """YAML Loader with `!include` constructor and which can remember anchors
    between documents"""

    def __init__(self, stream):
        """Initialise Loader."""

        # pylint: disable=non-parent-init-called

        try:
            self._root = os.path.split(stream.name)[0]
        except AttributeError:
            self._root = os.path.curdir

        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        RememberComposer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)


def construct_include(loader, node):
    """Include file referenced at node."""

    # pylint: disable=protected-access
    filename = os.path.abspath(os.path.join(
        loader._root, loader.construct_scalar(node)
    ))
    extension = os.path.splitext(filename)[1].lstrip('.')

    if extension not in ('yaml', 'yml'):
        raise BadSchemaError("Unknown filetype '{}'".format(filename))

    with open(filename, 'r') as f:
        return yaml.load(f, IncludeLoader)


IncludeLoader.add_constructor("!include", construct_include)
IncludeLoader.add_constructor("!uuid", makeuuid)


class TypeSentinel(yaml.YAMLObject):
    """This is a sentinel for expecting a type in a response. Any value
    associated with these is going to be ignored - these are only used as a
    'hint' to the validator that it should expect a specific type in the
    response.
    """
    yaml_loader = IncludeLoader

    @classmethod
    def from_yaml(cls, loader, node):
        return cls()

    def __str__(self):
        return "<Tavern YAML sentinel for {}>".format(self.constructor) # pylint: disable=no-member


class IntSentinel(TypeSentinel):
    yaml_tag = "!anyint"
    constructor = int

class FloatSentinel(TypeSentinel):
    yaml_tag = "!anyfloat"
    constructor = float

class StrSentinel(TypeSentinel):
    yaml_tag = "!anystr"
    constructor = str

class BoolSentinel(TypeSentinel):
    yaml_tag = "!anybool"
    constructor = bool

class AnythingSentinel(TypeSentinel):
    yaml_tag = "!anything"
    constructor = "anything"

    @classmethod
    def from_yaml(cls, loader, node):
        return ANYTHING

    @classmethod
    def to_yaml(cls, dumper, data):
        node = yaml.nodes.ScalarNode(cls.yaml_tag, "", style=cls.yaml_flow_style)
        return node


# One instance of this
ANYTHING = AnythingSentinel()


class TypeConvertToken(yaml.YAMLObject):
    """This is a sentinel for something that should be converted to a different
    type. The rough load order is:

    1. Test data is loaded for schema validation
    2. Test data is dumped again so that pykwalify can read it (the actual
        values don't matter at all at this point, because we're just checking
        that the structure is correct)
    3. Test data is loaded and formatted

    So this preserves the actual value that the type should be up until the
    point that it actually needs to be formatted
    """
    yaml_loader = IncludeLoader

    def __init__(self, value):
        self.value = value

    @classmethod
    def from_yaml(cls, loader, node):
        value = loader.construct_scalar(node)

        try:
            # See if it's already a valid value (eg, if we do `!int "2"`)
            converted = cls.constructor(value) # pylint: disable=no-member
        except ValueError:
            # If not (eg, `!int "{int_value:d}"`)
            return cls(value)
        else:
            return converted

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.nodes.ScalarNode(cls.yaml_tag, data.value, style=cls.yaml_flow_style)


class IntToken(TypeConvertToken):
    yaml_tag = "!int"
    constructor = int


class FloatToken(TypeConvertToken):
    yaml_tag = "!float"
    constructor = float


class BoolToken(TypeConvertToken):
    yaml_tag = "!bool"
    constructor = bool


# Sort-of hack to try and avoid future API changes
ApproxScalar = type(pytest.approx(1.0))

class ApproxSentinel(yaml.YAMLObject, ApproxScalar):
    yaml_tag = "!approx"
    yaml_loader = IncludeLoader

    @classmethod
    def from_yaml(cls, loader, node):
        # pylint: disable=unused-argument
        try:
            val = float(node.value)
        except TypeError as e:
            logger.error("Could not coerce '%s' to a float for use with !approx", type(node.value))
            raise_from(BadSchemaError, e)

        return pytest.approx(val)

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.nodes.ScalarNode("!approx", str(data.expected), style=cls.yaml_flow_style)


# Apparently this isn't done automatically?
yaml.dumper.Dumper.add_representer(ApproxScalar, ApproxSentinel.to_yaml)

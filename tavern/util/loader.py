# https://gist.github.com/joshbode/569627ced3076931b02f

import uuid
import os.path

import yaml
from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.resolver import Resolver

from tavern.util.exceptions import BadSchemaError


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


class TypeSentinel(yaml.YAMLObject):
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

class AnythingSentinel(TypeSentinel):
    yaml_tag = "!anything"
    constructor = "anything"

    @classmethod
    def from_yaml(cls, loader, node):
        return ANYTHING


# One instance of this
ANYTHING = AnythingSentinel()


def represent_type_sentinel(sentinel_type):
    """Represent a type sentinel so it can be dumped in a format such that it
    can be read again later
    """

    def callback(representer, tag, style=None):
        # pylint: disable=unused-argument
        node = yaml.nodes.ScalarNode(sentinel_type.yaml_tag, "", style=style)
        return node

    return callback


# Could also just use a metaclass for this
yaml.representer.Representer.add_representer(AnythingSentinel, represent_type_sentinel)

IncludeLoader.add_constructor("!include", construct_include)
IncludeLoader.add_constructor("!uuid", makeuuid)


class TypeConvertToken(object):
    def __init__(self, value):
        self.value = value


class IntToken(TypeConvertToken):
    constructor = int


class FloatToken(TypeConvertToken):
    constructor = float


def construct_type_convert(sentinel_type):

    def callback(loader, node):
        value = loader.construct_scalar(node)
        return sentinel_type(value)

    return callback


yaml.loader.Loader.add_constructor("!int", construct_type_convert(IntSentinel))
yaml.loader.Loader.add_constructor("!float", construct_type_convert(FloatSentinel))

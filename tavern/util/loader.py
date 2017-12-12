# https://gist.github.com/joshbode/569627ced3076931b02f

import uuid
import os.path

from future.utils import with_metaclass

import yaml
from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.resolver import Resolver


def makeuuid(loader, node):
    # pylint: disable=unused-argument
    return str(uuid.uuid4())


class LoaderMeta(type):

    def __new__(mcs, name, bases, attrs):
        """Add include constructer to class."""

        # register the include constructor on the class
        cls = super(LoaderMeta, mcs).__new__(mcs, name, bases, attrs)
        cls.add_constructor('!include', cls.construct_include)
        cls.add_constructor('!uuid', makeuuid)

        return cls


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
class IncludeLoader(with_metaclass(LoaderMeta, Reader, Scanner, Parser, RememberComposer, SafeConstructor,
   Resolver)):
    """YAML Loader with `!include` constructor."""

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

    def construct_include(self, node):
        """Include file referenced at node."""

        filename = os.path.abspath(os.path.join(
            self._root, self.construct_scalar(node)
        ))
        extension = os.path.splitext(filename)[1].lstrip('.')

        if extension not in ('yaml', 'yml'):
            from tavern.util.exceptions import BadSchemaError
            raise BadSchemaError("Unknown filetype '{}'".format(filename))

        with open(filename, 'r') as f:
            return yaml.load(f, IncludeLoader)

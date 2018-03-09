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


class TypeConvertToken(object):
    def __init__(self, constructor, value):
        self.constructor = constructor
        self.value = value


def construct_type_convert(constructor):
    def callback(loader, node):
        value = loader.construct_scalar(node)
        return TypeConvertToken(constructor, value)
    return callback


ANYTHING = object()
def anything(loader, node):
    # pylint: disable=unused-argument
    return ANYTHING


class LoaderMeta(type):

    def __new__(mcs, name, bases, attrs):
        """Add include constructer to class."""

        # register the include constructor on the class
        cls = super(LoaderMeta, mcs).__new__(mcs, name, bases, attrs)
        cls.add_constructor('!include', cls.construct_include)
        cls.add_constructor('!uuid', makeuuid)
        cls.add_constructor('!int', construct_type_convert(int))
        cls.add_constructor('!float', construct_type_convert(float))
        cls.add_constructor('!anything', anything)

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


def create_node_class(cls):
    class node_class(cls):
        def __init__(self, x, start_mark, end_mark):
            cls.__init__(self, x)
            self.start_mark = start_mark
            self.end_mark = end_mark

        def __new__(self, x, start_mark, end_mark):
            return cls.__new__(self, x)
    node_class.__name__ = '%s_node' % cls.__name__
    return node_class

dict_node = create_node_class(dict)
list_node = create_node_class(list)

class SourceMappingConstructor(SafeConstructor):
    # To support lazy loading, the original constructors first yield
    # an empty object, then fill them in when iterated. Due to
    # laziness we omit this behaviour (and will only do "deep
    # construction") by first exhausting iterators, then yielding
    # copies.
    def construct_yaml_map(self, node):
        obj, = SafeConstructor.construct_yaml_map(self, node)
        return dict_node(obj, node.start_mark, node.end_mark)

    def construct_yaml_seq(self, node):
        obj, = SafeConstructor.construct_yaml_seq(self, node)
        return list_node(obj, node.start_mark, node.end_mark)


SourceMappingConstructor.add_constructor(
        u'tag:yaml.org,2002:map',
        SourceMappingConstructor.construct_yaml_map)

SourceMappingConstructor.add_constructor(
        u'tag:yaml.org,2002:seq',
        SourceMappingConstructor.construct_yaml_seq)

# pylint: disable=too-many-ancestors
class IncludeLoader(with_metaclass(LoaderMeta, Reader, Scanner, Parser, RememberComposer,
   Resolver, SourceMappingConstructor, SafeConstructor)):
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
        SourceMappingConstructor.__init__(self)

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

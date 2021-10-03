# https://gist.github.com/joshbode/569627ced3076931b02f
from abc import abstractmethod
from distutils.util import strtobool
from itertools import chain
import logging
import os.path
import re
import uuid

import pytest
import yaml
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.parser import Parser
from yaml.reader import Reader
from yaml.resolver import Resolver
from yaml.scanner import Scanner

from tavern._core import exceptions
from tavern._core.exceptions import BadSchemaError

logger = logging.getLogger(__name__)


def makeuuid(loader, node):
    # pylint: disable=unused-argument
    return str(uuid.uuid4())


class RememberComposer(Composer):
    """A composer that doesn't forget anchors across documents"""

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
    class node_class(cls):  # noqa
        def __init__(self, x, start_mark, end_mark):
            cls.__init__(self, x)
            self.start_mark = start_mark
            self.end_mark = end_mark

        # def __new__(self, x, start_mark, end_mark):
        #     return cls.__new__(self, x)

    node_class.__name__ = "%s_node" % cls.__name__
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
        (obj,) = SafeConstructor.construct_yaml_map(self, node)
        return dict_node(obj, node.start_mark, node.end_mark)

    def construct_yaml_seq(self, node):
        (obj,) = SafeConstructor.construct_yaml_seq(self, node)
        return list_node(obj, node.start_mark, node.end_mark)


SourceMappingConstructor.add_constructor(
    "tag:yaml.org,2002:map", SourceMappingConstructor.construct_yaml_map
)

SourceMappingConstructor.add_constructor(
    "tag:yaml.org,2002:seq", SourceMappingConstructor.construct_yaml_seq
)

yaml.add_representer(dict_node, yaml.representer.SafeRepresenter.represent_dict)
yaml.add_representer(list_node, yaml.representer.SafeRepresenter.represent_list)


# pylint: disable=too-many-ancestors
class IncludeLoader(
    Reader,
    Scanner,
    Parser,
    RememberComposer,
    Resolver,
    SourceMappingConstructor,
    SafeConstructor,
):
    """YAML Loader with `!include` constructor and which can remember anchors
    between documents"""

    def __init__(self, stream):
        """Initialise Loader."""

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

    env_path_list = None
    env_var_name = "TAVERN_INCLUDE"


def _get_include_dirs(loader):
    # pylint: disable=protected-access
    loader_list = [loader._root]

    if IncludeLoader.env_path_list is None:
        if IncludeLoader.env_var_name in os.environ:
            IncludeLoader.env_path_list = [
                os.path.expandvars(path_part)
                for path_part in os.environ[IncludeLoader.env_var_name].split(":")
            ]
        else:
            IncludeLoader.env_path_list = []

    return chain(loader_list, IncludeLoader.env_path_list)


def find_include(loader, node):
    """Locate an include file and return the abs path."""
    for directory in _get_include_dirs(loader):
        filename = os.path.abspath(
            os.path.join(directory, loader.construct_scalar(node))
        )
        if os.access(filename, os.R_OK):
            return filename

    raise BadSchemaError(
        "{} not found in include path: {}".format(
            loader.construct_scalar(node), [str(d) for d in _get_include_dirs(loader)]
        )
    )


def construct_include(loader, node):
    """Include file referenced at node."""

    filename = find_include(loader, node)
    extension = os.path.splitext(filename)[1].lstrip(".")

    if extension not in ("yaml", "yml", "json"):
        raise BadSchemaError(
            "Unknown filetype '{}' (included files must be in YAML format and end with .yaml or .yml)".format(
                filename
            )
        )

    return load_single_document_yaml(filename)


IncludeLoader.add_constructor("!include", construct_include)
IncludeLoader.add_constructor("!uuid", makeuuid)


class TypeSentinel(yaml.YAMLObject):
    """This is a sentinel for expecting a type in a response. Any value
    associated with these is going to be ignored - these are only used as a
    'hint' to the validator that it should expect a specific type in the
    response.
    """

    yaml_loader = IncludeLoader

    @staticmethod
    def constructor(_):
        raise NotImplementedError

    @classmethod
    def from_yaml(cls, loader, node):
        return cls()

    def __str__(self):
        return "<Tavern YAML sentinel for {}>".format(self.constructor)

    @classmethod
    def to_yaml(cls, dumper, data):
        node = yaml.nodes.ScalarNode(cls.yaml_tag, "", style=cls.yaml_flow_style)
        return node


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


class ListSentinel(TypeSentinel):
    yaml_tag = "!anylist"
    constructor = list


class DictSentinel(TypeSentinel):
    yaml_tag = "!anydict"
    constructor = dict


class RegexSentinel(TypeSentinel):
    """Sentinel that matches a regex in a part of the response

    This shouldn't be used directly and instead one of the below match/fullmatch/search tokens will be used
    """

    constructor = str
    compiled = None

    def __str__(self):
        return "<Tavern Regex sentinel for {}>".format(self.compiled.pattern)

    @property
    def yaml_tag(self):
        raise NotImplementedError

    @abstractmethod
    def passes(self, string):
        raise NotImplementedError

    @classmethod
    def from_yaml(cls, loader, node):
        c = cls()
        c.compiled = re.compile(node.value)
        return c


class _RegexMatchSentinel(RegexSentinel):
    yaml_tag = "!re_match"

    def passes(self, string):
        return self.compiled.match(string) is not None


class _RegexFullMatchSentinel(RegexSentinel):
    yaml_tag = "!re_fullmatch"

    def passes(self, string):
        return self.compiled.fullmatch(string) is not None


class _RegexSearchSentinel(RegexSentinel):
    yaml_tag = "!re_search"

    def passes(self, string):
        return self.compiled.search(string) is not None


class AnythingSentinel(TypeSentinel):
    yaml_tag = "!anything"
    constructor = "anything"

    @classmethod
    def from_yaml(cls, loader, node):
        return ANYTHING

    def __deepcopy__(self, memo):
        """Return ANYTHING when doing a deep copy

        This is required because the checks in various parts of the code assume
        that ANYTHING is a singleton, but doing a deep copy creates a new object
        by default
        """
        return ANYTHING


# One instance of this (see above)
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

    @staticmethod
    def constructor(_):
        raise NotImplementedError

    def __init__(self, value):
        self.value = value

    @classmethod
    def from_yaml(cls, loader, node):
        value = loader.construct_scalar(node)

        try:
            # See if it's already a valid value (eg, if we do `!int "2"`)
            converted = cls.constructor(value)
        except ValueError:
            # If not (eg, `!int "{int_value:d}"`)
            return cls(value)
        else:
            return converted

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.nodes.ScalarNode(
            cls.yaml_tag, data.value, style=cls.yaml_flow_style
        )


class IntToken(TypeConvertToken):
    yaml_tag = "!int"
    constructor = int


class FloatToken(TypeConvertToken):
    yaml_tag = "!float"
    constructor = float


class StrToBoolConstructor(object):
    """Using `bool` as a constructor directly will evaluate all strings to `True`."""

    def __new__(cls, s):
        return bool(strtobool(s))


class BoolToken(TypeConvertToken):
    yaml_tag = "!bool"
    constructor = StrToBoolConstructor


class StrToRawConstructor(object):
    """Used when we want to ignore brace formatting syntax"""

    def __new__(cls, s):
        return str(s.replace("{", "{{").replace("}", "}}"))


class RawStrToken(TypeConvertToken):
    yaml_tag = "!raw"
    constructor = StrToRawConstructor


class ForceIncludeToken(TypeConvertToken):
    """Magic tag that changes the way string formatting works"""

    yaml_tag = "!force_original_structure"

    @staticmethod
    def constructor(_):
        raise ValueError


# Sort-of hack to try and avoid future API changes
ApproxScalar = type(pytest.approx(1.0))


class ApproxSentinel(yaml.YAMLObject, ApproxScalar):  # type:ignore
    yaml_tag = "!approx"
    yaml_loader = IncludeLoader

    @classmethod
    def from_yaml(cls, loader, node):
        try:
            val = float(node.value)
        except (ValueError, TypeError) as e:
            logger.error(
                "Could not coerce '%s' to a float for use with !approx",
                type(node.value),
            )
            raise BadSchemaError from e
        else:
            return pytest.approx(val)

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.nodes.ScalarNode(
            "!approx", str(data.expected), style=cls.yaml_flow_style
        )


# Apparently this isn't done automatically?
yaml.dumper.Dumper.add_representer(ApproxScalar, ApproxSentinel.to_yaml)


def load_single_document_yaml(filename):
    """
    Load a yaml file and expect only one document

    Args:
        filename (str): path to document

    Returns:
        dict: content of file

    Raises:
        UnexpectedDocumentsError: If more than one document was in the file
    """

    with open(filename, "r", encoding="utf-8") as fileobj:
        try:
            contents = yaml.load(fileobj, Loader=IncludeLoader)
        except yaml.composer.ComposerError as e:
            msg = "Expected only one document in this file but found multiple"
            raise exceptions.UnexpectedDocumentsError(msg) from e

    return contents


def error_on_empty_scalar(self, mark):  # pylint: disable=unused-argument
    location = "{mark.name:s}:{mark.line:d} - column {mark.column:d}".format(mark=mark)
    error = "Error at {} - cannot define an empty value in test - either give it a value or explicitly set it to None".format(
        location
    )

    raise exceptions.BadSchemaError(error)


yaml.parser.Parser.process_empty_scalar = error_on_empty_scalar  # type:ignore

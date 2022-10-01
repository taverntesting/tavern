import operator
import re

from tavern._core import exceptions


def test_type(val, mytype):
    """Check value fits one of the types, if so return true, else false"""
    typelist = TYPES.get(str(mytype).lower())
    if typelist is None:
        raise TypeError(
            "Type {0} is not a valid type to test against!".format(str(mytype).lower())
        )
    try:
        for testtype in typelist:
            if isinstance(val, testtype):
                return True
        return False
    except TypeError:
        return isinstance(val, typelist)


COMPARATORS = {
    "count_eq": lambda x, y: safe_length(x) == y,
    "lt": operator.lt,
    "less_than": operator.lt,
    "eq": operator.eq,
    "equals": operator.eq,
    "str_eq": lambda x, y: operator.eq(str(x), str(y)),
    "ne": operator.ne,
    "not_equals": operator.ne,
    "gt": operator.gt,
    "greater_than": operator.gt,
    "contains": lambda x, y: x and operator.contains(x, y),  # is y in x
    "contained_by": lambda x, y: y and operator.contains(y, x),  # is x in y
    "regex": lambda x, y: regex_compare(str(x), str(y)),
    "type": test_type,
}
TYPES = {
    "none": [type(None)],
    "number": [int, float],
    "int": [int],
    "float": [float],
    "bool": [bool],
    "str": [str],
    "list": [list],
    "dict": [dict],
}


def regex_compare(_input, regex):
    return bool(re.search(regex, _input))


def safe_length(var):
    """Exception-safe length check, returns -1 if no length on type or error"""
    try:
        return len(var)
    except TypeError:
        return -1


def validate_comparison(each_comparison):
    try:
        assert set(each_comparison.keys()) == {"jmespath", "operator", "expected"}
    except KeyError as e:
        raise exceptions.BadSchemaError(
            "Invalid keys given to JMES validation function"
        ) from e

    jmespath, _operator, expected = (
        each_comparison["jmespath"],
        each_comparison["operator"],
        each_comparison["expected"],
    )

    try:
        COMPARATORS[_operator]
    except KeyError as e:
        raise exceptions.BadSchemaError("Invalid comparator given") from e

    return jmespath, _operator, expected


def actual_validation(_operator, _actual, expected, _expression, expression):
    if not COMPARATORS[_operator](_actual, expected):
        raise exceptions.JMESError(
            "Validation '{}' ({}) failed!".format(expression, _expression)
        )

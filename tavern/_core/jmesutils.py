import operator
import re
from collections.abc import Sized
from typing import Any

from tavern._core import exceptions


def test_type(val, mytype) -> bool:
    """Check value fits one of the types, if so return true, else false"""
    typelist = TYPES.get(str(mytype).lower())
    if typelist is None:
        raise TypeError(
            f"Type {str(mytype).lower()} is not a valid type to test against!"
        )
    try:
        for testtype in typelist:
            if isinstance(val, testtype):  # type: ignore
                return True
        return False
    except TypeError:
        return isinstance(val, typelist)  # type: ignore


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
TYPES: dict[str, list[Any]] = {
    "none": [type(None)],
    "number": [int, float],
    "int": [int],
    "float": [float],
    "bool": [bool],
    "str": [str],
    "list": [list],
    "dict": [dict],
}


def regex_compare(_input, regex) -> bool:
    return bool(re.search(regex, _input))


def safe_length(var: Sized) -> int:
    """Exception-safe length check, returns -1 if no length on type or error"""
    try:
        return len(var)
    except TypeError:
        return -1


def validate_comparison(each_comparison: dict[Any, Any]):
    if extra := set(each_comparison.keys()) - {"jmespath", "operator", "expected"}:
        raise exceptions.BadSchemaError(
            f"Invalid keys given to JMES validation function (got extra keys: {extra})"
        )

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


def actual_validation(
    _operator: str, _actual, expected, _expression, expression
) -> None:
    if not COMPARATORS[_operator](_actual, expected):
        raise exceptions.JMESError(f"Validation '{expression}' ({_expression}) failed!")

import logging

import jmespath

from tavern.util import exceptions
from tavern.util.dict_util import check_keys_match_recursive

logger = logging.getLogger(__name__)


def check_jmespath_match(parsed_response, query, expected=None):
    """
    Check that the JMES path given in 'query' is present in the given response

    Args:
        parsed_response (dict, list): Response list or dict
        query (str): JMES query
        expected (str, optional): Possible value to match against. If None,
            'query' will just check that _something_ is present
    """
    actual = jmespath.search(query, parsed_response)

    msg = "JMES path '{}' not found in response".format(query)

    if actual is None:
        raise exceptions.JMESError(msg)

    if expected is not None:
        # Reuse dict util helper as it should behave the same
        check_keys_match_recursive(expected, actual, [], True)
    elif not actual and not (actual == expected):  # pylint: disable=superfluous-parens
        # This can return an empty list, but it might be what we expect. if not,
        # raise an exception
        raise exceptions.JMESError(msg)

    return actual

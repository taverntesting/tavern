import logging
from abc import abstractmethod

from tavern.util.python_2_util import indent
from tavern.util.dict_util import format_keys, recurse_access_key, yield_keyvals

logger = logging.getLogger(__name__)


def indent_err_text(err):
    if err == "null":
        err = "<No body>"
    return indent(err, " "*4)


class BaseResponse(object):

    def __init__(self):
        # all errors in this response
        self.errors = []

    def _str_errors(self):
        return "- " + "\n- ".join(self.errors)

    def _adderr(self, msg, *args, **kwargs):
        e = kwargs.get('e')

        if e:
            logger.exception(msg, *args)
        else:
            logger.error(msg, *args)
        self.errors += [(msg % args)]

    @abstractmethod
    def verify(self, response):
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests
        """

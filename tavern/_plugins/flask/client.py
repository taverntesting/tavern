import logging
from tavern.util import exceptions
from tavern.util.dict_util import check_expected_keys
from tavern.util.python_2_util import partialmethod
from tavern.schemas.extensions import import_ext_function


logger = logging.getLogger(__name__)


class FlaskTestSession:
    
    def __init__(self, **kwargs):
        expected_blocks = {
            "app": {
                "location",
            },
        }

        check_expected_keys(expected_blocks.keys(), kwargs)

        try:
            self._app_args = kwargs.pop("app", {})
            app_location = self._app_args["location"]
        except KeyError:
            msg = "Need to specify app location (in the form my.module:application)"
            logger.error(msg)
            raise exceptions.MissingKeysError(msg)

        self._flask_app = import_ext_function(app_location)
        self._test_client = self._flask_app.test_client()

    def _make_request(self, method, route):
        meth = getattr(self._test_client, method)
        meth(route)

    get = partialmethod(_make_request, "GET")

import logging
from urllib.parse import parse_qs, urlparse

import requests

from tavern._core import exceptions
from tavern._core.pytest import call_hook
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse

logger: logging.Logger = logging.getLogger(__name__)


class RestResponse(CommonResponse):
    response: requests.Response

    def _get_redirect_query_params(self, response: requests.Response) -> dict[str, str]:
        """If there was a redirect header, get any query parameters from it"""

        try:
            redirect_url = response.headers["location"]
        except KeyError as e:
            if "redirect_query_params" in self.expected.get("save", {}):
                self._adderr(
                    "Wanted to save %s, but there was no redirect url in response",
                    self.expected["save"]["redirect_query_params"],
                    e=e,
                )
            redirect_query_params = {}
        else:
            parsed = urlparse(redirect_url)
            qp = parsed.query
            redirect_query_params = {i: j[0] for i, j in parse_qs(qp).items()}

        return redirect_query_params

    def verify(self, response: requests.Response) -> dict:
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests

        There are various ways to 'validate' a block - a specific function, just
        matching values, validating a schema, etc...

        Args:
            response: response object

        Returns:
            Any saved values

        Raises:
            TestFailError: Something went wrong with validating the response
        """

        call_hook(
            self.test_block_config,
            "pytest_tavern_beta_after_every_response",
            expected=self.expected,
            response=response,
        )
        body = self._common_verify_setup(response)  # type:ignore[arg-type]
        redirect_query_params = self._get_redirect_query_params(response)

        # Run validation on response
        self._check_status_code(response.status_code, body)

        self._validate_block("json", body)  # type:ignore[arg-type]
        self._validate_block("headers", response.headers)

        self._validate_block("redirect_query_params", redirect_query_params)

        attach_yaml(
            {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body,
                "redirect_query_params": redirect_query_params,
            },
            name="rest_response",
        )

        self._maybe_run_validate_functions(response)

        # Get any keys to save
        saved = self._common_verify_save(body, response)  # type:ignore[arg-type]
        saved.update(
            self.maybe_get_save_values_from_save_block(
                "redirect_query_params", redirect_query_params
            )
        )

        # Check cookies
        for cookie in self.expected.get("cookies", []):
            if cookie not in response.cookies:
                self._adderr("No cookie named '%s' in response", cookie)

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

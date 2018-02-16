import logging

logger = logging.getLogger(__name__)


def log_pass(test, response):
    # pylint: disable=unused-argument
    fmt = "PASSED: {:s}"
    formatted = fmt.format(test["name"])
    logger.info(formatted)


def log_fail(test, response, expected):
    # pylint: disable=unused-argument
    # TODO print more info
    fmt = "FAILED: {:s} [{}]"
    try:
        formatted = fmt.format(test["name"], response.status_code)
    except AttributeError:
        formatted = fmt.format(test["name"], "N/A")
    logger.error(formatted)
    logger.error("Expected: %s", expected)

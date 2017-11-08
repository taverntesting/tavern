import logging

logger = logging.getLogger(__name__)


def log_pass(test, response):
    fmt = "PASSED: {:s} [{:d}]"
    formatted = fmt.format(test["name"], response.status_code)
    logger.info(formatted)


def log_fail(test, response, expected):
    # TODO print more info
    fmt = "FAILED: {:s} [{}]"
    if response:
        formatted = fmt.format(test["name"], response.status_code)
    else:
        formatted = fmt.format(test["name"], "N/A")
    logger.error(formatted)
    logger.error("Expected: %s", expected)

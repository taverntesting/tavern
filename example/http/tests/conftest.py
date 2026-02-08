import logging
import logging.config

import pytest
import yaml

@pytest.fixture(autouse=True)
def setup_logging():
    log_cfg = """
---
version: 1
formatters:
    default:
        # colorlog is really useful
        (): colorlog.ColoredFormatter
        format: "%(asctime)s [%(bold)s%(log_color)s%(levelname)s%(reset)s]: (%(bold)s%(name)s:%(lineno)d%(reset)s) %(message)s"
        style: "%"
        datefmt: "%X"
        log_colors:
            DEBUG:    cyan
            INFO:     green
            WARNING:  yellow
            ERROR:    red
            CRITICAL: red,bg_white

handlers:
    stderr:
        class: colorlog.StreamHandler
        formatter: default

loggers:
    tavern:
        handlers:
            - stderr
        level: INFO
        propagate: false
"""

    as_dict = yaml.load(log_cfg, Loader=yaml.SafeLoader)
    logging.config.dictConfig(as_dict)

    logging.info("Logging set up")
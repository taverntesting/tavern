import logging
import logging.config

import yaml

from tavern._core.pytest.item import YamlItem

logging_initialised = False


def setup_logging():
    log_cfg = """
version: 1
disable_existing_loggers: true
formatters:
    fluent_fmt:
        (): fluent.handler.FluentRecordFormatter
        format:
            level: '%(levelname)s'
            where: '%(filename)s.%(lineno)d'
    default:
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
    fluent:
        class: fluent.handler.FluentHandler
        formatter: fluent_fmt
        tag: tavern
        port: 24224
        host: localhost
        level: INFO
    stderr:
        class: colorlog.StreamHandler
        formatter: default
        level: DEBUG
loggers:
    paho: &log
        handlers:
            - stderr
        level: DEBUG
        propagate: False
    tavern: 
        <<: *log

    tavern.mqtt: &reduced_log
        handlers:
            - stderr
            - fluent
        level: INFO
        propagate: False
    tavern.response.mqtt:
        <<: *reduced_log
    tavern.request.mqtt:
        <<: *reduced_log
"""

    as_dict = yaml.load(log_cfg, Loader=yaml.SafeLoader)
    logging.config.dictConfig(as_dict)

    logging.info("Logging set up")

    global logging_initialised
    logging_initialised = True


def pytest_runtest_setup(item):
    """Hack to get around pytest bug

    pytest doesn't appear to run 'autouse' fixtures unless the test being run is
    actually a normal python test, not for our custom tests - this runs
    setup_logging once for tavern tests
    """
    if isinstance(item, YamlItem) and not logging_initialised:
        setup_logging()

    return False

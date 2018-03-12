import logging
import argparse
from argparse import ArgumentParser #, ArgumentTypeError

from .core import run


class TavernArgParser(ArgumentParser):

    def __init__(self):
        super(TavernArgParser, self).__init__(
            description="""Parse yaml + make requests against an API""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        self.add_argument(
            "in_file",
            help="Input file with tests in",
        )

        self.add_argument(
            "--tavern-global-cfg",
            required=False,
            nargs="+",
            help="One or more global configuration files to include in every test",
        )

        self.add_argument(
            "--log-to-file",
            help="Log output to a file (tavern.log if no argument is given)",
            nargs="?",
            const="tavern.log",
        )

        self.add_argument(
            "--stdout",
            help="Log output stdout",
            action="store_true",
            default=False,
        )

        self.add_argument(
            "--debug",
            help="Log debug information (only relevant if --stdout or --log-to-file is passed)",
            action="store_true",
            default=False,
        )


def main():
    args = TavernArgParser().parse_args()
    vargs = vars(args)

    if vargs.pop("debug"):
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    # Basic logging config that will print out useful information
    log_cfg = {
        "version": 1,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s]: (%(name)s:%(lineno)d) %(message)s",
                "style": "%",
            },
        },
        "handlers": {
            "to_stdout": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "tavern": {
                "handlers": [
                ],
                "level": log_level,
            }
        }
    }

    log_loc = vargs.pop("log_to_file")

    if log_loc:
        log_cfg["handlers"].update({
            "to_file": {
                "class": "logging.FileHandler",
                "filename": log_loc,
                "formatter": "default",
            }
        })

        log_cfg["loggers"]["tavern"]["handlers"].append("to_file")

    if vargs.pop("stdout"):
        log_cfg["loggers"]["tavern"]["handlers"].append("to_stdout")

    logging.config.dictConfig(log_cfg)

    exit(not run(**vargs))

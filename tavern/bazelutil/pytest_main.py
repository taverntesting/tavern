import sys

import pytest


def run():
    return pytest.main(sys.argv)


if __name__ == "__main__":
    sys.exit(run())

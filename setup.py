#!/usr/bin/env python

from setuptools import setup

TESTS_REQUIRE = [
    "pytest-cov",
    "colorlog",
    "faker",
    "prospector[with_pyroma,with_mypy]>=1.3.0,<2",
    "pygments",
    "pylint==2.5.2",
    "black",
    "mypy",
    "mypy-extensions",
    "isort<5"
]

setup(
    name="tavern",

    tests_require=TESTS_REQUIRE,
    extras_require={
        "tests": TESTS_REQUIRE
    },

    zip_safe=True
)

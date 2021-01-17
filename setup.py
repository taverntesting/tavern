#!/usr/bin/env python

from setuptools import setup

TESTS_REQUIRE = [
    "pytest-cov",
    "colorlog",
    "faker",
    "flake8",
    "pygments",
    "pylint==2.6.0",
    "black",
    "mypy",
    "mypy-extensions",
    "isort==5.7.0"
]

setup(
    name="tavern",

    tests_require=TESTS_REQUIRE,
    extras_require={
        "tests": TESTS_REQUIRE
    },

    zip_safe=True
)

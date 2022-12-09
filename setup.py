#!/usr/bin/env python

from setuptools import setup

TESTS_REQUIRE = [
    "pytest-cov",
    "colorlog",
    "faker",
    "flake8",
    "pygments",
    "pylint",
    "black",
    "mypy",
    "mypy-extensions",
    "isort",
    "allure-pytest",
]

setup(
    name="tavern",

    tests_require=TESTS_REQUIRE,
    extras_require={
        "tests": TESTS_REQUIRE
    },

    zip_safe=True
)

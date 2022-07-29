#!/usr/bin/env python

from setuptools import setup

TESTS_REQUIRE = [
    "Faker~=7.0.1",
    "allure-pytest",
    "black==22.3.0",
    "colorlog~=6.6.0",
    "flake8",
    "flask~=2.0.0",
    "isort~=5.10.1",
    "itsdangerous~=2.0.0",
    "mypy",
    "mypy-extensions",
    "pygments",
    "pylint==2.6.0",
    "pytest-cov",
]

setup(
    name="tavern",

    tests_require=TESTS_REQUIRE,
    extras_require={
        "tests": TESTS_REQUIRE
    },

    zip_safe=True
)

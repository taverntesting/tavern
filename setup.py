#!/usr/bin/env python

import os

from subprocess import check_call
from distutils.core import Command
from setuptools import setup


class BuildDocs(Command):
    description = "Build documentation html"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.execute(check_call,
            [["sphinx-apidoc", "tavern", "-o", "docs"]],
            msg="Generating rst for tavern")

        self.execute(check_call,
            [["make", "-C", "docs", "html"]],
            msg="Making html docs")


class DeployPypi(Command):
    description = "Deploy to pypi using twine"
    user_options = [
        ("repository=", "r", "Repository to upload to"),
    ]

    def initialize_options(self):
        self.repository = None

    def finalize_options(self):
        if not self.repository:
            raise RuntimeError("Need a repository to upload to! Run 'python setup.py upload_twine' for options.")

    def run(self):
        self.run_command("clean")
        self.run_command("sdist")

        if len(os.listdir("dist")) > 1:
            raise RuntimeError("More than one package in dist/ - only one can be present to upload! Delete the dist/ folder before running this command.")

        to_upload = os.path.join("dist", os.listdir("dist")[0])

        args = ["twine", "upload", "-r", self.repository, to_upload]

        self.execute(check_call,
            [args],
            msg="Uploading package to pypi")


SETUP_REQUIRES = [
    "setuptools>=36",
    "pytest-runner",
]


setup(
    name="tavern",

    setup_requires=SETUP_REQUIRES,

    cmdclass={
        "docs": BuildDocs,
        "upload_twine": DeployPypi,
    },
)

load("@com_github_ali5h_rules_pip//:defs.bzl", "py_pytest_test")
load("@tavern_pip//:requirements.bzl", "requirement")

def gentest(filename):
    py_pytest_test(
        name = "integration_test_{}".format(filename),
        srcs = ["ext_functions.py"],
        args = [
            "-c",
            "pytest.ini",
            "--color",
            "yes",
            "--help",
        ],
        data = [
            "//:pytest.ini",
            filename,
        ],
        deps = [
            ":conftest",
            "//tavern",
            "//tavern/testutils",
            "//tavern/testutils/pytesthook",
            "@tavern_pip_faker//:pkg",
            "@tavern_pip_text_unidecode//:pkg",
            "@tavern_pip_colorlog//:pkg",
        ],
    )

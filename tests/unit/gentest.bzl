load("//bazel:tavern_test.bzl", "pytest_test")

def gentest(filename):
    pytest_test(
        name = "unit_test_{}".format(filename.replace("/", "_").replace(".py", "")),
        srcs = [filename],
        args = [
            "-c",
            "pyproject.toml",
            "--color",
            "yes",
        ],
        data = ["//:pyproject.toml"],
        deps = [
            ":conftest",
            "@tavern_pip_faker//:pkg",
            "@tavern_pip_colorlog//:pkg",
        ],
    )

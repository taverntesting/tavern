load("//bazel:tavern_test.bzl", "pytest_test")
load("@tavern_pip//:requirements.bzl", "requirement")

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
            requirement("faker"),
            requirement("colorlog"),
        ],
    )

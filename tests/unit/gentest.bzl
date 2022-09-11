load("//tavern/bazelutil:tavern_test.bzl", "pytest_test")

def gentest(filename):
    pytest_test(
        name = "unit_test_{}".format(filename.replace("/", "_").replace(".py", "")),
        srcs = [filename],
        args = [
            "-c",
            "pytest.ini",
            "--color",
            "yes",
        ],
        data = ["//:pytest.ini"],
        deps = [
            ":conftest",
            "@tavern_pip_faker//:pkg",
            "@tavern_pip_colorlog//:pkg",
        ],
    )

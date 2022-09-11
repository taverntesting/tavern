load("@rules_python//python:defs.bzl", "py_test")

def tavern_test(filename, extra_data = [], extra_deps = [], extra_args = [], **kwargs):
    base_data = [
        "//:pytest.ini",
        filename,
    ]

    base_deps = [
        "//tavern",
        "//tavern/_plugins/mqtt",
        "//tavern/_plugins/rest",
        "@rules_python//python/runfiles",
        "//tavern/testutils",
        "//tavern/testutils/pytesthook",
        "@tavern_pip_colorlog//:pkg",
    ]

    base_args = [
        filename,
        "-c",
        "pytest.ini",
        "-x",
        "--color",
        "yes",
        "--tavern-merge-ext-function-values",
    ]

    py_test(
        name = "integration_test_{}".format(filename),
        srcs = ["//tavern/bazelutil:integration_main.py"],
        args = base_args + extra_args,
        data = base_data + extra_data,
        main = "//tavern/bazelutil:integration_main.py",
        deps = base_deps + extra_deps,
        env = {
            "TAVERN_TEST_FILE_LOCATION": "$(location " + filename + ")",
        },
        tags = ["requires-network"],
        **kwargs
    )

def pytest_test(name, args = [], data = [], srcs = [], **kwargs):
    if "//:pytest.ini" not in data:
        data = data + ["//:pytest.ini"]

    args = args + [
        "--ignore=external",
        ".",
    ]

    py_test(
        name = name,
        srcs = srcs + ["//tavern/bazelutil:pytest_main.py"],
        main = "//tavern/bazelutil:pytest_main.py",
        data = data,
        args = args,
        **kwargs
    )

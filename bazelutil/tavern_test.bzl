load("@tavern_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")

def tavern_test(filename, extra_data = [], extra_deps = [], extra_args = []):
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
        srcs = ["//bazelutil:integration_main.py"],
        args = base_args + extra_args,
        data = base_data + extra_data,
        main = "//bazelutil:integration_main.py",
        deps = base_deps + extra_deps,
        env = {
            "TAVERN_TEST_FILE_LOCATION": "$(location " + filename + ")",
        },
    )

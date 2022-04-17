load("@tavern_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")

def gentest(filename):
    py_test(
        name = "integration_test_{}".format(filename),
        srcs = [":integration_main.py"],
        args = [
            filename,
            "-c",
            "pytest.ini",
            "-x",
            "--color",
            "yes",
            "--tavern-merge-ext-function-values",
            "--tavern-global-cfg",
            "tests/integration/global_cfg.yaml",
        ],
        data = [
            "//:pytest.ini",
            filename,
            ":common.yaml",
            ":global_cfg.yaml",
            ":OK.txt",
            ":OK.json.gz",
            ":testfile.txt",
        ],
        main = ":integration_main.py",
        deps = [
            ":conftest",
            "//tavern",
            "//tavern/_plugins/mqtt",
            "//tavern/_plugins/rest",
            "@rules_python//python/runfiles",
            "//tavern/testutils",
            "//tavern/testutils/pytesthook",
            "@tavern_pip_colorlog//:pkg",
        ],
    )

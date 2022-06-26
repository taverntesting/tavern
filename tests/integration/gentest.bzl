load("@tavern_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")
load("//tavern/bazelutil:tavern_test.bzl", "tavern_test")

def gentest(filename):
    tavern_test(
        filename,
        extra_args = [
            "--tavern-global-cfg",
            "tests/integration/global_cfg.yaml",
        ],
        extra_data = [
            ":common.yaml",
            ":global_cfg.yaml",
            ":OK.txt",
            ":OK.json.gz",
            ":parametrize_includes.yaml",
            ":testfile.txt",
            # Minor hack to make it so the tests are rerun when the server changes
            ":server_image.tar",
        ],
        extra_deps = [
            ":conftest",
        ],
    )

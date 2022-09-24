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
        ],
        extra_deps = [
            ":conftest",
        ],
        images = {"integration": ":server_image.tar"},
    )

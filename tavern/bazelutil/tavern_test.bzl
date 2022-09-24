load("@rules_python//python:defs.bzl", "py_test")
load("@bazel_skylib//rules:run_binary.bzl", "run_binary")

def tavern_test(filename, image, port, extra_data = [], extra_deps = [], extra_args = [], **kwargs):
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
        "@tavern_pip_docker//:pkg",
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

    image_names = "image_names_for_" + filename + ".json"
    run_binary(
        name = "load_image_for_" + filename,
        outs = [image_names],
        srcs = [image],
        tool = "//tavern/bazelutil:load_image",
        args = ["$(location " + image + ")", "$(location " + image_names + ")"],
    )

    py_test(
        name = "integration_test_{}".format(filename),
        srcs = ["//tavern/bazelutil:integration_main.py"],
        args = base_args + extra_args,
        data = base_data + extra_data + [image_names, image],
        main = "//tavern/bazelutil:integration_main.py",
        deps = base_deps + extra_deps,
        env = {
            "TAVERN_TEST_FILE_LOCATION": "$(location " + filename + ")",
            "TAVERN_DOCKER_IMAGES": "$(location " + image_names + ")",
            "TAVERN_DOCKER_PORT": str(port),
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

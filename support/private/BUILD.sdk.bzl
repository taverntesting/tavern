load("@bazel_tools//tools/build_defs/pkg:pkg.bzl", "pkg_tar")

pkg_tar(
    name = "libs_tar",
    srcs = glob(
        [
            "Lib/**",
        ],
        allow_empty = False,
    ),
    mode = "0444",
    strip_prefix = "Lib",
)

filegroup(
    name = "libs",
    srcs = glob(
        [
            "Lib/**",
        ],
        allow_empty = False,
        exclude = [
            "Lib/test/**",
        ],
    ),
    visibility = ["//visibility:public"],
)

genrule(
    name = "testy",
    srcs = [
        #        ":libs",
        ":libs_tar",
    ],
    outs = ["fake.txt"],
    cmd = """
    tar xf $(location libs_tar)
    find
    exit 1
    """,
)

filegroup(
    name = "sources",
    srcs = glob(["**/*"]),
    visibility = ["//visibility:public"],
)

#
#pkg_tar(
#    name = "bazel-bin",
#    srcs = ["//src:bazel"],
#    mode = "0755",
#    package_dir = "/usr/bin",
#    strip_prefix = "/src",
#)

load("@com_github_ali5h_rules_pip//:defs.bzl", "py_pytest_test")
load("@tavern_deps//:requirements.bzl", "requirement")

def gentest(filename):
    py_pytest_test(
        name = "unit_test_{}".format(filename),
        srcs = [filename],
        args = [
            "-c",
            "pytest.ini",
        ],
        data = ["//:pytest.ini"],
        deps = [
            "//tests:conftest",
            "//:setup",
            "//tavern",
            "//tavern/_plugins",
            "//tavern/_plugins/mqtt",
            "//tavern/_plugins/rest",
            "//tavern/request",
            "//tavern/response",
            "//tavern/schemas",
            "//tavern/testutils",
            "//tavern/testutils/pytesthook",
            "//tavern/util",
            requirement("faker"),
            requirement("text_unidecode"),
        ],
    )

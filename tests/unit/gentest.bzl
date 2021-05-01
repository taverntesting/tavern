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
            ":conftest",
            "//tests:conftest",
            "//:setup",
            requirement("faker"),
            requirement("text_unidecode"),
            requirement("colorlog"),
        ],
    )

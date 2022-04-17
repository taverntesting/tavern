load("@com_github_ali5h_rules_pip//:defs.bzl", "py_pytest_test")
load("@tavern_pip//:requirements.bzl", "requirement")

def gentest(filename):
    py_pytest_test(
        name = "unit_test_{}".format(filename),
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
            "//tests:conftest",
            "//:tavern",
            requirement("faker"),
            requirement("text_unidecode"),
            requirement("colorlog"),
        ],
    )
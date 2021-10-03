resources(
    name = "logging_config",
    sources = ["logging.yaml"],
)

python_library(
    name = "conftests",
    dependencies = [":logging_config"],
    sources = [
        "conftest.py",
        "unit/conftest.py",
    ],
)

python3_multitests(
    dependencies = [
        "//:tavern_wheel",
        "//:pyest_ini",
        "//:colorlog",
        "//:faker",
        ":conftests",
    ],
)

#python_tests(
#    name = "integration_test",
#    sources = [
#        "conftest.py",
#        "integration/*",
#    ],
#)

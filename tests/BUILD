resources(
    name = "logging_config",
    sources = ["logging.yaml"],
)

python_sources(
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

resources(
    name = "tavern_test_files",
    sources = [
        "integration/*.yaml",
        "integration/*.txt",
        "conftest.py",
        "integration/*.py",
    ],
)

python_tests(
    name = "integration_test",
    dependencies = [
        "//:tavern_wheel",
        "//:pyest_ini",
        "//:colorlog",
        "//:faker",
        ":conftests",
        ":tavern_test_files",
    ],
    sources = [
    ],
)

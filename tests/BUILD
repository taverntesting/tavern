python3_multitests(
    dependencies = [
        "//:tavern_wheel",
        "//:pyest_ini",
        ":logging_config",
        "//:colorlog",
    ],
    sources = [
        "conftest.py",
        "unit/**",
    ],
)

resources(
    name = "logging_config",
    sources = ["logging.yaml"],
)

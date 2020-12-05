python_tests(
  sources=["conftest.py", "unit/**"],
  dependencies=[
    "//tavern/util",
    "//tavern/testutils/pytesthook",
    "//tavern/_plugins/rest",
    ":logging_config" ]
)

resources(
    name="logging_config",
    sources=["logging.yaml"],
)

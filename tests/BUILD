python_tests(
  sources=["conftest.py", "unit/**"],
  dependencies=[
    "//:tavern_wheel",
    "//:pyest_ini",
    ":logging_config",
   ]
)

resources(
    name="logging_config",
    sources=["logging.yaml"],
)

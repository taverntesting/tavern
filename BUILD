python_requirements(
  module_mapping={
    "setuptools": ["pkg_resources"],
  },
)

resources(
    name="pyest_ini",
    sources=["pytest.ini"],
)

python_distribution(
    name="tavern_wheel",
    dependencies=[
      "//tavern/_plugins",
      "//tavern/_plugins/mqtt",
      "//tavern/_plugins/rest",
      "//tavern/request",
      "//tavern/response",
      "//tavern/schemas",
      "//tavern/schemas:schema_yaml",
      "//tavern/testutils",
      "//tavern/testutils/pytesthook",
      "//tavern/util",
    ],
    provides=setup_py(
        name="tavern",
        version="1.11.1",
        description="Tavern",
        author="Michael Boulton",
        classifiers=[
            "Programming Language :: Python :: 3",
        ],
    ).with_binaries({"tavern-ci": "//tavern:tavern-ci"}),
    setup_py_commands=["sdist", "bdist_wheel"]
)

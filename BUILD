python_requirements(
    module_mapping = {
        "setuptools": ["pkg_resources"],
        "PyYAML": ["yaml"],
        "python-box": ["box"],
        "pyjwt": ["jwt"],
    },
)

resources(
    name = "pyest_ini",
    sources = ["pytest.ini"],
)

python_distribution(
    name = "tavern_wheel",
    dependencies = [
        "//tavern",
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
    provides = setup_py(
        name = "tavern",
        author = "Michael Boulton",
        classifiers = [
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "Framework :: Pytest",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Topic :: Utilities",
            "Topic :: Software Development :: Testing",
            "License :: OSI Approved :: MIT License",
        ],
        description = "Simple testing of RESTful APIs",
        entry_points = {
            "pytest11": "tavern = tavern.testutils.pytesthook",
            "tavern_http": "requests = tavern._plugins.rest.tavernhook:TavernRestPlugin",
            "tavern_mqtt": "paho-mqtt = tavern._plugins.mqtt.tavernhook",
        },
        include_package_data = True,
        keywords = [
            "testing",
            "pytest",
        ],
        license = "MIT",
        license_file = "LICENSE",
        long_description = "file: README.rst",
        project_urls = {
            "Documentation": "https://taverntesting.github.io/",
            "Source": "https://github.com/taverntesting/tavern",
        },
        python_requires = ">=3.7",
        url = "https://taverntesting.github.io/",
        version = "1.11.1",
    ).with_binaries({
        "tavern-ci": "//tavern:tavern-ci",
    }),
    setup_py_commands = ["bdist_wheel"],
)

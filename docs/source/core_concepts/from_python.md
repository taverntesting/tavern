# Calling from Python

## Using the run() function

The `tavern.core.run()` function calls directly into the library, which then calls pytest.
Any options that would be passed to pytest can be passed to `run()` in the `pytest_args` argument.
This includes things like paths to global configuration files, and extra arguments to pytest or any other pytest plugins
that you may be using.

An example of using `pytest_args` to exit on the first failure:

```python
from tavern.core import run

success = run("test_server.tavern.yaml", pytest_args=["-x"])
```

`run()` will use a Pytest instance to actually run the tests, so these values
can also be controlled just by putting them in the appropriate Pytest
configuration file (such as your `setup.cfg` or `pytest.ini`).

Under the hood, the `run` function calls `pytest.main` to start the test
run, and will pass the return code back to the caller. At the time of
writing, this means it will return a `0` if all tests are successful,
and a nonzero result if one or more tests failed (or there was some
other error while running or collecting the tests).
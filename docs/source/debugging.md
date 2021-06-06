# Debugging a test

**This section assumes you're using pytest to run tests**.

When making a test it's not always going to work first time, and at the time of
writing the error reporting is a bit messy because it shows the whole stack
trace from pytest is printed out (which can be a few hundred lines, most of
which is useless). Figuring out if it's an error in the test, an error in the
API response, or even a bug in Tavern can be a bit tricky.

### Setting up logging

Tavern has extensive debug logging to help figure out what is going on in tests.
When running your tests, it helps a lot to set up logging so that you can check
the logs in case something goes wrong. The easiest way to do this is with
[dictConfig](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig)
from the Python logging library. It can also be useful to use
[colorlog](https://pypi.org/project/colorlog/) to colourize the output so it's
easier to see the different log levels. An example logging configuration

```yaml
# log_spec.yaml
---
version: 1
formatters:
    default:
        # colorlog is really useful
        (): colorlog.ColoredFormatter
        format: "%(asctime)s [%(bold)s%(log_color)s%(levelname)s%(reset)s]: (%(bold)s%(name)s:%(lineno)d%(reset)s) %(message)s"
        style: "%"
        datefmt: "%X"
        log_colors:
            DEBUG:    cyan
            INFO:     green
            WARNING:  yellow
            ERROR:    red
            CRITICAL: red,bg_white

handlers:
    stderr:
        class: colorlog.StreamHandler
        formatter: default

loggers:
    tavern:
        handlers:
            - stderr
        level: DEBUG

```

Which is used like this:

```python
from logging import config
import yaml

with open("log_spec.yaml", "r") as log_spec_file:
    config.dictConfig(yaml.load(log_spec_file))
```

Making sure this code is called before running your tests (for example, by
putting into `conftest.py`) will show the tavern logs if a test fails.

By default, recent versions of pytest will print out log messages in the
"Captured stderr call" section of the output - if you have set up your own
logging, you probably want to disable this by also passing `-p no:logging` to
the invocation of pytest.

### Setting pytest options

Some pytest options can be used to make the test output easier to read.

- Using the `-vv` option will show a separate line for each test and whether it
  has passed or failed as well as showing more information about mismatches in
  data returned vs data expected

- Using `--tb=short` will reduce the amount of data presented in the traceback
  when a test fails. If logging it set up as above, any important information
  will be present in the logs.

- If you just want to run one test you can use the `-k` flag to make pytest only
  run that test.

### Example

Say we are running against the [advanced example](https://github.com/taverntesting/tavern/tree/master/example/advanced)
from Tavern but we have an error in the yaml:

```yaml
  # Log in ...

  - name: post a number
    request:
      url: "{host}/numbers"
      json:
        name: smallnumber
        number: 123
      method: POST
      headers:
        content-type: application/json
        Authorization: "bearer {test_login_token:s}"
    response:
      status_code: 201
      headers:
        content-type: application/json
      # This key will not actually be present in the response
      json:
        a_key: missing
```

Having full debug output can be a bit too much information, so we set up logging
as above but at the `INFO` level rather than `DEBUG`.

We run this by doing `py.test --tb=short -p no:logging` and get the following
output:

```
../../../.virtualenvs/tavern/lib/python3.5/site-packages/_pytest/runner.py:192: in __init__
    self.result = func()
../../../.virtualenvs/tavern/lib/python3.5/site-packages/_pytest/runner.py:178: in <lambda>
    return CallInfo(lambda: ihook(item=item, **kwds), when=when)
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/__init__.py:617: in __call__
    return self._hookexec(self, self._nonwrappers + self._wrappers, kwargs)
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/__init__.py:222: in _hookexec
    return self._inner_hookexec(hook, methods, kwargs)
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/__init__.py:216: in <lambda>
    firstresult=hook.spec_opts.get('firstresult'),
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/callers.py:201: in _multicall
    return outcome.get_result()
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/callers.py:76: in get_result
    raise ex[1].with_traceback(ex[2])
../../../.virtualenvs/tavern/lib/python3.5/site-packages/pluggy/callers.py:180: in _multicall
    res = hook_impl.function(*args)
../../../.virtualenvs/tavern/lib/python3.5/site-packages/_pytest/runner.py:109: in pytest_runtest_call
    item.runtest()
tavern/testutils/pytesthook.py:124: in runtest
    run_test(self.path, self.spec, global_cfg)
tavern/core.py:111: in run_test
    saved = v.verify(response)
tavern/response/rest.py:147: in verify
    raise TestFailError("Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()))
E   tavern._core.exceptions.TestFailError: Test 'login' failed:
E   - Key not present: a_key
---------------------------- Captured stderr call -----------------------------
16:30:46 [INFO]: (tavern.core:70) Running test : Check trying to get a number that we didnt post before returns a 404
16:30:46 [INFO]: (tavern.core:99) Running stage : reset database for test
16:30:46 [INFO]: (tavern.response.rest:72) Response: '<Response [204]>' ()
16:30:46 [INFO]: (tavern.printer:10) PASSED: reset database for test
16:30:46 [INFO]: (tavern.core:99) Running stage : login
16:30:46 [INFO]: (tavern.response.rest:72) Response: '<Response [200]>' ({"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE1MjYwNTYyNDYsImF1ZCI6InRlc3RzZXJ2ZXIiLCJzdWIiOiJ0ZXN0LXVzZXIifQ.p7pwb_u_iNiYfqjTQS4Cj3mH4XDTeAoMjKn-Nn8u0lk"}
)
16:30:46 [ERROR]: (tavern.response.base:33) Key not present: a_key
Traceback (most recent call last):
  File "/home/michael/code/tavern/tavern/tavern/response/base.py", line 87, in recurse_check_key_match
    actual_val = recurse_access_key(block, list(split_key))
  File "/home/michael/code/tavern/tavern/tavern/_core/dict_util.py", line 77, in recurse_access_key
    return recurse_access_key(current_val[current_key], keys)
KeyError: 'a_key'
16:30:46 [ERROR]: (tavern.printer:21) FAILED: login [200]
16:30:46 [ERROR]: (tavern.printer:22) Expected: {'requests': {'save': {'$ext': {'extra_kwargs': {'jwt_key': 'token', 'key': 'CGQgaG7GYvTcpaQZqosLy4', 'options': {'verify_aud': True, 'verify_signature': True, 'verify_exp': True}, 'audience': 'testserver'}, 'function': 'tavern.testutils.helpers:validate_jwt'}, 'body': {'test_login_token': 'token'}}, 'status_code': 200, 'headers': {'content-type': 'application/json'}, 'body': {'a_key': 'missing', 'token': <tavern._core.loader.AnythingSentinel object at 0x7fce0b395c50>}}}
```

When tavern tries to access `a_key` in the response it gets a `KeyError` (shown
in the logs), and the `TestFailError` in the stack trace gives a more
human-readable explanation as to why the test failed.

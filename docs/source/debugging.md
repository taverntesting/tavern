# Debugging a test

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
easier to see the different log levels. An example logging configuration (note that this requires
the `colorlog` package to be installed):

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
        level: INFO
        propagate: false
```

Which is used like this:

```python
from logging import config
import yaml

with open("log_spec.yaml", "r") as log_spec_file:
    as_dict = yaml.load(log_spec_file.read(), Loader=yaml.SafeLoader)
    config.dictConfig(as_dict)
```

Making sure this code is called before running your tests (for example, by
putting into `conftest.py`) will show the tavern logs if a test fails.

By default, recent versions of pytest will print out log messages in the
"Captured stderr call" section of the output - if you have set up your own
logging, you probably want to disable this by also passing `-p no:logging` to
the invocation of pytest.

**WARNING**: Tavern will try not to log any response data or request data at the `INFO` level or
above (unless it is in an error trace). Logging at the `DEBUG` level will log things like response
headers, return values from any external functions etc. If this contains sensitive data, either
log at the `INFO` level, or make sure that any data logged is obfuscated, or the logs are not public.

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

Say we are running against the [http example](https://github.com/taverntesting/tavern/tree/master/example/http)
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
_______________________________________________________________ /home/michael/code/tavern/example/http/tests/test_hello.tavern.yaml::Test authenticated /hello ________________________________________________________________
Format variables:
  test_login_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJhdWQiOiJ0ZXN0c2VydmVyIiwiZXhwIjoxNzcwNTkyODMxfQ.5AZfT6_G0EpEI_mnR5t_JItDvmBvrILa9yK5XaJpbQY'
  service:s = 'http://localhost:5000'

Source test stage (line 18):
  - name: Authenticated /hello
    request:
      url: "{service:s}/hello/Jim"
      method: GET
      headers:
        Content-Type: application/json
        Authorization: "Bearer {test_login_token}"
    response:
      status_code: 200
      headers:
        content-type: application/json
      json:
        data: "this test should fail"

Formatted stage:
  name: Authenticated /hello
  request:
    headers:
      Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJhdWQiOiJ0ZXN0c2VydmVyIiwiZXhwIjoxNzcwNTkyODMxfQ.5AZfT6_G0EpEI_mnR5t_JItDvmBvrILa9yK5XaJpbQY
      Content-Type: application/json
    method: GET
    url: http://localhost:5000/hello/Jim
  response:
    headers:
      content-type: application/json
    json:
      data: this test should fail
    status_code: 200

Errors:
E   tavern._core.exceptions.TestFailError: Test 'Authenticated /hello' failed:
    - Key mismatch: (expected["data"] = 'this test should fail' (type = <class 'tavern._core.formatted_str.FormattedString'>), actual["data"] = 'Hello, Jim' (type = <class 'str'>))

---------------------------------------------------------------------------------------------------- Captured stderr call -----------------------------------------------------------------------------------------------------
22:28:52 [INFO]: (tavern._core.run:177) Running test : Test authenticated /hello
22:28:52 [INFO]: (tavern._core.run:370) Running stage : Unauthenticated /hello
22:28:52 [INFO]: (tavern._plugins.common.response:64) Response: '<Response [401]>'
22:28:52 [INFO]: (tavern._core.run:370) Running stage : Login and acquire token
22:28:53 [INFO]: (tavern._plugins.common.response:64) Response: '<Response [200]>'
22:28:53 [INFO]: (tavern._core.run:370) Running stage : Authenticated /hello
22:28:53 [INFO]: (tavern._plugins.common.response:64) Response: '<Response [200]>'
22:28:53 [ERROR]: (tavern.response:42) Key mismatch: (expected["data"] = 'this test should fail' (type = <class 'tavern._core.formatted_str.FormattedString'>), actual["data"] = 'Hello, Jim' (type = <class 'str'>))
Traceback (most recent call last):
  File "/home/michael/code/tavern/tavern/_core/dict_util.py", line 418, in check_keys_match_recursive
    assert actual_val == expected_val  # noqa
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/michael/code/tavern/tavern/_core/dict_util.py", line 418, in check_keys_match_recursive
    assert actual_val == expected_val  # noqa
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/michael/code/tavern/tavern/response.py", line 107, in recurse_check_key_match
    check_keys_match_recursive(expected_block, block, [], strict)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/michael/code/tavern/tavern/_core/dict_util.py", line 466, in check_keys_match_recursive
    check_keys_match_recursive(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^
        expected_val[key],
        ^^^^^^^^^^^^^^^^^^
    ...<2 lines>...
        strict,
        ^^^^^^^
    )
    ^
  File "/home/michael/code/tavern/tavern/_core/dict_util.py", line 553, in check_keys_match_recursive
    raise exceptions.KeyMismatchError(f"Key mismatch: ({full_err()})") from e
tavern._core.exceptions.KeyMismatchError: Key mismatch: (expected["data"] = 'this test should fail' (type = <class 'tavern._core.formatted_str.FormattedString'>), actual["data"] = 'Hello, Jim' (type = <class 'str'>))

```

When tavern tries to access `a_key` in the response it gets a `KeyError` (shown
in the logs), and the `TestFailError` in the stack trace gives a more
human-readable explanation as to why the test failed.

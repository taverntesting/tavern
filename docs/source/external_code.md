# Using Python functions in Tavern

## Calling external functions

Not every response can be validated simply by checking the values of keys, so with
Tavern you can call external functions to validate responses and save decoded data.
You can write your own functions or use those built in to Tavern. Each function
should take the response as its first argument, and you can pass extra arguments
using the **extra_kwargs** key.

To make sure that Tavern can find external functions you need to make sure that
it is in the Python path. For example, if `utils.py` is in the 'tests' folder,
you will need to run your tests something like (on Linux):

```shell
$ PYTHONPATH=$PYTHONPATH:tests py.test tests/
```

### Checking the response using external functions

The function(s) should be put into the `verify_response_with` block of a
response (HTTP or MQTT):

```yaml
  - name: Check friendly mess
    request:
      url: "{host}/token"
      method: GET
    response:
      status_code: 200
      verify_response_with:
        function: testing_utils:message_says_hello
```

```python
# testing_utils.py
def message_says_hello(response):
    """Make sure that the response was friendly
    """
    assert response.json().get("message") == "hello world"
```

A list of functions can also be passed to `verify_response_with` if you need to
check multiple things:

```yaml
    response:
      status_code: 200
      verify_response_with:
        - function: testing_utils:message_says_hello
        - function: testing_utils:message_says_something_else
          extra_kwargs:
            should_say: hello
```

### Built-in validators

There are two external functions built in to Tavern: `validate_jwt` and
`validate_pykwalify`.

`validate_jwt` takes the key of the returned JWT in the body as `jwt_key`, and
additional arguments that are passed directly to the `decode` method in the
[PyJWT](https://github.com/jpadilla/pyjwt/blob/master/jwt/api_jwt.py#L59)
library. **NOTE: Make sure the keyword arguments you are passing are correct
or PyJWT will silently ignore them. In the future, this function will likely be
changed to use a different library to avoid this issue.**

```yaml
# Make sure the response contains a key called 'token', the value of which is a
# valid jwt which is signed by the given key.
response:
  verify_response_with:
    function: tavern.helpers:validate_jwt
    extra_kwargs:
      jwt_key: "token"
      key: CGQgaG7GYvTcpaQZqosLy4
      options:
        verify_signature: true
        verify_aud: false
```

`validate_pykwalify` takes a
[pykwalify](http://pykwalify.readthedocs.io/en/master/) schema and verifies the
body of the response against it.

```yaml
# Make sure the response matches the given schema - a sequence of dictionaries,
# which has to contain a user name and may contain a user number.
response:
  verify_response_with:
    function: tavern.helpers:validate_pykwalify
    extra_kwargs:
      schema:
        type: seq
        required: True
        sequence:
          - type: map
            mapping:
              user_number:
                type: int
                required: False
              user_name:
                type: str
                required: True
```

If an external function you are using raises any exception, the test will be
considered failed. The return value from these functions is ignored.

### Using external functions for other things

External functions can be used to inject arbitrary data into tests or to save
data from the response.

An external function must return a dict where each key either points to a single value or
to an object which is accessible using dot notation. The easiest way to do this
is to return a [Box](https://pypi.python.org/pypi/python-box/) object.

**Note**: Functions used with `verify_response_with` or `save` in the
`response` block should always take the response as the first argument.

#### Injecting external data into a request

A use case for this is trying to insert some data into a response that is either
calculated dynamically or fetched from an external source. If we want to
generate some authentication headers to access our API for example, we can use
an external function using the `$ext` key to calculate it dynamically (note as
above that this function should _not_ take any arguments):

```python
# utils.py
from box import Box


def generate_bearer_token():
    token = sign_a_jwt()
    auth_header = {
        "Authorization": "Bearer {}".format(token)
    }
    return Box(auth_header)
```

This can be used as so:

```yaml
- name: login
  request:
    url: http://server.com/login
    headers:
      x-my-header: abc123
      $ext:
        function: utils:generate_bearer_token
    json:
      username: test_user
      password: abc123
  response:
    status_code: 200
```

By default, using the `$ext` key will replace anything already present in that block.
Input from external functions can be merged into a request instead by specifying the
`tavern-merge-ext-function-values` option in your pytest.ini or on the command line:

```python
# ext_functions.py

def return_hello():
    return {"hello": "there"}
```

```yaml
    request:
      url: "{host}/echo"
      method: POST
      json:
        goodbye: "now"
        $ext:
          function: ext_functions:return_hello
```

If `tavern-merge-ext-function-values` is set, this will send "hello" and "goodbye" in
the request. If not, it will just send "hello".

Example `pytest.ini` setting `tavern-merge-ext-function-values` as an argument.

```python
# pytest.ini
[pytest]
addopts = --tavern - merge - ext - function - values 
```

#### Saving data from a response

When using the `$ext` key in the `save` block there is special behaviour - each key in
the returned object will be saved as if it had been specified separately in the
`save` object. The function is called in the same way as a validator function,
in the `$ext` key of the `save` object.

Say that we have a server which returns a response like this:

```json
{
  "user": {
    "name": "John Smith",
    "id": "abcdef12345"
  }
}
```

If our test function extracts the key `name` from the response body (note as above
that this function should take the response object as the first argument):

```python
# utils.py
from box import Box


def test_function(response):
    return Box({"test_user_name": response.json()["user"]["name"]})
```

We would use it in the `save` object like this:

```yaml
save:
  $ext:
    function: utils:test_function
  json:
    test_user_id: user.id
```

In this case, both `{test_user_name}` and `{test_user_id}` are available for use
in later requests.

#### A more complicated example

For a more practical example, the built in `validate_jwt` function also returns the
decoded token as a dictionary wrapped in a [Box](https://pypi.python.org/pypi/python-box/) object, which allows
dot-notation
access to members. This means that the contents of the token can be used for
future requests. Because Tavern will already be in the Python path (because you
installed it as a library) you do not need to modify the `PYTHONPATH`.

For example, if our server saves the user ID in the 'sub' field of the JWT:

```yaml
- name: login
  request:
    url: http://server.com/login
    json:
      username: test_user
      password: abc123
  response:
    status_code: 200
    verify_response_with:
      # Make sure a token exists
      function: tavern.helpers:validate_jwt
      extra_kwargs:
        jwt_key: "token"
        options:
          verify_signature: false
    save:
      # Saves a jwt token returned as 'token' in the body as 'jwt'
      # in the test configuration for use in future tests
      # Note the use of $ext again
      $ext:
        function: tavern.helpers:validate_jwt
        extra_kwargs:
          jwt_key: "token"
          options:
            verify_signature: false

- name: Get user information
  request:
    url: "http://server.com/info/{jwt.sub}"
    ...
  response:
    ...
```

Ideas for other helper functions which might be useful:

- Making sure that the response matches a database schema
- Making sure that an error returns the correct error text in the body
- Decoding base64 data to extract some information for use in a future query
- Validate templated HTML returned from an endpoint using an XML parser
- etc.

One thing to bear in mind is that data can only be saved for use within the same
test - each YAML document is considered to be a separate test (not counting
anchors as described below). If you need to use the data in multiple tests, you
will either need to put it into another file which you then include, or perform
the same request in each test to re-fetch the data.

## Hooks

As well as fixtures as mentioned in the previous section, since version 0.28.0
there is a couple of hooks which can be used to extract more information from
tests.

These hooks are used by defining a function with the name of the hook in your
`conftest.py` that take the same arguments _with the same names_ - these hooks
will then be picked up at runtime and called appropriately.

**NOTE**: These hooks should be considered a 'beta' feature, they are ready to
use but the names and arguments they take should be considered unstable and may
change in a future release (and more may also be added).

More documentation for these can be found in the docstrings for the hooks
in the `tavern/testutils/pytesthook/newhooks.py` file.

### Before every test run

This hook is called after fixtures, global configuration, and plugins have been
loaded, but _before_ formatting is done on the test and the schema of the test
is checked. This can be used to 'inject' extra things into the test before it is
run, such as configurations blocks for a plugin, or just for some kind of
logging.

Example usage:

```python
import logging


def pytest_tavern_beta_before_every_test_run(test_dict, variables):
    logging.info("Starting test %s", test_dict["test_name"])

    variables["extra_var"] = "abc123"
```

### After every test run

This hook is called _after_ execution of each test, regardless of the test
result. The hook can, for example, be used to perform cleanup after the test is run.

Example usage:

```python
import logging


def pytest_tavern_beta_after_every_test_run(test_dict, variables):
    logging.info("Ending test %s", test_dict["test_name"])
```

### After every response

This hook is called after every _response_ for each _stage_ - this includes HTTP
responses, but also MQTT responses if you are using MQTT. This means if you are
using MQTT it might be called multiple times for each stage!

Example usage:

```python
def pytest_tavern_beta_after_every_response(expected, response):
    with open("logfile.txt", "a") as logfile:
        logfile.write("Got response: {}".format(response.json()))
```

### Before every request

This hook is called just before each request with the arguments passed to the request
"function". By default, this is Session.request (from requests) for HTTP and Client.publish
(from paho-mqtt) for MQTT.

Example usage:

```python
import logging


def pytest_tavern_beta_before_every_request(request_args):
    logging.info("Making request: %s", request_args)
```

## Tinctures

Another way of running functions at certain times is to use the 'tinctures' functionality:

```python
# package/helpers.py

import logging
import time

logger = logging.getLogger(__name__)


def time_request(stage):
    t0 = time.time()
    yield
    t1 = time.time()
    logger.info("Request for stage %s took %s", stage, t1 - t0)


def print_response(_, extra_print="affa"):
    logger.info("STARTING:")
    (expected, response) = yield
    logger.info("Response is %s (%s)", response, extra_print)
```

```yaml
---
test_name: Test tincture

tinctures:
  - function: package.helpers:time_request

stages:
  - name: Make a request
    tinctures:
      - function: package.helpers:print_response
        extra_kwargs:
          extra_print: "blooble"
    request:
      url: "{host}/echo"
      method: POST
      json:
        value: "one"

  - name: Make another request
    request:
      url: "{host}/echo"
      method: POST
      json:
        value: "two"
```

Tinctures can be specified on a per-stage level or a per-test level. When specified on the test level, the tincture is
run for every stage in the test. In the above example, the `time_request` function will be run for both stages, but
the 'print_response' function will only be run for the first stage.

Tinctures are _similar_ to fixtures but are more similar to [external functions](#calling-external-functions). Tincture
functions do not need to be annotated with a function like Pytest fixtures, and are referred to in the same
way (`path.to.package:function`), and have arguments passed to them in the same way (`extra_kwargs`, `extra_args`) as
external functions.

The first argument to a tincture is always a dictionary of the stage to be run.

If a tincture has a `yield` in the middle of it, during the `yield` the stage itself will be run. If a return value is
expected from the `yield` (eg `(expected, response) = yield` in the example above) then the _expected_ return values and
the response object from the stage will be returned. This allows a tincture to introspect the response, and compare it
against the expected, the same as the `pytest_tavern_beta_after_every_response` [hook](#after-every-response). This
response object will be different for MQTT and HTTP tests!

If you need to run something before _every_ stage or after _every_ response in your test suite, look at using
the [hooks](#hooks) instead.

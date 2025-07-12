# Basic Concepts

## Quick Start Guide

New to Tavern? Follow this quick start guide to get up and running in minutes.

### 1. Installation

```bash
pip install tavern
```

### 2. Your First Test

Create a file called `test_my_api.tavern.yaml`:

```yaml
test_name: My First Tavern Test

stages:
  - name: Check API health
    request:
      url: https://httpbin.org/get
      method: GET
    response:
      status_code: 200
      json:
        url: "https://httpbin.org/get"
```

### 3. Run Your Test

```bash
python -m pytest test_my_api.tavern.yaml -v
```

### 4. Next Steps

- Check out the [Getting Started Examples](../../example/getting_started/) for comprehensive tutorials
- Read the [Advanced Cookbook](cookbook.html) for advanced features
- Explore [HTTP](http.html), [MQTT](mqtt.html), and [gRPC](grpc.html) specific guides

## Common Patterns

### Testing with Authentication

```yaml
test_name: Authenticated API Test

stages:
  - name: Login to get token
    request:
      url: https://api.example.com/login
      method: POST
      json:
        username: "testuser"
        password: "password123"
    response:
      status_code: 200
      save:
        json:
          auth_token: token

  - name: Make authenticated request
    request:
      url: https://api.example.com/protected
      method: GET
      headers:
        Authorization: "Bearer {auth_token}"
    response:
      status_code: 200
```

### Using Pytest Marks

```yaml
test_name: Integration Test

marks:
  - integration
  - slow
  - usefixtures:
      - setup_test_data

stages:
  - name: Test integration scenario
    request:
      url: https://api.example.com/integration
      method: GET
    response:
      status_code: 200
```

### Error Handling

```yaml
test_name: Error Handling Test

stages:
  - name: Test 404 response
    request:
      url: https://api.example.com/notfound
      method: GET
    response:
      status_code: 404
      json:
        error: "Resource not found"

  - name: Test validation error
    request:
      url: https://api.example.com/users
      method: POST
      json:
        # Missing required fields
    response:
      status_code: 400
      json:
        error: "Validation failed"
```

## Anatomy of a test

Tests are defined in YAML with a **test_name**, one or more **stages**, each of
which has a **name**, a **request** and a **response**. Taking the simple example:

```yaml
test_name: Get some fake data from the JSON placeholder API

stages:
  - name: Make sure we have the right ID
    request:
      url: https://jsonplaceholder.typicode.com/posts/1
      method: GET
    response:
      status_code: 200
      json:
        id: 1
        userId: 1
        title: "sunt aut facere repellat provident occaecati excepturi optio reprehenderit"
        body: "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
      save:
        json:
          returned_id: id
```

If using the pytest plugin (the recommended way of using Tavern), this needs to
be in a file called `test_x.tavern.yaml`, where `x` should be a description of
the contained tests.

If you want to call your files something different (though this is not
recommended) it is also possible to specify a custom regular expression to match
filenames. For example, if you want to call all of your files
`tavern_test_x.yaml`, `tavern_test_y.yaml`, etc. then use the
`tavern-file-path-regex` option in the configuration file or on the command
line. For example, `py.test --tavern-file-path-regex "tavern_test_.*.yaml"`

**test_name** is, as expected, the name of that test. If the pytest plugin is
being used to run integration tests, this is what the test will show up as in
the pytest report, for example:

```
tests/integration/test_simple.tavern.yaml::Get some fake data from the JSON placeholder API
```

This can then be selected with the `-k` flag to pytest - e.g. pass `pytest -k fake`
to run all tests with 'fake' in the name.

**stages** is a list of the stages that make up the test. A simple test might
just be to check that an endpoint returns a 401 with no login information. A
more complicated one might be:

1. Log in to server

- `POST` login information in body
- Expect login details to be returned in body

2. Get user information

- `GET` with login information in `Authorization` header
- Expect user information returned in body

3. Create a new resource with that user information

- `POST` with login information in `Authorization` header and user information in body
- Expect a 201 with the created resource in the body

4. Make sure it's stored on the server

- `GET` with login information in `Authorization` header
- Expect the same information returned as in the previous step

The **name** of each stage is a description of what is happening in that
particular test.

### Request

The **request** describes what will be sent to the server. The keys for this are
passed directly to the
[requests](http://docs.python-requests.org/en/master/api/#requests.request)
library (after preprocessing) - at the moment the only supported keys are:

- `url` - a string, including the protocol, of the address of the server that
  will be queried
- `json` - a mapping of (possibly nested) key: value pairs/lists that will be
  converted to JSON and sent as the request body.
- `params` - a mapping of key: value pairs that will go into the query
  parameters.
- `data` - Either a mapping of key: value pairs that will go into the body as
  application/x-www-url-formencoded data, or a string that will be sent by
  itself (with no content-type).
- `headers` - a mapping of key: value pairs that will go into the headers. Defaults
  to adding a `content-type: application/json` header.
- `method` - one of GET, POST, PUT, DELETE, PATCH, OPTIONS, or HEAD. Defaults to
  GET if not defined

For more information, refer to the [requests
documentation](http://docs.python-requests.org/en/master/api/#requests.request).

### Response

The **response** describes what we expect back. There are a few keys for verifying
the response:

- `status_code` - an integer corresponding to the status code that we expect, or
  a list of status codes if you are expecting one of a few status codes.
  Defaults to `200` if not defined.
- `json` - Assuming the response is json, check the body against the values
  given. Expects a mapping (possibly nested) key: value pairs/lists. This can
  also use an external check function, described further down.
- `headers` - a mapping of key: value pairs that will be checked against the
  headers.
- `redirect_query_params` - Checks the query parameters of a redirect url passed
  in the `location` header (if one is returned). Expects a mapping of key: value
  pairs. This can be useful for testing implementation of an OpenID connect
  provider, where information about the request may be returned in redirect
  query parameters.

The **save** block can save values from the response for use in future requests.
Things can be saved from the body, headers, or redirect query parameters. When
used to save something from the json body, this can also access dictionaries
and lists recursively. If the response is:

```json
{
  "thing": {
    "nested": [
      1,
      2,
      3,
      4
    ]
  }
}
```

This can be saved into the value `first_val` with this response block:

```yaml
response:
  save:
    json:
      first_val: "thing.nested[0]"
```

The query should be defined as a JMES query (see [JMESPath](http://jmespath.org/)
for more information). In the above example, this essentially performs
the operation `json["thing"]["nested"][0]`. This can be used to perform
powerful queries on response data.

This can be used to save blocks of data as well, for example:

```yaml
response:
  save:
    json:
      nested_thing: "thing"
```

This will save `{"nested": [1, 2, 3, 4]}` into the `nested_thing` variable. See the documentation for
the `force_format_include` tag for how this can be used.

**NOTE**: The behaviour of these queries used to be different and indexing into
an array was done like `thing.nested.0`. This will be deprecated in the
1.0 release.

It is also possible to save data using function calls, [explained below](#saving-data-from-a-response).

For a more formal definition of the schema that the tests are validated against,
check [tests schema](https://github.com/taverntesting/tavern/blob/master/tavern/schemas/tests.schema.yaml) in the main
Tavern repository.

## Generating Test Reports

Since 1.13 Tavern has support via the Pytest integration provided by
[Allure](https://docs.qameta.io/allure/#_pytest). To generate a test report, add `allure-pytest`
to your Pip dependencies and pass the `--alluredir=<dir>` flag when running Tavern. This will produce
a test report with the stages that were run, the responses, any fixtures used, and any errors.

See the [Allure documentation](https://docs.qameta.io/allure/#_installing_a_commandline) for more
information on how to use it.

## Variable formatting

Variables can be used to prevent hardcoding data into each request, either from
included global configuration files or saving data from previous stages of a
test (how these variables are 'injected' into a test is described in more detail
in the relevant sections).

An example of accessing a string from a configuration file which is then passed
in the request:

```yaml
request:
  json:
    variable_key: "{key_name:s}"
    # or
    # variable_key: "{key_name}"
```

This is formatted using Python's [string formatting
syntax](https://docs.python.org/3/library/string.html#format-string-syntax). The
variable to be used is encased in curly brackets and an optional
[type code](https://docs.python.org/3/library/string.html#format-specification-mini-language)
can be passed after a colon.

This means that if you want to pass a literal `{` or `}` in a request (or expect
it in a response), it must be escaped by doubling it:

```yaml
request:
  json:
    graphql_query: "{%raw%}{{ user(id: 123) {{ first_name }} }}{%endraw%}"
```

Since `0.5.0`, Tavern also has some 'magic' variables available in the `tavern`
key for formatting.

### Request variables

This currently includes all request variables and is available under the
`request_vars` key. Say we want to test a server that updates a user's profile
and returns the change:

```
---
test_name: Check server responds with updated data

stages:
  - name: Send message, expect it to be echoed back
    request:
      method: POST
      url: "www.example.com/user"
      json:
        welcome_message: "hello"
      params:
        user_id: abc123
    response:
      status_code: 200
      json:
        user_id: "{tavern.request_vars.params.user_id}"
        new_welcome_message: "{tavern.request_vars.json.welcome_message}"
```

This example uses `json` and `params` - we can also use any of the other request
parameters like `method`, `url`, etc.

### Environment variables

Environment variables are also available under the `env_vars` key. If a server
being tested against requires a password, bearer token, or some other form of
authorisation that you don't want to ship alongside the test code, it can be
accessed via this key (for example, in CI).

```
---
test_name: Test getting user information requires auth

stages:
  - name: Get information without auth fails
    request:
      method: GET
      url: "www.example.com/get_info"
    response:
      status_code: 401
      json:
        error: "No authorization"

  - name: Get information with admin token
    request:
      method: GET
      url: "www.example.com/get_info"
      headers:
        Authorization: "Basic {tavern.env_vars.SECRET_CI_COMMIT_AUTH}"
    response:
      status_code: 200
      json:
        name: "Joe Bloggs"
```

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
PYTHONPATH=$PYTHONPATH:tests py.test tests/
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

**Note**: Functions used in the `verify_response_with` block in the
_response_ block take the response as the first argument. Functions used
anywhere else should take _no_ arguments. This might be changed in future to be
less confusing.

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

## Strict key checking

'Strict' key checking can be enabled or disabled globally, per test, or per
stage. 'Strict' key checking refers to whether extra keys in the response should
be ignored or whether they should raise an error. With strict key checking
enabled, all keys in dictionaries at all levels have to match or it will raise
an error. With it disabled, Extra keys in the response will be ignored as long
as the ones in your response block are present.

Strict key checking can be controlled individually for the response for the JSON
body,the redirect query parameter, or the headers.

By default, strict key checking is _disabled_ for headers and redirect query
parameters in the response, but _enabled_ for JSON (as well as when checking for
JSON in an mqtt response). This is because although there may be a lot of
'extra' things in things like the response headers (such as server agent
headers, cache control headers, etc), the expected JSON body will likely always
want to be matched exactly.

### Effect of different settings

This is best explained through an example. If we expect this response from a
server:

```json
{
  "first": 1,
  "second": {
    "nested": 2
  }
}
```

This is what we would put in our Tavern test:

```yaml
...
response:
  json:
    first: 1
    second:
      nested: 2
```

The behaviour of various levels of 'strictness' based on the response:

| Response                                                  | strict=on | strict=off |
|-----------------------------------------------------------|-----------|------------|
| `{ "first": 1, "second": { "nested": 2 } }`               | PASS      | PASS       |
| `{ "first": 1 }`                                          | FAIL      | PASS       |
| `{ "first": 1, "second": { "another": 2 } }`              | FAIL      | FAIL       |
| `{ "first": 1, "second": { "nested": 2, "another": 2 } }` | FAIL      | PASS       |

Turning 'strict' off also means that extra items in lists will be ignored as
long as the ones specified in the test response are present. For example, if the
response from a server is `[ 1, 2, 3 ]` then strict being on - the default for
the JSON response body - will match _only_ `[1, 2, 3]`.

With strict being turned off for the body, any of these in the test will pass:

- `[1, 2, 3]`
- `[1]`
- `[2]`
- `[3]`
- `[1, 2]`
- `[2, 3]`
- `[1, 3]`

But not:

- `[2, 4]` - '4' not present in response from the server
- `[3, 1]`, `[2, 1]` - items present, but out of order

To match the last case you can use the special setting `list_any_order`. This setting
can only be used in the 'json' key of a request, but will match list items in any order as
long as they are present in the response.

### Changing the setting

This setting can be controlled in 3 different ways, the order of priority being:

1. In the test/stage itself
2. Passed on the command line
3. Read from pytest config

This means that using the command line option will _not_ override any settings
for specific tests.

Each of these methods is done by passing a sequence of strings indicating which
section (`json`/`redirect_query_params`/`headers`) should be affected, and
optionally whether it is on or off.

- `json:off headers:on` - turn off for the body, but on for the headers.
  `redirect_query_params` will stay default off.
- `json:off headers:off` - turn body and header strict checking off
- `redirect_query_params:on json:on` redirect parameters is turned on and json
  is kept on (as it is on by default), header strict matching is kept off (as
  default).

Leaving the 'on' or 'off' at the end of each setting will imply 'on' - ie, using
`json headers redirect_query_params` as an option will turn them all on.

#### Command line

There is a command line argument, `--tavern-strict`, which controls the default
global strictness setting.

```shell
# Enable strict checking for body and headers only
py.test --tavern-strict json:on headers:on redirect_query_params:off -- my_test_folder/
```

#### In the Pytest config file

This behaves identically to the command line option, but will be read from
whichever configuration file Pytest is using.

```ini
[pytest]
tavern-strict = json:off headers:on
```

#### Per test

Strictness can also be enabled or disabled on a per-test basis. The `strict` key
at the top level of the test should a list consisting of one or more strictness
setting as described in the previous section.

```yaml
---

test_name: Make sure the headers match what I expect exactly

strict:
  - headers:on
  - json:off

stages:
  - name: Try to get user
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      status_code: 200
      headers:
        content-type: application/json
        content-length: 20
        x-my-custom-header: chocolate
      json:
        # As long as "id: 1" is in the response, this will pass and other keys will be ignored
        id: 1
```

A special option that can be done at the test level (or at the stage level, as
described in the next section) is just to pass a boolean. This will turn strict
checking on or off for all settings for the duration of that test/stage.

```yaml
test_name: Just check for one thing in a big nested dict

# completely disable strict key checking for this whole test
strict: False

stages:
  - name: Try to get user
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      status_code: 200
      json:
        q:
          x:
            z:
              a: 1
```

#### Per stage

Often you have a standard stage before other stages, such as logging in to your
server, where you only care if it returns a 200 to indicate that you're logged
in. To facilitate this, you can enable or disable strict key checking on a
per-stage basis as well.

Two examples for doing this - these examples should behave identically:

```yaml
---

# Enable strict checking for this test, but disable it for the login stage

test_name: Login and create a new user

# Force re-enable strict checking, in case it was turned off globally
strict:
  - json:on

stages:
  - name: log in
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      # Disable all strict key checking just for this stage
      strict: False
      status_code: 200
      json:
        logged_in: True
        # Ignores any extra metadata like user id, last login, etc.

  - name: Create a new user
    request:
      url: "{host}/users/joebloggs"
      method: POST
      json: &create_user
        first_name: joe
        last_name: bloggs
        email: joe@bloggs.com
    response:
      status_code: 200
      # Because strict was set 'on' at the test level, this must match exactly
      json:
        <<: *create_user
        id: 1
```

## Marking tests

Tests can be marked using the `marks` key. This uses pytest's marking system under the hood.

> **Pytest 7.3.0+ Compatibility:**
> All marks in Tavern are now created and handled using the modern Pytest API. Use `pytest.Mark` objects for programmatic mark creation, and always access mark arguments via `.args`. Register custom marks in your `pytest.ini`, `pyproject.toml`, or `conftest.py` to avoid warnings.

```yaml
test_name: A test with marks

marks:
  - slow
  - integration
  - skipif: "some_condition"
  - parametrize:
      key: fruit
      vals:
        - apple
        - orange
```

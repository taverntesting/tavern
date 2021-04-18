# Basic Concepts

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
            1, 2, 3, 4
        ]
    }
}
```

This can be saved into the value `first_val` with this response block:

```yaml
response:
  save:
    json:
      first_val: thing.nested[0]
```

The query should be defined as a JMES query (see [JMESPath](http://jmespath.org/)
for more information). In the above example, this essentially performs
the operation `json["thing"]["nested"][0]`. This can be used to perform
powerful queries on response data, but note that only 'simple' values
like integers, strings, or float values can be saved. Trying to save a
'block' of data such as a JSON list or object is currently unsupported
and will cause the test to fail.

**NOTE**: The behaviour of these queries used to be different and indexing into
an array was done like `thing.nested.0`. This will be deprecated in the
1.0 release.

It is also possible to save data using function calls, [explained below](#saving-data-from-a-response).

For a more formal definition of the schema that the tests are validated against,
check [tests schema](https://github.com/taverntesting/tavern/blob/master/tavern/schemas/tests.schema.yaml) in the main Tavern repository.

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
    function: tavern.testutils.helpers:validate_jwt
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
    function: tavern.testutils.helpers:validate_pykwalify
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
the request. If not, it will just sent "hello". 

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
decoded token as a dictionary wrapped in a [Box](https://pypi.python.org/pypi/python-box/) object, which allows dot-notation
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
      function: tavern.testutils.helpers:validate_jwt
      extra_kwargs:
        jwt_key: "token"
        options:
          verify_signature: false
    save:
      # Saves a jwt token returned as 'token' in the body as 'jwt'
      # in the test configuration for use in future tests
      # Note the use of $ext again
      $ext:
        function: tavern.testutils.helpers:validate_jwt
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

| Response | strict=on | strict=off |
| ---- | -------- | ------ |
| `{ "first": 1, "second": { "nested": 2 } }`  | PASS | PASS |
| `{ "first": 1 }`  | FAIL | PASS |
| `{ "first": 1, "second": { "another": 2 } }`  | FAIL | FAIL |
| `{ "first": 1, "second": { "nested": 2, "another": 2 } }`  | FAIL | PASS |

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

- `[3, 1]`, `[2, 1]` - items present, but out of order
- `[2, 4]` - '4' not present in response from the server

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
tavern-strict=json:off headers:on
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

Or if strict json key checking was enabled at the global level:

```yaml
---

test_name: Login and create a new user

stages:
  - name: log in
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      strict:
        - json:off
      status_code: 200
      json:
        logged_in: True

  - name: Create a new user
    request: ...
```

## Reusing requests and YAML fragments

A lot of tests will require using the same step multiple times, such as logging
in to a server before running tests or simply running the same request twice in
a row to make sure the same (or a different) response is returned.

Anchors are a feature of YAML which allows you to reuse parts of the code. Define
an anchor using  `&name_of_anchor`. This can then be assigned to another object
using `new_object: *name_or_anchor`, or they can be used to extend objects using
`<<: *name_of_anchor`.

```yaml
# input.yaml
---
first: &top_anchor
  a: b
  c: d

second: *top_anchor

third:
  <<: *top_anchor
  c: overwritten
  e: f
```

If we convert this to JSON, for example with a script like this:

```python
#!/usr/bin/env python

# load.py
import yaml
import json

with open("input.yaml", "r") as yfile:
    for doc in yaml.load_all(yfile.read()):
        print(json.dumps(doc, indent=2))
```

We get something like the following:

```
{
  'first': {
    'a': 'b',
    'c': 'd'
  },
  'second': {
    'a': 'b',
    'c': 'd'
  },
  'third': {
    'a': 'b',
    'c': 'overwritten',
    'e': 'f'
  }
}
```

This does not however work if there are different documents in the yaml file:

```yaml
# input.yaml
---
first: &top_anchor
  a: b
  c: d

second: *top_anchor

---

third:
  <<: *top_anchor
  c: overwritten
  e: f
```

```
$ python test.py
{
  "second": {
    "c": "d",
    "a": "b"
  },
  "first": {
    "c": "d",
    "a": "b"
  }
}
Traceback (most recent call last):
  File "test.py", line 8, in <module>
    for doc in yaml.load_all(yfile.read()):
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/__init__.py", line 84, in load_all
    yield loader.get_data()
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/constructor.py", line 31, in get_data
    return self.construct_document(self.get_node())
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 27, in get_node
    return self.compose_document()
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 55, in compose_document
    node = self.compose_node(None, None)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 84, in compose_node
    node = self.compose_mapping_node(anchor)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 133, in compose_mapping_node
    item_value = self.compose_node(node, item_key)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 84, in compose_node
    node = self.compose_mapping_node(anchor)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 133, in compose_mapping_node
    item_value = self.compose_node(node, item_key)
  File "/home/cooldeveloper/.virtualenvs/tavern/lib/python3.5/site-packages/yaml/composer.py", line 69, in compose_node
    % anchor, event.start_mark)
yaml.composer.ComposerError: found undefined alias 'top_anchor'
  in "<unicode string>", line 12, column 7:
      <<: *top_anchor
```

This poses a bit of a problem for running our integration tests. If we want to
log in at the beginning of each test, or if we want to query some user
information which is then operated on for each test, we don't want to copy paste
the same code within the same file.

For this reason, Tavern will override the default YAML behaviour and preserve anchors
across documents **within the same file**. Then we can do something more like this:

```yaml
---
test_name: Make sure user location is correct

stages:
  - &test_user_login_anchor
    # Log in as user and save the login token for future requests
    name: Login as test user
    request:
      url: http://test.server.com/user/login
      method: GET
      json:
        username: test_user
        password: abc123
    response:
      status_code: 200
      save:
        json:
          test_user_login_token: token
      verify_response_with:
        function: tavern.testutils.helpers:validate_jwt
        extra_kwargs:
          jwt_key: "token"
          options:
            verify_signature: false

  - name: Get user location
    request:
      url: http://test.server.com/locations
      method: GET
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200
      json:
    location:
          road: 123 Fake Street
          country: England

---
test_name: Make sure giving premium works

stages:
  # Use the same block to log in across documents
  - *test_user_login_anchor

  - name: Assert user does not have premium
    request: &has_premium_request_anchor
      url: http://test.server.com/user_info
      method: GET
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200
      json:
        has_premium: false

  - name: Give user premium
    request:
      url: http://test.server.com/premium
      method: POST
      headers:
        Authorization: "Bearer {test_user_login_token}"
    response:
      status_code: 200

  - name: Assert user now has premium
    request:
      # Use the same block within one document
      <<: *has_premium_request_anchor
    response:
      status_code: 200
      json:
        has_premium: true
```


## Including external files

Even with being able to use anchors within the same file, there is often some
data which either you want to keep in a separate (possibly autogenerated) file,
or is used on every test (e.g. login information). You might also want to run the
same tests with different sets of input data.

Because of this, external files can also be included which contain simple
key: value data to be used in other tests.

Including a file in every test can be done by using a `!include` directive:

```yaml
# includes.yaml
---

# Each file should have a name and description
name: Common test information
description: Login information for test server

# Variables should just be a mapping of key: value pairs
variables:
  protocol: https
  host: www.server.com
  port: 1234
```

```yaml
# tests.tavern.yaml
---
test_name: Check server is up

includes:
  - !include includes.yaml

stages:
  - name: Check healthz endpoint
    request:
      method: GET
      url: "{protocol:s}://{host:s}:{port:d}"
    response:
      status_code: 200
```

As long as includes.yaml is in the same folder as the tests or found in the
TAVERN_INCLUDE search path, the variables will
automatically be loaded and available for formatting as before. Multiple include
files can be specified.

The environment variable TAVERN_INCLUDE can contain a : separated list of
paths to search for include files.  Each path in TAVERN_INCLUDE has
environment variables expanded before it is searched. 


### Including global configuration files

If you do want to run the same tests with a different input data, this can be
achieved by passing in a global configuration.

Using a global configuration file works the same as implicitly including a file
in every test. For example, say we have a server that takes a user's name and
address and returns some hash based on this information. We have two
servers that need to do this correctly, so we need two tests that use the same
input data but need to post to 2 different urls:

```yaml
# two_tests.tavern.yaml
---
test_name: Check server A responds properly

includes:
  - !include includesA.yaml

stages:
  - name: Check thing is processed correctly
    request:
      method: GET
      url: "{host:s}/"
      json: &input_data
        name: "{name:s}"
        house_number: "{house_number:d}"
        street: "{street:s}"
        town: "{town:s}"
        postcode: "{postcode:s}"
        country: "{country:s}"
        planet: "{planet:s}"
        galaxy: "{galaxy:s}"
        universe: "{universe:s}"
    response:
      status_code: 200
      json:
        hashed: "{expected_hash:s}"

---
test_name: Check server B responds properly

includes:
  - !include includesB.yaml

stages:
  - name: Check thing is processed correctly
    request:
      method: GET
      url: "{host:s}/"
      json:
        <<: *input_data
    response:
      status_code: 200
      json:
        hashed: "{expected_hash:s}"
```

Including the full set of input data in includesA.yaml and includesB.yaml would
mean that a lot of the same input data would be repeated. To get around this, we
can define a file called, for example, `common.yaml` which has all the input
data except for `host` in it, and make sure that includesA/B only have the
`host` variable in:

```yaml
# common.yaml
---

name: Common test information
description: |
  user location information for Joe Bloggs test user

variables:
  name: Joe bloggs
  house_number: 123
  street: Fake street
  town: Chipping Sodbury
  postcode: BS1 2BC
  country: England
  planet: Earth
  galaxy: Milky Way
  universe: A
  expected_hash: aJdaAK4fX5Waztr8WtkLC5
```

```yaml
# includesA.yaml
---

name: server A information
description: server A specific information

variables:
  host: www.server-a.com
```

```yaml
# includesB.yaml
---

name: server B information
description: server B specific information

variables:
  host: www.server-B.io
```

If the behaviour of server A and server B ever diverge in future, information
can be moved out of the common file and into the server specific include
files.

Using the `tavern-ci` tool or pytest, this global configuration can be passed in
at the command line using the `--tavern-global-cfg` flag. The variables in
`common.yaml` will then be available for formatting in *all* tests during that
test run.

**NOTE**: `tavern-ci` is just an alias for `py.test` and
will take the same options.

```
# These will all work
$ tavern-ci --tavern-global-cfg=integration_tests/local_urls.yaml
$ tavern-ci --tavern-global-cfg integration_tests/local_urls.yaml
$ py.test --tavern-global-cfg=integration_tests/local_urls.yaml
$ py.test --tavern-global-cfg integration_tests/local_urls.yaml
```

It might be tempting to put this in the 'addopts' section of the pytest.ini file
to always pass a global configuration when using pytest, but be careful when
doing this - due to what appears to be a bug in the pytest option parsing, this
might not work as expected:

```ini
# pytest.ini
[pytest]
addopts =
    # This will work
    --tavern-global-cfg=integration_tests/local_urls.yaml
    # This will not!
    # --tavern-global-cfg integration_tests/local_urls.yaml
```

Instead, use the `tavern-global-cfg` option in your pytest.ini file:

```ini
[pytest]
tavern-global-cfg=
    integration_tests/local_urls.yaml
```

### Multiple global configuration files

Sometimes you will want to have 2 (or more) different global configuration
files, one containing common information such as paths to different resources
and another containing information specific to the environment that is being
tested. Multiple global configuration files can be specified either on the
command line or in pytest.ini to avoid having to put an `!include` directive in
every test:

```
# Note the '--' after all global configuration files are passed, indicating that
# arguments after this are not global config files
$ tavern-ci --tavern-global-cfg common.yaml test_urls.yaml -- test_server.tavern.yaml
$ py.test --tavern-global-cfg common.yaml local_docker_urls.yaml -- test_server.tavern.yaml
```
```ini
# pytest.ini
[pytest]
tavern-global-cfg=
    common.yaml
    test_urls.yaml
```

### Sharing stages in configuration files

If you have a stage that is shared across a huge number of tests and it
is infeasible to put all the tests which share that stage into one file,
you can also define stages in configuration files and use them in your
tests.

Say we have a login stage that needs to be run before every test in our
test suite. Stages are defined in a configuration file like this:

```yaml
# auth_stage.yaml
---

name: Authentication stage
description:
  Reusable test stage for authentication

variables:
  user:
    user: test-user
    pass: correct-password

stages:
  - id: login_get_token
    name: Login and acquire token
    request:
      url: "{service:s}/login"
      json:
        user: "{user.user:s}"
        password: "{user.pass:s}"
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      headers:
        content-type: application/json
      save:
        json:
          test_login_token: token
```

Each stage should have a uniquely identifiable `id`, but other than that
the stage can be define just as other tests (including using format
variables).

This can be included in a test by specifying the `id` of the test like
this:

```yaml
---

test_name: Test authenticated /hello

includes:
  - !include auth_stage.yaml

stages:
  - type: ref
    id: login_get_token
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
        data: "Hello, Jim"

```

### Directly including test data

If your test just has a huge amount of data that you would like to keep
in a separate file, you can also (ab)use the `!include` tag to directly
include data into a test. Say we have a huge amount of JSON that we want
to send to a server and we don't want hundreds of lines in the test:

```json
// test_data.json
[
  {
    "_id": "5c965b1373f3fe071a9cb2b7",
    "index": 0,
    "guid": "ef3f8c42-522a-4d6b-84ec-79a07009460d",
    "isActive": false,
    "balance": "$3,103.47",
    "picture": "http://placehold.it/32x32",
    "age": 26,
    "eyeColor": "green",
    "name": "Cannon Wood",
    "gender": "male",
    "company": "CANDECOR",
    "email": "cannonwood@candecor.com",
    "phone": "+1 (944) 549-2826",
    "address": "528 Woodpoint Road, Snowville, Kansas, 140",
    "about": "Dolore in consequat exercitation esse esse velit eu velit aliquip ex. Reprehenderit est consectetur excepteur sint sint dolore. Anim minim dolore est ut fugiat. Occaecat tempor tempor mollit dolore anim commodo laboris commodo aute quis ex irure voluptate. Sunt magna tempor veniam cillum exercitation quis minim est eiusmod aliqua.\r\n",
    "registered": "2015-12-27T11:30:18 -00:00",
    "latitude": -2.515302,
    "longitude": -98.678105,
    "tags": [
      "proident",
      "aliqua",
      "velit",
      "labore",
      "consequat",
      "esse",
      "ea"
    ],
    "friends": [
      {
        "id": 0,
        "etc": []
      }
    ]
  }
]
```

(Handily generated by [JSON Generator](https://www.json-generator.com/))

Putting this whole thing into the test would be a bit overkill, but it
can be inject directly into your test like this:

```yaml
---

test_name: Post a lot of data

stages:
  - name: Create new user
    request:
      url: "{service:s}/new_user"
      method: POST
      json: !include test_data.json
    response:
      status_code: 201
      json:
        status: user created
```

This works with YAML as well, the only caveat being that the filename
_must_ end with `.yaml`, `.yml`, or `.json`.

## Using the run() function

Because the `run()` function (see [examples](/examples)) calls directly into the
library, there is no nice way to control which global configuration to use - for
this reason, you can pass a dictionary into `run()` which will then be used as
global configuration. This should have the same structure as any other global
configuration file:

```python
from tavern.core import run

extra_cfg = {
    "variables": {
        "key_1": "value",
        "key_2": 123,
    }
}

success = run("test_server.tavern.yaml", extra_cfg)
```

An absolute filepath to a configuration file can also be passed.

This is also how things such as strict key checking is controlled via the
`run()` function. Extra keyword arguments that are taken by this function:

- `tavern_strict` - Controls strict key checking (see section on strict key
  checking for details)
- `tavern_mqtt_backend` and `tavern_http_backend` controls which backend to use
  for those requests (see [plugins](/plugins) for details)
- `pytest_args` - A list of any extra arguments you want to pass directly
  through to Pytest.

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

## Matching arbitrary return values in a response

Sometimes you want to just make sure that a value is returned, but you don't
know (or care) what it is. This can be achieved by using `!anything` as the
value to match in the **response** block:

```yaml
response:
  json:
    # Will assert that there is a 'returned_uuid' key, but will do no checking
    # on the actual value of it
    returned_block: !anything
```

This would match both of these response bodies:

```yaml
returned_block: hello
```
```yaml
returned_block:
  nested: value
```

Using the magic `!anything` value should only ever be used inside pre-defined
blocks in the response block (for example, `headers`, `params`, and `json` for a
HTTP response).

**NOTE**: Up until version 0.7.0 this was done by setting the value as `null`.
This creates issues if you want to ensure that your server is actually returning
a null value. Using `null` is still supported in the current version of Tavern,
but will be removed in a future release, and should raise a warning.

### Matching arbitrary specific types in a response

If you want to make sure that the key returned is of a specific type, you can
use one of the following markers instead:

- `!anyint`: Matches any integer
- `!anyfloat`: Matches any float (note that this will NOT match integers!)
- `!anystr`: Matches any string
- `!anybool`: Matches any boolean (this will NOT match `null`)
- `!anylist`: Matches any list
- `!anydict`: Matches any dict/'mapping'

### Matching via a regular expression

Sometimes you know something will be a string, but you also want to make sure
that the string matches some kind of regular expression. This can be done using
external functions, but as a shorthand there is also the `!re_` family of custom
YAML tags that can be used to match part of a response. Say that we want to make
sure that a UUID returned is a
[version 4 UUID](https://tools.ietf.org/html/rfc4122#section-4.1.3), where the
third block must start with 4 and the third block must start with 8, 9, "A", or
"B".

```yaml
  - name: Check that uuidv4 is returned
    request:
      url: {host}/get_uuid/v4
      method: GET
    response:
      status_code: 200
      json:
        uuid: !re_fullmatch "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89AB][0-9a-f]{3}-[0-9a-f]{12}"
```

This is using the `!re_fullmatch` variant of the tag - this calls
[`re.fullmatch`](https://docs.python.org/3.7/library/re.html#re.fullmatch) under
the hood, which means that the regex given needs to match the _entire_ part of
the response that is being checked for it to pass. There is also `!re_search`
which will pass if it matches _part_ of the thing being checked, or `!re_match`
which will match _part_ of the thing being checked, as long as it is at the
_beginning_ of the string. See the Python documentation for more details.

Another way of doing this is to use the builtin `validate_regex` helper function.
For example if we want to get a version that is returned in a 'meta' key in the
format `v1.2.3-510c2665d771e1`:

```yaml
stages:
- name: get a token by id
  request:
    url: "{host}/tokens/get"
    method: GET
    params:
      id: 456
  response:
    status_code: 200
    json:
      code: abc123
      id: 456
      meta:
        version: !anystr
        hash: 456
    save:
      $ext:
        function: tavern.testutils.helpers:validate_regex
        extra_kwargs:
          expression: "v(?P<version>[\d\.]+)-[\w\d]+"
          in_jmespath: "meta.version"
```

This is a more flexible version of the helper which can also be used to save values
as in the example. If a named matching group is used as shown above, the saved values
 can then be accessed in subsequent stages by using the `regex.<group-name>` syntax, eg: 

```yaml
- name: Reuse thing specified in first request
  request:
    url: "{host}/get_version_info"
    method: GET
    params:
      version: "{regex.version}"
  response:
    status_code: 200
    json:
      simple_version: "v{regex.version}"
      made_on: "2020-02-21"
```

## Type conversions

[YAML](http://yaml.org/spec/1.1/current.html#id867381) has some magic variables
that you can use to coerce variables to certain types. For example, if we want
to write an integer but make sure it gets converted to a string when it's
actually sent to the server we can do something like this:

```yaml
request:
  json:
    an_integer: !!str 1234567890
```

However, due to the way YAML is loaded this doesn't work when you are using a
formatted value. Because of this, Tavern provides similar special constructors
that begin with a *single* exclamation mark that will work with formatted
values. Say we want to convert a value from an included file to an integer:

```yaml
request:
  json:
    # an_integer: !!int "{my_integer:d}" # Error
    an_integer: !int "{my_integer:d}" # Works
```

Because curly braces are automatically formatted, trying to send one
in a string might cause some unexpected issues. This can be mitigated
by using the `!raw` tag, which will not perform string formatting.

*Note*: This is just shorthand for replacing a `{` with a `{{` in the
string

```yaml
request:
  json:
    # Sent as {"raw_braces": "{not_escaped}"}
    raw_braces: !raw "{not_escaped}"
```

### Including raw JSON data

Sometimes there are situations where you need to directly include a block of
JSON, such as a list, rather than just one value. To do this, there is a
`!force_original_structure` tag which will include whatever variable is being
referenced in the format block rather than coercing it to a string.

For example, if we have an API that will return a list of users on a GET and
will bulk delete a list of users on a DELETE, a test that all users are deleted
could be done by

1. GET all users

2. DELETE the list you just got

3. GET again and expect an empty list

```yaml
  - name: Get all users
    request:
      url: "{host}/users"
      method: GET
    response:
      status_code: 200
      # Expect a list of users
      json: !anylist
      save:
        json:
          # Save the list as 'all_users'
          all_users: "@"

  - name: delete all users
    request:
      url: "{host}/users"
      method: DELETE
      # 'all_users' list will be sent in the request as a list, not a string
      json: !force_original_structure "{all_users}"
    response:
      status_code: 204

  - name: Get no users
    request:
      url: "{host}/users"
      method: GET
    response:
      status_code: 200
      # Expect no users
      json: []
```

Any blocks of JSON that are included this way will not be recursively formatted.
When using this token, do not use a conversion specifier (eg "{all_users:s}") as
it will be ignored.

## Adding a delay between tests

Sometimes you might need to wait for some kind of uncontrollable external event
before moving on to the next stage of the test. To wait for a certain amount of time
before or after a test, the `delay_before` and `delay_after` keys can be used.
Say you have an asynchronous task running after sending a POST message with a
user id - an example of using this behaviour:

```yaml
---
test_name: Make sure asynchronous task updates database

stages:
  - name: Trigger task
    request:
      url: https://example.com/run_intensive_task_in_background
      method: POST
      json:
        user_id: 123
    # Server responds instantly...
    response:
      status_code: 200
    # ...but the task takes ~3 seconds to complete
    delay_after: 5

  - name: Check task has triggered
    request:
      url: https://example.com/check_task_triggered
      method: POST
      json:
        user_id: 123
    response:
      status_code: 200
      json:
        task: completed
```

Having `delay_before` in the second stage of the test is semantically identical
to having `delay_after` in the first stage of the test - feel free to use
whichever seems most appropriate.

A saved/config variable can be used by using a type token conversion, such as:

```yaml
stages:
  - name: Trigger task
    ...
    delay_after: !float "{sleep_time}"
```

## Retrying tests

If you are not sure how long the server might take to process a request, you can
also retry a stage a certain number of times using `max_retries`:

```yaml
---
test_name: Poll until server is ready

includes:
  - !include common.yaml

stages:
  - name: polling
    max_retries: 1
    request:
      url: "{host}/poll"
      method: GET
    response:
      status_code: 200
      json:
        status: ready
```

This example will perform a `GET` request against `/poll`, and if it does not
return the expected response, will try one more time, _immediately_. To wait
before retrying a request, combine `max_retries` with `delay_after`.

**NOTE**: You should think carefully about using retries when making a request
that will change some state on the server or else you may get nondeterministic
test results.

MQTT tests can be retried as well, but you should think whether this
is what you want - you could also try increasing the timeout on an expected MQTT
response to achieve something similar.

## Marking tests

Since 0.11.0, it is possible to 'mark' tests. This uses Pytest behind the
scenes - see the [pytest mark documentation](https://docs.pytest.org/en/latest/example/markers.html)
for details on their implementation and prerequisites for use.

In short, marks can be used to:

- Select a subset of marked tests to run from the command line
- Skip certain tests based on a condition
- Mark tests as temporarily expected to fail, so they can be fixed later

An example of how these can be used:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - slow

stages:
  - name: Get info
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000

---
test_name: Get server info from fast endpoint

marks:
  - fast

stages:
  - name: Get info
    request:
      url: "{host}/get-info"
      method: GET
    response:
      status_code: 200
      json:
        n_items: 2048
        n_queries: 5
```

Both tests get some server information from our endpoint, but one requires a lot
of backend processing so we don't want to run it on every test run. This can be
selected like this:

```shell
$ py.test -m "not slow"
```

Conversely, if we just want to run all tests marked as 'fast', we can do this:

```shell
$ py.test -m "fast"
```

Marks can only be applied to a whole test, not to individual stages (with the
exception of `skip`, see below).

### Formatting marks

Marks can be formatted just like other variables:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - "{specialmarker}"
```

This is mainly for combining with one or more of the special marks as mentioned
below.

**NOTE**: Do _not_ use the `!raw` token or rely on double curly brace formatting
when formatting markers. Due to pytest-xdist, some behaviour with the formatting
of markers is subtly different than other places in Tavern.

### Special marks

There are 4 different 'special' marks from Pytest which behave the same as if
they were used on a Python test.

**NOTE**: If you look in the Tavern integration tests, you may notice a `_xfail`
key being used in some of the tests. This is for INTERNAL USE ONLY and may be
removed in future without warning.

#### skip

To always skip a test, just use the `skip` marker:

```yaml
...

marks:
  - skip
```

Separately from the markers, individual stages can be skipped by inserting the
`skip` keyword into the stage:

```yaml
stages:
  - name: Get info
    skip: True
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000
```

#### skipif

Sometimes you just want to skip some tests, perhaps based on which server you're
using. Taking the above example of the 'slow' server, perhaps it is only slow
when running against the live server at `www.slow-example.com`, but we still want to
run it in our local tests. This can be achieved using `skipif`:

```yaml
---
test_name: Get server info from slow endpoint

marks:
  - slow
  - skipif: "'slow-example.com' in '{host}'"

stages:
  - name: Get info
    request:
      url: "{host}/get-info-slow"
      method: GET
    response:
      status_code: 200
      json:
        n_users: 2048
        n_queries: 10000
```

`skipif` should be a mapping containing 1 key, a string that will be directly
passed through to `eval()` and should return `True` or `False`. This string will
be formatted first, so tests can be skipped or not based on values in the
configuration. Because this needs to be a valid piece of Python code, formatted
strings must be escaped as in the example above - using `"'slow-example.com' in
{host}"` will raise an error.

#### xfail

If you are expecting a test to fail for some reason, such as if it's temporarily
broken, a test can be marked as `xfail`. Note that this is probably not what you
want to 'negatively' check something like an API deprecation. For example, this
is not recommended:

```yaml
---
test_name: Get user middle name from endpoint on v1 api

stages:
  - name: Get from endpoint
    request:
      url: "{host}/api/v1/users/{user_id}/get-middle-name"
      method: GET
    response:
      status_code: 200
      json:
        middle_name: Jimmy

---
test_name: Get user middle name from endpoint on v2 api fails

marks:
  - xfail

stages:
  - name: Try to get from v2 api
    request:
      url: "{host}/api/v2/users/{user_id}/get-middle-name"
      method: GET
    response:
      status_code: 200
      json:
        middle_name: Jimmy
```

It would be much better to write a test that made sure that the endpoint just
returned a `404` in the v2 api.

#### parametrize

A lot of the time you want to make sure that your API will behave properly for a
number of given inputs. This is where the parametrize mark comes in:

```yaml
---
test_name: Make sure backend can handle arbitrary data

marks:
  - parametrize:
      key: metadata
      vals:
        - 13:00
        - Reading: 27 degrees
        - 手机号格式不正确
        - ""

stages:
  - name: Update metadata
    request:
      url: "{host}/devices/{device_id}/metadata"
      method: POST
      json:
        metadata: "{metadata}"
    response:
      status_code: 200
```

This test will be run 4 times, as 4 separate tests, with `metadata` being
formatted differently for each time. This behaves like the built in Pytest
`parametrize` mark, where the tests will show up in the log with some extra data
appended to show what was being run, eg `Test Name[John]`, `Test Name[John-Smythe John]`, etc.

The `parametrize` mark should be a mapping with `key` being the value that will
be formatted and `vals` being a list of values to be formatted. Note that
formatting of these values happens after checking for a `skipif`, so a `skipif`
mark cannot rely on a parametrized value.

Multiple marks can be used to parametrize multiple values:

```yaml
---
test_name: Test post a new fruit

marks:
  - parametrize:
      key: fruit
      vals:
        - apple
        - orange
        - pear
  - parametrize:
      key: edible
      vals:
        - rotten
        - fresh
        - unripe

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{edible} {fruit}"
    response:
      status_code: 201
```

This will result in 9 tests being run:

- rotten apple
- rotten orange
- rotten pear
- fresh apple
- fresh orange
- etc.

If you need to parametrize multiple keys but don't want there to be a new test
created for every possible combination, pass a list to `key` instead. Each item
in `val` must then also be a list that is _the same length as the `key`
variable_. Using the above example, perhaps we just want to test the server
works correctly with the items "rotten apple", "fresh orange", and "unripe pear"
rather than the 9 combinations listed above. This can be done like this:


```yaml
---
test_name: Test post a new fruit

marks:
  - parametrize:
      key:
        - fruit
        - edible
      vals:
        - [rotten, apple]
        - [fresh, orange]
        - [unripe, pear]
        # NOTE: we can specify a nested list like this as well:
        # -
        #   - unripe
        #   - pear

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{edible} {fruit}"
    response:
      status_code: 201
```

This will result in only those 3 tests being generated.

This can be combined with the 'simpler' style of parametrisation as well - for
example, to run the above test but also to specify whether the fruit was
expensive or cheap:


```yaml
---
test_name: Test post a new fruit and price

marks:
  - parametrize:
      key:
        - fruit
        - edible
      vals:
        - [rotten, apple]
        - [fresh, orange]
        - [unripe, pear]
  - parametrize:
      key: price
      vals:
        - expensive
        - cheap

stages:
  - name: Create a new fruit entry
    request:
      url: "{host}/fruit"
      method: POST
      json:
        fruit_type: "{price} {edible} {fruit}"
    response:
      status_code: 201
```

This will result in 6 tests:

- expensive rotten apple
- expensive fresh orange
- expensive unripe pear
- cheap rotten apple
- cheap fresh orange
- cheap unripe pear

**NOTE**: Due to implementation reasons it is currently impossible to
parametrize either the HTTP method or the MQTT QoS parameter.

#### usefixtures

Since 0.15.0 there is limited support for Pytest
[fixtures](https://docs.pytest.org/en/latest/fixture.html) in Tavern tests. This
is done by using the `usefixtures` mark. The return (or `yield`ed) values of any
fixtures will be available to use in formatting, using the name of the fixture.

An example of how this can be used in a test:

```python
# conftest.py

import pytest
import logging
import time

@pytest.fixture
def server_password():
    with open("/path/to/password/file", "r") as pfile:
        password = pfile.read().strip()

    return password

@pytest.fixture(name="time_request")
def fix_time_request():
    t0 = time.time()

    yield

    t1 = time.time()

    logging.info("Test took %s seconds", t1 - t0)
```

```yaml
---
test_name: Make sure server can handle a big query

marks:
  - usefixtures:
      - time_request
      - server_password

stages:
  - name: Do big query
    request:
      url: "{host}/users"
      method: GET
      params:
        n_items: 1000
      headers:
        authorization: "Basic {server_password}"
    response:
      status_code: 200
      json:
        ...
```

The above example will load basic auth credentials from a file, which will be
used to authenticate against the server. It will also time how long the test
took and log it.

`usefixtures` expects a list of fixture names which are then loaded by Pytest -
look at their documentation to see how discovery etc. works.

There are some limitations on fixtures:

- Fixtures are per _test_, not per stage. The above example of timing a test
  will include the (small) overhead of doing validation on the responses,
  setting up the requests session, etc. If the test consists of more than one
  stage, it will time how long both stages took.
- Fixtures should be 'function' or 'session' scoped. 'module' scoped fixtures
  will raise an error and 'class' scoped fixtures may not behave as you expect.
- Parametrizing fixtures does not work - this is a limitation in Pytest.

Fixtures which are specified as `autouse` can also be used without explicitly
using `usefixtures` in a test. This is a good way to essentially precompute a
format variable without also having to use an external function or specify a
`usefixtures` block in every test where you need it. 

To do this, just pass the `autouse=True` parameter to your fixtures along with
the relevant scope. Using 'session' will evalute the fixture once at the beginning
of your test run and reuse the return value everywhere else it is used:

```python
@pytest.fixture(scope="session", autouse=True)
def a_thing():
    return "abc"
```

```yaml
---
test_name: Test autouse fixture

stages:
  - name: do something with fixture value
    request:
      url: "{host}/echo"
      method: POST
      json:
        value: "{a_thing}"
```

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

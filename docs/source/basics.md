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
      body:
        id: 1
      save:
        body:
          returned_id: id
```

If using the pytest plugin (the recommended way of using Tavern), this needs to
be in a file called `test_x.tavern.yaml`, where `x` is a description of the
contained tests.

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
- `body` - Assuming the response is json, check the body against the values
  given. Expects a mapping (possibly nested) key: value pairs/lists.
  This can also use an external check function, described further down.
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
    body:
      fourth_val: thing.nested.0
```

It is also possible to save data using function calls, explained below.

For a more formal definition of the schema that the tests are validated against,
check `tavern/schemas/tests.schema.yaml` in the main Tavern repository.

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
    variable_key: "{key_name}"
```

This is formatted using Python's [string formatting
syntax](https://docs.python.org/2/library/string.html#format-string-syntax). The
variable to be used is encased in curly brackets and an optional
[type code](https://docs.python.org/2/library/string.html#format-specification-mini-language)
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
      body:
        user_id: "{tavern.request_vars.params.user_id}"
        new_welcome_message: "{tavern.request_vars.json.message}"
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
      body:
        error: "No authorization"

  - name: Get information with admin token
    request:
      method: GET
      url: "www.example.com/get_info"
      headers:
        Authorization: "Basic {tavern.env_vars.SECRET_CI_COMMIT_AUTH}"
    response:
      status_code: 200
      body:
        name: "Joe Bloggs"
```

## Calling external functions

Not every response can be validated simply by checking the values of keys, so with
Tavern you can call external functions to validate responses and save decoded data.
You can write your own functions or use those built in to Tavern. Each function
should take the response as its first argument, and you can pass extra arguments
using the **extra_kwargs** key.

### Built-in validators

There are two external functions built in to Tavern: `validate_jwt` and
`validate_pykwalify`.

`validate_jwt` takes the key of the returned JWT in the body as `jwt_key`, and
additional arguments that are passed directly to the `decode` method in the
[PyJWT](https://github.com/jpadilla/pyjwt/blob/master/jwt/api_jwt.py#L59)
library. **NOTE: Make sure the keyword arguments you are passing are correct
or PyJWT will silently ignore them. In thr future, this function will likely be
changed to use a different library to avoid this issue.**

```yaml
# Make sure the response contains a key called 'token', the value of which is a
# valid jwt which is signed by the given key.
response:
  body:
    $ext:
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
  body:
    $ext:
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

### Saving data with external functions

An external function can also be used to save data from the response. To do this,
the function must return a dict where each key either points to a single value or
to an object which is accessible using dot notation. The easiest way to do this
is to return a [Box](https://pypi.python.org/pypi/python-box/) object. Each key in
the returned object will be saved as if it had been specified separately in the
**save** object. The function is called in the same way as a validator function,
in the **$ext** key of the **save** object.

Say that we have a server which returns a response like this:

```json
{
    "user": {
        "name": "John Smith",
        "id": "abcdef12345",
    }
}
```

If our test function extracts the key `name` from the response body:

```python
# utils.py
def test_function(response):
    return {"test_user_name": response.json()["user"]["name"]}
```

We would use it in the **save** object like this:

```yaml
save:
  $ext:
    function: utils:test_function
  body:
    test_user_id: user.id
```

In this case, both `{test_user_name}` and `{test_user_id}` are available for use
in later requests.

To make sure that Tavern can find this test function you need to make sure that
it is in the Python path. For example, if `utils.py` is in the 'tests' folder,
you will need to run your tests something like (on Linux):

```shell
$ PYTHONPATH=$PYTHONPATH:tests py.test tests/
```

For a more practical example, the built in `validate_jwt` function also returns the
decoded token as a dictionary wrapped in a [Box]
(https://pypi.python.org/pypi/python-box/) object, which allows dot-notation
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
    body:
      # Make sure a token exists
      $ext:
        function: tavern.testutils.helpers:validate_jwt
        extra_kwargs:
          jwt_key: "token"
          options:
            verify_signature: false
    save:
      # Saves a jwt token returned as 'token' in the body as 'jwt'
      # in the test configuration for use in future tests
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

**NOTE**: At the time of writing, Tavern will by default not perform 'strict'
key checking on the top level keys in the response, but will perform it on all
keys below that. This 'legacy' behaviour will be changed in a future version, see below for details.

'Strict' key checking can be enabled or disabled globally, per test, or per
stage. 'Strict' key checking refers to whether extra keys in the response should
be ignored or whether they should raise an error. There are currently 3 levels
of strict checking in Tavern, which only apply to HTTP tests. With strict key
checking enabled, all keys in dictionaries at all levels have to match or it
will raise an error. With it disabled, Extra keys in the response will be
ignored. If it is not set at all, 'legacy' behaviour is used.

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
  body:
    first: 1
    second:
      nested: 2
```

The behaviour of various levels of 'strictness' based on the response:


| Response | True | False | 'legacy' |
| ---- | -------- | ------ | ------- |
| `{ "first": 1, "second": { "nested": 2 } }`  | PASS | PASS | PASS |
| `{ "first": 1 }`  | FAIL | PASS | PASS |
| `{ "first": 1, "second": { "another": 2 } }`  | FAIL | FAIL | FAIL |
| `{ "first": 1, "second": { "nested": 2, "another": 2 } }`  | FAIL | PASS | FAIL |


As you can see from the table, the 'legacy' behaviour only cares about keys
below the top level which was a design flaw. This behaviour will be removed in a
future version, but has been left in for the time being to maintain backwards
compatability.

The strictness setting does not only apply to the body however, it can also be
used on the headers and redirect query parameters.

This setting can be controlled in 3 different ways, the order of priority being:

1. In the test/stage itself
2. Passed on the command line
3. Read from pytest config

This means that using the command line option will _not_ override any settings
for specific tests.

**NOTE**: 'strict' key checking can currently only be _enabled_ via the command line
and the pytest config file, not _disabled_.

### Command line

There is a command line argument, `--tavern-strict`, which controls the default
global strictness setting. If not set, this uses the 'legacy' behaviour - in
future, this will default to 'strict' key checking being disabled. This is
mainly because a lot of web programs will return a huge number of headers which
you don't want to include in every test, and when checking the body you normally
only want to check that it returns the data you want and not care about any
extra metadata sent with the response. This can be re-enabled per test or per
stage if wanted.

```shell
# Enable strict checking for body and headers only
py.test --tavern-strict body headers -- my_test_folder/
```

### In the Pytest config file

This behaves identically to the command line option, but will be read from
whichever configuration file Pytest is using.

```editorconfig
[pytest]
tavern-strict=body headers
```

### Per test

Strictness can also be enabled or disabled on a per-test basis. The `strict` key
at the top level of the test should be one of `body`, `headers`, or
`redirect_query_params`, or a list consisting of a combination of the three.

```yaml
---

test_name: Make sure the headers match what I expect exactly

strict: headers

# This can also be done like this:
# strict:
#   - headers

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
      body:
        id: 1
---

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
      body:
        q:
          x:
            z:
              a: 1
---

test_name: Make sure the headers and body match what I expect exactly

strict:
  - headers
  - body

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
      body:
        id: 1
        first_name: joe
        last_name: bloggs
        email: joe@bloggs.com
```

### Per stage

Often you have a standard stage before other stages, such as logging in to your
server, where you only care if it returns a 200 to indicate that you're logged
in. To facilitate this, you can enable or disable strict key checking on a
per-stage basis as well.

Two examples for doing this - these examples should behave identically:

```yaml
---

# Enable strict checking for this test, but disable it for the login stage

test_name: Login and create a new user

strict:
  - body

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
      body:
        <<: *create_user
        id: 1
```

```yaml
---

# Enable strict checking only for the second stage (assuming strict checking is
# globally disabled).

test_name: Login and create a new user

stages:
  - name: log in
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
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
      strict: body
      body:
        <<: *create_user
        id: 1
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
        body:
          test_user_login_token: token
      body:
        $ext:
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
      body:
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
      body:
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
      body:
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

As long as includes.yaml is in the same folder as the tests, the variables will
automatically be loaded and available for formatting as before. Multiple include
files can be specified.

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
      body:
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
      body:
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

**NOTE**: `tavern-ci` uses argparse to read this from the command line:

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
# stage_auth.yaml
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
        body:
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
  - name: Unauthenticated /hello
    request:
      url: "{service:s}/hello/Jim"
      method: GET
    response:
      status_code: 401
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
      body:
        data: "Hello, Jim"

```

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
  body:
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
blocks in the response block (for example, `headers`, `params`, and `body` for a
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
    an_integer: !!int "{my_integer:d}" # Error
    an_integer: !int "{my_integer:d}" # Works
```

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
      body:
        task: completed
```

Having `delay_before` in the second stage of the test is semantically identical
to having `delay_after` in the first stage of the test - feel free to use
whichever seems most appropriate.

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
      body:
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

**The section on marking tests only applies if you are using Pytest**

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
      body:
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
      body:
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

### Special marks

There are 4 different 'special' marks from Pytest which behave the same as if
they were used on a Python test.

**NOTE**: If you look in the Tavern integration tests, you may notice a
`_xfail` key being used in some of the tests. This is for INTERNAL USE ONLY and
may be removed in future without warning.

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
      body:
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
      body:
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
      body:
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
      body:
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

The `parametrize` make should be a mapping with `key` being the value that will
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
      body:
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

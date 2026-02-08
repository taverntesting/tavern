# Core Concepts

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


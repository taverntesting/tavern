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
check [tests schema](https://github.com/taverntesting/tavern/blob/5e2597ae4c0d7023f08e7c8e793c6db57ee546cf/tavern/_core/schema/tests.jsonschema.yaml)
in the main Tavern repository.

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

**NOTE**: This is a toy example, if you want to use GraphQL with tavern then 
head over to the [GraphQL docs](./graphql.md).

Since `0.5.0`, Tavern also has some 'magic' variables available in the `tavern`
key for formatting.

### Request variables

This currently includes all request variables and is available under the
`request_vars` key. Say we want to test a server that updates a user's profile
and returns the change:

```yaml
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

```yaml
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

### Default document merge-down

When multiple tests are defined in a single Tavern file, you may want to share common configuration across all tests
without repeating it. Tavern supports this via the `is_defaults: true` flag in a top-level document. Any document with
this flag set will have its contents merged into all subsequent test documents in the same file.

This is useful for:

- Shared includes (common variables, stages, or configuration)
- Default MQTT connection settings
- Common authentication or headers
- Shared test setup stages

#### Example: Shared includes and configuration

```yaml
---
is_defaults: true

includes:
  - !include common.yaml

paho-mqtt:
  auth:
    username: tavern
    password: tavern
  connect:
    host: localhost
    port: 9001
  client:
    transport: websockets
---

test_name: Test mqtt message echo json

stages:
  - name: Echo json
    mqtt_publish:
      topic: /device/test/echo
      json:
        message: hello world
    mqtt_response:
      topic: /device/test/echo/response
      json:
        message: hello world
      timeout: 5
---

test_name: Test mqtt message echo binary

stages:
  - name: Echo binary
    mqtt_publish:
      topic: /device/test/echo
      payload: hello world
    mqtt_response:
      topic: /device/test/echo/response
      payload: hello world
      timeout: 5
```

In this example, both tests inherit the MQTT connection settings and includes from the defaults document, avoiding
duplication.

#### Example: Shared HTTP test configuration

```yaml
---
is_defaults: true

includes:
  - !include common.yaml
---

test_name: Test redirecting loops

stages:
  - name: Expect a 302 without setting the flag
    max_retries: 2
    request:
      follow_redirects: true
      url: "{host}/redirect/loop"
    response:
      status_code: 200

---

test_name: Using a shared stage from common.yaml

stages:
  - type: ref
    id: typetoken-anything-match
```

Both tests automatically include the shared configuration from `common.yaml` without needing to specify it individually.

Note:

- Only the first document in a file can use `is_defaults: true`
- The defaults document cannot contain test definitions (no `test_name` or `stages`)
- Values in the defaults document are merged with subsequent documents, with the test document taking precedence for
  conflicting keys

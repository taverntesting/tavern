# HTTP integration testing

The things specified in this section are only applicable if you are using Tavern
to test a HTTP API (ie, unless you are specifically checking MQTT or some other plugin).

## Using multiple status codes

If the server you are contacting might return one of a few different status
codes depending on it's internal state, you can write a test that has a list of
status codes in the expected response.

Say for example we want to try and get a user's details from a server - if it
exists, it returns a 200. If not, it returns a 404. We don't care which one, as
long as it it only one of those two codes.

```yaml
---

test_name: Make sure that the server will either return a 200 or a 404

stages:
  - name: Try to get user
    request:
      url: "{host}/users/joebloggs"
      method: GET
    response:
      status_code:
        - 200
        - 404
```

Note that there is no way to do something like this for the body of the
response, so unless you are expecting the same response body for every possible
status code, the `body` key should be left blank.

## Sending form encoded data

Though Tavern can only currently verify JSON data in the response, data can be
sent using `x-www-form-urlencoded` encoding by using the `data` key instead of
`json` in a request. An example of sending form data rather than json:

```yaml
    request:
      url: "{test_host}/form_data"
      method: POST
      data:
        id: abc123
```

## Authorisation

### Persistent cookies

Tavern uses
[requests](http://docs.python-requests.org/en/master/api/#requests.request)
under the hood, and uses a persistent `Session` for each test. This means that
cookies are propagated forward to further stages of a test. Cookies can also be
required to pass a test. For example, say we have a server that returns a cookie
which then needs to be used for future requests:

```yaml
---

test_name: Make sure cookie is required to log in

includes:
  - !include common.yaml

stages:
  - name: Try to check user info without login information
    request:
      url: "{host}/userinfo"
      method: GET
    response:
      status_code: 401
      body:
        error: "no login information"
      headers:
        content-type: application/json

  - name: login
    request:
      url: "{host}/login"
      json:
        user: test-user
        password: correct-password
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      cookies:
        - session-cookie
      headers:
        content-type: application/json

  - name: Check user info
    request:
      url: "{host}/userinfo"
      method: GET
    response:
      status_code: 200
      body:
        name: test-user
      headers:
        content-type: application/json
```

This test ensures that a cookie called `session-cookie` is returned from the
'login' stage, and this cookie will be sent with all future stages of that test.

### HTTP Basic Auth

For a server that expects HTTP Basic Auth, the `auth` keyword can be used in the
request block. This expects a list of two items - the first item is the user
name, and the second name is the password:

```yaml
---

test_name: Check we can access API with HTTP basic auth

includes:
  - !include common.yaml

stages:
  - name: Get user info
    request:
      url: "{host}/userinfo"
      method: GET
      auth:
        - user@api.com
        - password123
    response:
      status_code: 200
      body:
        user_id: 123
      headers:
        content-type: application/json
```

### Custom auth header

If you're using a form of authorisation not covered by the above two examples to
authorise against your test server (for example, a JWT-based system), specify a
custom `Authorization` header. If you are using a JWT, you can use the built in
`validate_jwt` external function as defined above to check that the claims are
what you'd expect.

```yaml
---

test_name: Check we can login then use a JWT to access the API

includes:
  - !include common.yaml

stages:
  - name: login
    request:
      url: "{host}/login"
      json:
        user: test-user
        password: correct-password
      method: POST
      headers:
        content-type: application/json
    response:
      status_code: 200
      body:
        $ext: &verify_token
          function: tavern.testutils.helpers:validate_jwt
          extra_kwargs:
            jwt_key: "token"
            key: CGQgaG7GYvTcpaQZqosLy4
            options:
              verify_signature: true
              verify_aud: true
              verify_exp: true
            audience: testserver
      headers:
        content-type: application/json
      save:
        body:
          test_login_token: token

  - name: Get user info
    request:
      url: "{host}/userinfo"
      method: GET
      Authorization: "Bearer {test_login_token:s}"
    response:
      status_code: 200
      body:
        user_id: 123
      headers:
        content-type: application/json
```

## Controlling secure access

### Running against an unverified server

If you're testing against a server which has SSL certificates that fail
validation (for example, testing against a local development server with
self-signed certificates), the `verify` keyword can be used in the `request`
stage to disable certificate checking for that request.

### Using self signed certificates

In case you need to use a self-signed certificate to connect to a server,
you can use the `cert` key in the request to control which certificates
will be used by Requests.

If you just want to pass your client certificate with a request, pass
the path to it using the `cert` key:

```yaml
---

test_name: Access an API which requires a client certificate

stages:
  - name: Get user info
    request:
      url: "{host}/userinfo"
      method: GET
      cert: "/path/to/certificate"
      # Or use a format variable:
      # cert: "{cert_path}"
    response:
      ...
```

If you need to pass a SSL key file as well, pass a list of length two with the first
element being the certificate and the second being the path to the key:

```yaml
---

test_name: Access an API which requires a client certificate

stages:
  - name: Get user info
    request:
      url: "{host}/userinfo"
      method: GET
      cert:
        - "/path/to/certificate"
        - "/path/to/key"
    response:
      ...
```

See the [Requests documentation](http://docs.python-requests.org/en/master/api/#requests.request)
for more details about this option.

## Uploading files as part of the request

To upload a file along with the request, the `files` key can be used:

```yaml
---

test_name: Test files can be uploaded with tavern

includes:
  - !include common.yaml

stages:
  - name: Upload multiple files
    request:
      url: "{host}/fake_upload_file"
      method: POST
      files:
        test_files: "test_files.tavern.yaml"
        common: "common.yaml"
    response:
      status_code: 200
```

This expects a mapping of the 'name' of the file in the request to the path on
your computer.

By default, the sending of files is handled by the Requests library - to see the
implementation details, see their
[documentation](http://docs.python-requests.org/en/master/user/quickstart/#post-a-multipart-encoded-file).

## Timeout on requests

If you want to specify a timeout for a request, this can be done using the
`timeout` parameter:

```yaml
---
test_name: Get server info from slow endpoint

stages:
  - name: Get info
    request:
      url: "{host}/get-info-slow"
      method: GET
      timeout: 0.5
    response:
      status_code: 200
      body:
        n_users: 2048
        n_queries: 10000
```

If this request takes longer than 0.5 seconds to respond, the test will be
considered as failed. A 2-tuple can also be passed - the first value will be a
_connection_ timeout, and the second value will be the response timeout. By
default this uses the Requests implementation of timeouts - see [their
documentation](http://docs.python-requests.org/en/master/user/advanced/#timeouts)
for more details.

## Using JMES path with the response body

A more generic way to query and save data from the response can be done using the
**jmespath** block. This block can take 3 values, specifying a query
to run on the (JSON) response, an optional expected value, and an optional
name to save the result of this query. Using the above example, this would
be done using:

```yaml
response:
  jmespath:
    - query: thing.nested[0]
      expected: 1  # optional
      save_as: first_val  # optional
``` 

This technique is required when dealing with nested lists. Say that we
_only_ want to make sure that the list in the above response contained
the value `3`, and we do not care about either the order of the list or
how many other values are returned. One way to do this for the given
response would be:

```yaml
response:
  body:
    thing:
      nested:
        - !anyint
        - !anyint
        - 3
        - !anyint
```

This is messy and we need to put extra data into our test when we are
just going to ignore the other values. This will also break if the length
of the list changes or if the types change.

A more robust way of doing this is with the `jmespath` key, using a
similar query to above:

```yaml
response:
  jmespath:
    - query: thing.nested[?@ == `3`]
```

This will just make sure that _one of_ the values in the returned nested
list matches the value we expect, no matter how many other elements there
are, or in what order. The 'expected' key in this situation is the _result_
of the query , ie `[3]`. Because values to be saved can only be 'simple'
values, if you want to save the result of the query
you need to use the [pipe operator](http://jmespath.org/specification.html#pipe-expressions)
like this:

```yaml
response:
  jmespath:
    - query: thing.nested[?@ == `3`] | [0]
      save_as: value_equalling_3
```

For a more complicate example, we might have an endpoint returning a user
with a list of groups they belong to, like so:

```json
{
  "username": "johnny",
  "groups": [
    {
      "groupname": "normal_user",
      "assigned": "2017-09-01"
    },
    {
      "groupname": "special_user",
      "assigned": "2017-09-01"
    }
  ]
}
```

To make sure that this user is in the normal groups but is not an admin,
we can do it like so:

```yaml
response:
  jmespath:
    - query: "groups[?groupname == "admin"]"
      # NOTE: If we do not give an explicit empty list here, Tavern will
      # assume that you expected a value and will cause the test to fail    
      expected: []
    - query: "groups[?groupname == "normal_user]"
      # NOTE: No 'expected' value is given here, so this will match
      # as long as the normal_user group is present
    - query: "groups[?groupname == "special_user].assigned"
      # Save the date the the user was assigned the 'special' group
      # for use in a later test
      save_as: special_assigned_on_date 
```

Due to implementation reasons, this cannot be used to match a null value.

There are much more examples at http://jmespath.org/tutorial.html.

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

## Running against an unverified server

If you're testing against a server which has SSL certificates that fail
validation (for example, testing against a local development server with
self-signed certificates), the `verify` keyword can be used in the `request`
stage to disable certificate checking for that request.

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

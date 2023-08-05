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
status code, the `json` key should be left blank.

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
      json:
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
      json:
        name: test-user
      headers:
        content-type: application/json
```

This test ensures that a cookie called `session-cookie` is returned from the
'login' stage, and this cookie will be sent with all future stages of that test.

#### Choosing cookies

If you have multiple cookies for a domain, the `cookies` key
can also be used in the request block to specify which one to send:

```yaml
---

test_name: Test receiving and sending cookie

includes:
  - !include common.yaml

stages:
  - name: Expect multiple cookies returned
    request:
      url: "{host}/get_cookie"
      method: POST
    response:
      status_code: 200
      cookies:
        - tavern-cookie-1
        - tavern-cookie-2

  - name: Only send one cookie
    request:
      url: "{host}/expect_cookie"
      method: GET
      cookies:
        - tavern-cookie-1
    response:
      status_code: 200
      json:
        status: ok
```

Trying to specify a cookie which does not exist will fail the stage.

To send _no_ cookies, simply use an empty array:

```yaml
---

test_name: Test receiving and sending cookie

includes:
  - !include common.yaml

stages:
  - name: get cookie for domain
    request:
      url: "{host}/get_cookie"
      method: POST
    response:
      status_code: 200
      cookies:
        - tavern-cookie-1

  - name: Send no cookies
    request:
      url: "{host}/expect_cookie"
      method: GET
      cookies: [ ]
    response:
      status_code: 403
      json:
        status: access denied
```

#### Overriding cookies

If you want to override the value of a cookie, then instead of passing a string
to the `cookies` block in the request, use a mapping of `cookie name: cookie
value`:

```yaml
  - name: Override cookie value
    request:
      url: "{host}/expect_cookie"
      method: GET
      cookies:
        - tavern-cookie-2: abc
    response:
      status_code: 200
      json:
        status: ok

```

This will create a new cookie with the name `tavern-cookie-2` with the value
`abc` and send it in the request. If this cookie already exists from a previous
stage, it will be overwritten. Trying to override the cookie multiple times in
one stage will cause an error to occur at runtime.

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
      json:
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
      json:
        $ext: &verify_token
          function: tavern.helpers:validate_jwt
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
        json:
          test_login_token: token

  - name: Get user info
    request:
      url: "{host}/userinfo"
      method: GET
      headers:
        Authorization: "Bearer {test_login_token:s}"
    response:
      status_code: 200
      json:
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

### Uploading a file as the body of a request

In some cases it may be required to upload the entire contents of a file in the
request body - for example, when posting a binary data blob from a file. This
can be done for JSON and YAML using the `!include` tag, but for other data
formats the `file_body` key can be used:

```yaml
  - name: Upload a file in the request body
    request:
      url: "{host}/data_blob"
      method: POST
      file_body: "/path/to/blobfile
    response:
      status_code: 200
```

Like the `files` key, this is mutually exclusive with the `json` key.

### Specifying custom content type and encoding

If you need to use a custom file type and/or encoding when uploading the file,
there is a 'long form' specification for uploading files. Instead of just
passing the path to the file to upload, use the `file_path` and
`content_type`/`content_encoding` in the block for the file:

```yaml
---

test_name: Test files can be uploaded with tavern

stages:
  - name: Upload multiple files
    request:
      url: "{host}/fake_upload_file"
      method: POST
      files:
        # simple style - guess the content type and encoding
        test_files: "test_files.tavern.yaml"
        # long style - specify them manually
        common:
          file_path: "common.yaml"
          content_type: "application/customtype"
          content_encoding: "UTF16"
```

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
      json:
        n_users: 2048
        n_queries: 10000
```

If this request takes longer than 0.5 seconds to respond, the test will be
considered as failed. A 2-tuple can also be passed - the first value will be a
_connection_ timeout, and the second value will be the response timeout. By
default this uses the Requests implementation of timeouts - see [their
documentation](http://docs.python-requests.org/en/master/user/advanced/#timeouts)
for more details.

## Redirects

By default, Tavern will not follow redirects. This allows you to check whether
an endpoint is indeed redirecting a user to a certain page.

To disable this behaviour, use either the `--tavern-always-follow-redirects`
command line flag or set `tavern-always-follow-redirects` to True in your Pytest
settings file.

This can also be disabled or enabled on a per-stage basis by using the `follow_redirects` flag:

```yaml
---
test_name: Expect a redirect when setting the flag

stages:
  - name: Expect to be redirected
    request:
      url: "{host}/redirect/source"
      follow_redirects: true
    response:
      status_code: 200
      json:
        status: successful redirect
``` 

Specifying `follow_redirects` on a stage will override any global setting, so if
you just want to change the behaviour for one stage then use this flag.

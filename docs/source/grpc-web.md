# gRPC-Web integration testing

The gRPC-Web backend allows Tavern to call unary RPC methods over HTTP using the gRPC-Web wire format.

## Enabling the backend

The backend is loaded via the `tavern_grpc_web` entry point. Enable it with:

```bash
pytest --tavern-extra-backends=grpc_web
```

You can also configure this in `pytest.ini`:

```ini
[pytest]
addopts = --tavern-extra-backends=grpc_web
```

## Example

```yaml
test_name: grpc-web hello

includes:
  - !include common.yaml

grpc_web:
  connect:
    base_url: "{grpc_web_base_url}"
    path_prefix: rpc
    timeout: 3
  proto:
    module: helloworld_v1_precompiled_pb2

stages:
  - name: Echo text
    grpc_web_request:
      service: helloworld.v1.Greeter/SayHello
      body:
        name: "John"
    grpc_web_response:
      status: "OK"
      http_status_code: 200
      body:
        message: "Hello, John!"
```

## Connection

Connection settings are configured at the top level in the `grpc_web.connect` block:

```yaml
grpc_web:
  connect:
    base_url: http://localhost:50053
    path_prefix: rpc
    timeout: 10
    verify: true
    headers:
      authorization: "Bearer {token}"
```

Supported keys:

- `base_url`: Base URL of your gRPC-Web endpoint (required)
- `path_prefix`: Prefix inserted before `package.Service/Method` (defaults to `rpc`)
- `timeout`: Default timeout in seconds for every call
- `verify`: TLS verification setting (`true`/`false` or CA bundle path)
- `headers`: Default HTTP headers sent with every request

## Requests

Each stage sends one gRPC-Web request using `grpc_web_request`.

```yaml
stages:
  - name: Call service
    grpc_web_request:
      service: my.package.UserService/GetUser
      body:
        id: "123"
      timeout: 5
      headers:
        x-request-id: "{request_id}"
```

Supported keys:

- `service`: RPC target in `package.Service/Method` format (required)
- `body` or `json`: Request payload as protobuf fields (mutually exclusive)
- `timeout`: Per-stage timeout override
- `headers`: Per-stage HTTP headers merged with default headers

## Responses

Use `grpc_web_response` to validate gRPC and HTTP-level results.

```yaml
stages:
  - name: Expect successful response
    grpc_web_request:
      service: my.package.UserService/GetUser
      body:
        id: "123"
    grpc_web_response:
      status: "OK"
      http_status_code: 200
      body:
        id: "123"
        name: "Alice"
      save:
        body:
          saved_name: name
```

Supported keys:

- `status`: Accepts canonical names (for example `"OK"`) and numeric codes
  (for example `0`); either form is valid.
- `details`: Expected value for the `grpc-message` trailer/header (mapped from
  gRPC error details)
- `http_status_code`: Expected HTTP status code
- `body`: Expected protobuf response body represented as JSON fields
- `save`: Save values from response body for later stages
- `verify_response_with`: External validation function(s)

If `grpc_web_response` is omitted, Tavern still performs the request but no response assertions are made.

## Loading protobuf definitions

Configure protobuf loading in `grpc_web.proto`:

```yaml
grpc_web:
  proto:
    module: my_app.protos.user_pb2
```

or:

```yaml
grpc_web:
  proto:
    source: ./proto
```

- `module`: Import an existing generated protobuf Python module
- `source`: Compile `.proto` file/folder at runtime (requires `protoc`)

At least one of `module` or `source` must be set.

## Example project

See the full runnable example in:

- `example/grpc_web`

Start it with:

```bash
cd example/grpc_web
docker compose up --build
```

Then run tests in another terminal:

```bash
pytest -v --tavern-extra-backends=grpc_web
```

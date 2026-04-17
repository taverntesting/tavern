# gRPC-Web example

This example demonstrates how to use Tavern with the built-in `grpc_web` backend.

It includes:

- a small Flask server that accepts gRPC-Web requests
- a protobuf definition for a `Greeter` service
- Tavern tests using `grpc_web_request` and `grpc_web_response`

## Running the example

1. Start the server:

```bash
docker compose up --build
```

2. In another terminal, run tests:

```bash
uv run pytest -v
```

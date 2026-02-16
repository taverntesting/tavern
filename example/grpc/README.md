# gRPC example

This example demonstrates how to use Tavern to test gRPC services. It includes a simple "Greeter" service that responds
with a hello message.

The example shows three different approaches for handling protobuf definitions:

1. **Pre-compiled** (`helloworld_v1_precompiled.proto`): The protobuf is compiled ahead of time and the generated Python
   module is imported directly by Tavern.
2. **Runtime compilation** (`helloworld_v2_compiled.proto`): The `.proto` source file is compiled by Tavern at test time
   using the `source` key.
3. **Server reflection** (`helloworld_v3_reflected.proto`): No local proto files needed - Tavern discovers the service
   schema by querying the server's reflection API.

The server runs two gRPC endpoints:

- Port 50051: Standard server with pre-compiled and runtime-compiled services
- Port 50052: Server with reflection enabled for the reflection-based tests

## Running the example

1. Start the server:
   ```bash
   docker compose up --build
   ```

2. In another terminal, run the tests:
   ```bash
   py.test -v
   ```

The test file (`tests/test_grpc.tavern.yaml`) demonstrates:

- Basic gRPC requests and responses using `grpc_request` and `grpc_response`
- Saving values from responses for use in subsequent stages
- Using the `connect` block for connection settings
- Using the `proto` block to specify how to load protobuf definitions
- Server reflection for schema discovery
